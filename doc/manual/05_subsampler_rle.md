# Subsampler and run-length encoding {#subsampler-rle}

This chapter describes the two blocks that stretch the time a capture covers: the subsampler,
which keeps one sample every N cycles, and the optional run-length encoder (RLE), which stores a
run of identical samples as one sample and a count. The concepts are introduced in [Embedded
logic analysis in a nutshell](#la-primer).

## At a glance {#sub-glance}

| Item | Subsampler | RLE |
|-------------------|---------------------------------------|----------------------------------------|
| Class | `_SubSampler` | `_RLE` |
| Built | Always | With `with_rle=True` |
| Run-time control | `subsampler_value` = N - 1 | `rle_enable` |
| Range | N from 1 to `2**subsampler_width` | Runs up to `rle_length - 1` repeats per word |
| Applies to | Every sample, pre- and post-trigger; placed after the trigger block | Post-trigger samples only |
| Costs | One counter | One marker bit, a comparator, wider memory |
| Driver | `configure_subsampler(N)` | `configure_rle(True)`, decoding in `upload()` |

## Subsampler {#sub-subsampler}

The subsampler keeps one sample every N cycles of the scope clock and drops the others. A counter
counts the cycles; when it reaches the value of `subsampler_value`, the sample of that cycle goes
on to the storage and the counter restarts from 0. The driver writes N - 1, so N = 1 keeps every
sample.

`configure_subsampler(N)` accepts N from 1 to `2**subsampler_width`, 65536 with the default
width of 16 bits, and raises an error outside this range. The counter runs freely: the kept
cycles are not aligned on the arming of the capture or on the trigger.

The subsampler sits after the trigger, so the trigger compares every cycle. A short event
can fire the trigger and yet be missing from the capture, because the cycle that carried it
was dropped. Every pulse shorter than N cycles may be missed in the same way.

A capture of `length` samples covers `length` x N cycles of the scope clock. For example, 4096
samples with N = 512 at 125 MHz (8 ns) cover 16.8 ms. The pre-trigger window, `offset`, also
counts kept samples.

Do not combine the subsampler with the RLE: with the RLE enabled and N above 1, the capture never
completes ([Limitation: lost samples and subsampling](#rle-limitation)).

The driver records N, and `save()` divides the sample rate of `analyzer.csv` by it to time the
dumps. `save()` reads the recorded N, so call `configure_subsampler()` before saving, even with
N = 1.

## Run-length encoding {#rle}

A run-length encoder stores a run of identical samples as the first sample followed by a repeat
count. Probes that change rarely, such as state machines and status flags, then fill the memory
far more slowly. The RLE is built with `with_rle=True` and used when the host enables it for a
capture; its [status](#intro-status) is given in the introduction.

### Stored words {#rle-words}

With the RLE built, each stored word carries a marker in its most significant bit, as the figure
below shows. Marker 0 is a raw sample; marker 1 is a repeat word whose low bits give the number
of times the previous sample repeats.

![Stored words with RLE. Look at the marker bit: 0 for a raw sample, 1 for a repeat word whose
count field sits in the low bits, the bits in between being zero.](rle_words.svg)

The count field has `bits_for(rle_length - 1)` bits, 8 bits with the default `rle_length` of 256,
and a repeat word holds at most `rle_length - 1` repeats. The stored word must hold either a
sample or a count, plus the marker:

```text
storage_width = max(data_width, bits_for(rle_length - 1)) + 1
```

Without the RLE, `storage_width` equals `data_width`. With the RLE built, the memory is one bit
wider, or more when `rle_length` needs a count wider than the sample. The extra width costs
memory even in the captures that leave the RLE disabled.

### Encoder state machine {#rle-fsm}

The encoder is a state machine of three states, shown in the figure below. BYPASS passes the
samples unchanged. RUN compares each sample with the last one stored and counts the repeats. A
new value is stored raw at once when no repeat is pending. When a new value ends a run, RUN stores
the repeat word and EMIT_RAW stores the new value on the next cycle.

![RLE state machine. Follow a run: BYPASS enters RUN after the trigger; in RUN each identical
sample adds one to the count; a new value after a run emits the repeat word, then EMIT_RAW
stores the new value and returns to RUN.](rle_fsm.svg)

RUN also emits a repeat word in two other cases. When the count reaches `rle_length - 1`, the
word is stored and a new count starts. When the storage is one word from the capture length, the
pending count is stored, so the end of a run is not lost when the capture stops.

The encoder works only while the storage is in its post-trigger phase. The pre-trigger window and
the first samples after the trigger are stored raw. At the end of the capture, the state machine
returns to BYPASS and clears its count.

### Compression {#rle-compression}

A run of N identical samples stores in at most `1 + ceil((N - 1) / (rle_length - 1))` words. With
`rle_length` of 256, a stable run of 256 samples takes 2 words and a run of 1024 samples at most
6 words. The RLE never stores more words than samples, and data that changes on every cycle is
not compressed at all.

With the RLE enabled, `depth` and the capture length count stored words, not samples. A capture
of `length` words can decode into far more samples, and the time it covers depends on the
activity of the probes.

### Decoding {#rle-decoding}

`upload()` decodes the words when the RLE was enabled with `configure_rle(True)`: a raw word adds
one sample, a repeat word adds the previous sample `count` times. `upload(max_samples=N)` keeps
the first N decoded samples. With the RLE built but disabled, the driver strips the marker bit and
returns the raw samples.

`configure_rle(True)` raises an error when `analyzer.csv` reports an analyzer without RLE. The
setting stays until `configure_rle(False)` or `clear()`.

### Limitation: lost samples and subsampling {#rle-limitation}

The encoder stores at most one word per cycle and cannot hold back the samples. Three cases store
a word without taking a new sample: EMIT_RAW after a run ended, a repeat word emitted because the
count is full, and the repeat word stored at the end of the capture. The stream ahead of the
encoder does not wait, so the sample of that cycle is dropped.

The decoded capture is therefore shorter than the time it covers: each case above removes one
sample. The removed sample can be a value of its own: a value that lasts one sample right after
the end of a run is missing from the capture. Read an RLE capture as an approximate view of the
sequence of values, and use a raw capture to measure durations or to see every value.

Do not combine the RLE with subsampling either. With the RLE enabled and N above 1, the encoder
and the subsampler wait for each other after the trigger: the subsampler counts cycles only
while the encoder is ready, and in RUN the encoder is ready only when a sample is offered, which
the subsampler does only at the end of its count.
The capture never completes, and `wait_done()` does not return. [Known issues](#debug-known)
lists these limitations with the others.

## Registers {#sub-registers}

| Register | Access | Meaning |
|-------------------------|--------|------------------------------------------------------|
| `subsampler_value` | rw | N - 1: keep one sample every N cycles, `subsampler_width` bits |
| `rle_enable` | rw | 1 enables the encoder; write it before arming; only with `with_rle` |

[Register reference](#registers) gives the addresses.

## In the code {#sub-code}

| Item | Place |
|-------------------------------|----------------------------------------------------------|
| Subsampler | `_SubSampler`, `litescope/core.py` |
| Encoder | `_RLE`, `litescope/core.py`; enabled by `post_hit` and flushed by `flush` of the storage |
| Storage width rule | `LiteScopeAnalyzer.__init__`, `litescope/core.py` |
| Driver settings | `configure_subsampler()`, `configure_rle()` |
| Decoding | `DumpData.decode_rle()`, `litescope/software/dump/common.py` |

Where to go next: [Storage and read-back](#storage) for the memory that holds the words, [Host
tools](#host-tools) for the `--subsampling` and `--rle` options of the CLI.
