# Storage and read-back {#storage}

This chapter describes the end of the pipeline: the sample memory, the state machine that keeps
the window around the trigger, and the read path that brings the words to the host. Read it to
size the memory, to choose the pre-trigger window and the capture length, and to understand what
`upload()` returns.

## At a glance {#stor-glance}

| Item | Value |
|---------------------|------------------------------------------------------------------------|
| Class | `_Storage` (`litescope/core.py`), instance `storage` of the analyzer |
| Memory | Synchronous FIFO of `depth` words of `storage_width` bits, in block RAM |
| State machine | IDLE, FLUSH, WAIT, RUN, in the scope domain |
| Pre-trigger window | `storage_offset` words, below `length` |
| Capture length | `storage_length` words, up to `depth` |
| Read path | Clock-crossing FIFO of 4 words, then 32-bit words when wider |
| Read-out | `length` words, read from `storage_mem_data` |

## Sample memory {#stor-memory}

The memory is a synchronous FIFO of `depth` words in the scope domain, built as a buffered FIFO
that maps to block RAM. A word is `storage_width` bits: the sample width, plus the marker bit
when the RLE is built ([Stored words](#rle-words)). The memory costs `depth` x `storage_width`
bits of block RAM.

The memory works as a FIFO during the whole capture. Before the trigger, it drops its oldest word
to keep the pre-trigger window; after the trigger, it fills up to the capture length; once the
capture is over, it empties into the read path.

## State machine {#stor-fsm}

The storage is a state machine of four states, shown in the figure below. The text under each
state says what it does to the memory.

![Storage state machine. Follow one capture from left to right: the rising edge of enable flushes
the memory, WAIT keeps the pre-trigger window until hit, RUN fills the memory up to the capture
length, and IDLE hands the words to the read path.](stor_fsm.svg)

| State | Memory | Leaves on |
|-------|--------------------------------------------------------|----------------------------------|
| IDLE | Drains into the read path; `storage_done` is 1 | Arming: rising edge of `storage_enable` |
| FLUSH | Drains and drops; incoming samples are dropped; the read path is emptied too | `depth` cycles |
| WAIT | Stores every sample; drops the oldest beyond `offset` words | First sample with `hit` set |
| RUN | Stores samples while it holds fewer than `length` words | `length` words held |

FLUSH empties what an earlier capture left in the memory and in the read path, so that the upload
starts with the first word of the new capture. It lasts `depth` cycles of the scope clock,
whatever the memory holds. The storage is *armed* in WAIT and RUN: only then does the trigger
receive samples.

`storage_done` drops at the rising edge of `storage_enable`, in the `sys` domain, and stays low
until the storage has left IDLE. A read of `done()` right after `run()` thus never reports the
previous capture.

In RUN, the storage tells the RLE that the capture is in its post-trigger phase (`post_hit`), and
asks it to store its pending count when one word is left (`flush`). Without the RLE, these
signals are not used.

### Pre-trigger window {#stor-window}

In WAIT, the memory keeps the most recent samples and drops the older ones. The first sample
with `hit` set is stored in WAIT too. RUN then drops the pre-trigger samples still in flight in
the buffered memory until exactly `offset` samples precede the trigger sample, and adds samples
up to `length` words in total. The capture thus holds `offset` words before the trigger sample,
the trigger sample at index `offset`, and the rest after it ([Trigger position in the
capture](#trig-position)). With no trigger term, `hit` is already set when WAIT starts, and the
capture starts at once with no pre-trigger window.

### Flush and arming {#stor-flush}

The trigger receives samples only while the storage is armed, in WAIT and RUN. The driver writes
`trigger_enable` right after `storage_enable`. When this write reaches the analyzer before FLUSH
ends, which happens when register writes take less than `depth` cycles of the scope clock (a CPU
in the SoC, a simulation), the trigger still compares nothing until FLUSH ends: a match during
FLUSH is not seen, and the capture waits for the next match. Over a slow bridge, such as
UARTBone, the write arrives after FLUSH, as in the figure of [Capture sequence](#arch-capture).

A match that comes less than `offset` samples after FLUSH ends has a shorter pre-trigger window:
the capture starts with the first sample after FLUSH. Both cases matter for an event that follows
the arming closely, such as an event caused by the register write that arms the trigger: cause
the event at least `depth + offset` cycles of the scope clock after the arming.

## Read path {#stor-readpath}

Once the capture is over, the storage returns to IDLE and the memory drains into the read path,
as the figure below shows. A clock-crossing FIFO of 4 words carries the words to `sys`. When the
word is wider than 32 bits, a converter splits it into 32-bit sub-words, after padding it to a
multiple of 32 bits.

![Read path. Follow the words from the sample memory through the clock-crossing FIFO and the
converter to the mem_data register; mem_level reports the words left in the sample
memory.](stor_readpath.svg)

Each read of `storage_mem_data` pops one sub-word, the least significant sub-word of a word
first. The read path also pops words while `storage_enable` is 0, and during FLUSH. Keep
`storage_enable` at 1 until the upload is over: the driver leaves it at 1 after `run()`, and
creating a driver does not change it, so a script can connect again and upload a capture taken
by another one.

With a CSR bus narrower than 32 bits, `storage_mem_data` spans several addresses, and the pop
happens on the read of its last address, the least significant part with the default big-endian
ordering. Read all the addresses of the register: a tool that reads only some of them loses
samples.

`storage_mem_level` reports the number of words in the sample memory. It crosses to `sys` through
a `MultiReg` and is only meaningful once `storage_done` is 1.

## Upload {#stor-upload}

`upload()` reads the capture length given to `run()` in words from `storage_mem_data`. It does not
use `storage_mem_level`: once the capture is done, the last words have already moved into the
clock-crossing FIFO, and the level does not count them. Without a `run()` on the same driver, the
length is unknown and `upload()` falls back to `storage_mem_level`, which misses those words.

The reads use fixed-address bursts of up to 192 sub-word reads, and the driver assembles the
sub-words into words. With the RLE enabled, it then decodes the words ([Decoding](#rle-decoding)).
The Verilator test reads a 16-word capture and checks 16 consecutive samples (`test/test_sim.py`).

## Choosing depth, offset and length {#stor-sizing}

- `depth` is fixed at build time and sets the block RAM cost; `run(offset, length)` asserts that
  `offset` is below `depth` and below `length`, and that `length` is at most `depth`
  (`AssertionError`).
- `length` defaults to `depth` in the driver; a shorter length ends the capture sooner.
- The capture holds `offset` samples before the trigger sample and `length - offset - 1` after it
  ([Trigger position in the capture](#trig-position)).
- With the RLE enabled, `depth`, `offset` and `length` count stored words, not samples.

[Performance and resources](#performance) covers the resources of the analyzer.

## Registers {#stor-registers}

| Register | Access | Meaning |
|---------------------------|--------|-------------------------------------------------------|
| `storage_enable` | rw | Rising edge arms a capture; keep 1 while uploading |
| `storage_done` | ro | Storage in IDLE: no capture running; 0 from the arming on |
| `storage_length` | rw | Capture length in words, `bits_for(depth)` bits |
| `storage_offset` | rw | Pre-trigger window in words, `bits_for(depth)` bits |
| `storage_mem_level` | ro | Words left in the sample memory, `bits_for(depth)` bits |
| `storage_mem_data` | ro | Read port: each read pops one sub-word, `min(32, storage_width)` bits |

[Register reference](#registers) gives the addresses.

## In the code {#stor-code}

| Item | Place |
|---------------------------------|---------------------------------------------------------|
| Memory, state machine, read path | `_Storage`, `litescope/core.py` |
| Arming, offset and length | `run()`, `litescope/software/driver/analyzer.py` |
| Polling | `done()`, `wait_done()` |
| Read-out and decoding | `upload()` |

Where to go next: [Host tools](#host-tools) to run captures and save dumps, [Capture
files](#file-formats) for the formats of the dumps.
