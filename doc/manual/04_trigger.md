# Trigger {#trigger}

This chapter describes the trigger: how it stores its conditions, compares them with the probes,
chains them into sequences and marks the samples that follow. It also covers what the driver adds
on top of the hardware (edges, value strings, re-arming) and where the trigger lands in the
capture. The concepts are introduced in [Embedded logic analysis in a nutshell](#la-primer).

## At a glance {#trig-glance}

| Item | Value |
|-----------------------|-------------------------------------------------------------------|
| Class | `_Trigger` (`litescope/core.py`), instance `trigger` of the analyzer |
| Condition | One term: a mask and a value, as wide as the sample |
| Match | Every masked bit of the sample equals the same bit of the value |
| Sequence | Terms matched one after the other, in the order they were loaded |
| Term memory | Asynchronous FIFO of `trigger_depth` terms (a power of two, at least 4, 16 by default), plus one output register: `trigger_depth + 1` terms |
| Output | `hit` set on every sample after the last term has matched |
| No terms | `hit` set at once: immediate capture |
| Edges | Built by the driver as two-term sequences |
| Not in hardware | OR of terms, counters, timeouts, edge detection, external trigger |

## Terms and the term memory {#trig-memory}

A term is a condition on one sample: a mask selects the bits to compare and a value gives the
expected level of each selected bit. A bit outside the mask is a don't care. A term therefore
expresses an AND of bit conditions over all the probes of the group.

The figure below shows the parts of the trigger. The host loads the terms into a term memory, the
comparator checks the first term of the memory against each sample, and the empty memory gives
`hit`.

![Trigger. Follow a term from the registers through the memory to the comparator: a match pops the
term and the next one is compared. When the memory is empty, hit goes to the subsampler with
every sample.](trig_blocks.svg)

The host writes a term in two registers, `trigger_mem_mask` and `trigger_mem_value`, then pushes
it with a write to `trigger_mem_write`. The term memory is an asynchronous FIFO that carries the
terms from `sys` to the scope domain. `trigger_mem_full` reports a full memory; the driver checks
it before each push and stops with an error.

The FIFO has `trigger_depth` entries, 16 by default. The FIFO of LiteX requires a power of two
of at least 4: another value stops the build. It is a buffered FIFO: its output register holds one
more term, so the memory takes `trigger_depth + 1` terms, 17 by default, before
`trigger_mem_full` rises. The mask and value thus reach the comparator from registers rather than
from the block RAM read port. The comment in the code gives the reason: it keeps the wide
comparator within one clock cycle.

## Comparator {#trig-compare}

The comparator computes `(data & mask) == (value & mask)` on every sample, with the mask and the
value of the first term in the memory. A register stage in front of it delays the sample by one
cycle. Data and `hit` leave the trigger together, so the delay does not move the trigger in the
capture.

A term is consumed when the trigger is enabled and the sample matches it. The memory then pops
the term, and the comparator sees the next term from the next sample on. The trigger compares
every sample of the scope clock: subsampling comes after it and never hides a match from the
trigger.

## Sequences {#trig-sequences}

Several terms form a sequence. The trigger waits for the first term, then for the second, and so
on, and fires once the last term has matched. The figure below shows a sequence of two terms, a
rising edge of a signal `x` as the driver builds it.

![A two-term sequence. Term 1 (x = 0) matches on the first sample where x is low and is consumed;
term 2 (x = 1) is compared from the next sample and matches when x rises; hit is set from that
sample, the trigger sample, on.](trig_sequence.svg)

The terms of a sequence may match on consecutive samples: the next term is ready one cycle after
the previous one is consumed. Nothing limits the time between two terms either: the trigger waits
as long as needed for the next match.

The trigger sets `hit` from the sample that matched the last term on, and keeps it set for the
rest of the capture. `hit` is the empty flag of the memory, so it stays a level until new terms
are loaded. The status register `trigger_done` reports the same flag on the `sys` side.

## Immediate capture {#trig-immediate}

With no term in the memory, the memory is empty and `hit` is set at once. The storage then leaves
its pre-trigger phase on the first sample after its flush: the capture starts immediately, with no
pre-trigger window. The driver does this when no term is configured, and the CLI prints "No
trigger, immediate capture."

## Disarm and re-arm {#trig-rearm}

The trigger compares samples only while `trigger_enable` is 1. On the falling edge of
`trigger_enable`, the trigger drops the terms left in its memory until the memory is empty. This
clears a sequence left half-matched by an earlier capture.

A capture consumes its terms, so each capture needs them again. The driver keeps the list of terms
it was given, and `run()` reloads them on every call:

1. write 0 to `trigger_enable` and poll `trigger_done` until the memory is empty;
2. push each term, checking `trigger_mem_full` first;
3. arm the storage, then write 1 to `trigger_enable`.

A script can therefore call `run()` again without configuring the trigger again. `clear()` empties
the list of terms.

## Edges {#trig-edges}

The hardware has no edge detector. The driver builds an edge from a sequence of two terms on the
same signal, with the mask of that signal:

| Method | First term | Second term |
|----------------------------------|---------------|---------------|
| `add_rising_edge_trigger(name)` | signal = 0 | signal = 1 |
| `add_falling_edge_trigger(name)` | signal = 1 | signal = 0 |

For a 1-bit signal, the second term matches on the first transition after the signal was seen at
the first level, which is the edge. For a wider signal, the terms compare the whole value with 0
and 1: a rising edge is a sample equal to 0 followed later by a sample equal to 1.

An edge takes two terms of the memory. Terms added before or after an edge chain with it into one
sequence, in the order they were added.

## Value strings {#trig-values}

`add_trigger(cond={name: string})` builds one term from a dictionary of signal names and value
strings. The driver places each value at the position of the signal in the selected group, so
select the group with `configure_group()` before adding the terms. All the signals of one
dictionary are ANDed in the same term.

| String | Meaning |
|----------------|-------------------------------------------------------------------|
| `"0b1x0"` | Binary; each `x` is a don't care bit |
| `"0xax"` | Hexadecimal; each `x` after the prefix is a don't care nibble |
| `"12"` | Decimal, read with `int(v, 0)`; all bits of the signal compared |

Values are strings, not integers. The driver tests show the encoding: with a 1-bit `flag` at bit
0 and a 3-bit `state` at bits 1 to 3, `{"flag": "1", "state": "0b1x0"}` gives the mask `0xb` and
the value `0x9`. The raw form, `add_trigger(value, mask)`, takes the mask and value as integers
over the whole sample.

The driver cuts the mask and the value to the width of the signal: the bits of a value wider than
its signal are ignored, so `{"flag": "3", "state": "0"}` compares `flag` with 1 and `state` with 0.
A name that is not in the selected group raises `ValueError`, even when another group has a signal
of that name.

## Trigger position in the capture {#trig-position}

The pre-trigger window, `offset`, asks for that many samples before the trigger. The storage
places the trigger sample, the one that matched the last term, at index `offset` of the capture:
`offset` samples precede it and `length - offset - 1` follow it. The tests lock this position for
offsets from 0 to `length - 1` (`test/test_analyzer.py`). The `scope_trig` variable written by
`save()` rises at the same sample ([Capture files](#file-formats)).

Some cases change what the capture holds around the trigger:

- **Subsampling**: the trigger sample is the first kept sample from the match on, at index
  `offset`. The sample that matched is that sample only when it falls on a kept cycle; otherwise
  it is not in the capture.
- **Offset and length**: `run()` asserts that `offset` is below `length` (`AssertionError`), so
  the capture always holds the trigger sample.
- **Match during the flush**: the trigger receives no sample while the storage flushes. A match in
  that time is not seen, and the capture waits for the next match ([Flush and
  arming](#stor-flush)).
- **Match soon after the flush**: a match less than `offset` samples after the flush ends has a
  shorter pre-trigger window: the capture starts with the first sample after the flush, and the
  trigger sample sits before index `offset`.

## Limits {#trig-limits}

- One sequence of up to `trigger_depth + 1` terms; no OR between terms.
- No counter, no timeout, no edge detector and no external trigger input or output in hardware.
- One analyzer cannot trigger another.
- The comparator spans the whole sample width: a wide group costs a wide comparison in the scope
  domain, see [Adding LiteScope to a SoC](#integration).

## Registers {#trig-registers}

| Register | Access | Meaning |
|---------------------------|--------|---------------------------------------------------------|
| `trigger_enable` | rw | 1 compares samples; the falling edge drops the remaining terms |
| `trigger_done` | ro | Term memory empty: all terms consumed, or none loaded |
| `trigger_mem_mask` | rw | Mask of the next term, `data_width` bits |
| `trigger_mem_value` | rw | Value of the next term, `data_width` bits |
| `trigger_mem_write` | rw | A write pushes the mask and value into the term memory |
| `trigger_mem_full` | ro | Term memory full |

With the analyzer named `analyzer`, the registers are `analyzer_trigger_enable` and so on. When
`data_width` is over 32 bits, the mask and value span several 32-bit words, most significant word
first. [Register reference](#registers) gives the addresses.

## In the code {#trig-code}

| Item | Place |
|---------------------------------|-----------------------------------------------------------|
| Term memory, comparator, `hit` | `_Trigger`, `litescope/core.py` |
| Terms, edges, value strings | `add_trigger()`, `add_rising_edge_trigger()`, `add_falling_edge_trigger()` |
| Reload on each capture | `_load_trigger_terms()`, called by `run()` |
| Driver | `litescope/software/driver/analyzer.py` |

Where to go next: [Storage and read-back](#storage) for the window around the trigger, [Host
tools](#host-tools) for the trigger options of the CLI.
