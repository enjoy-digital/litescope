# Debugging LiteScope itself {#debugging}

This chapter helps when the analyzer is the problem: a capture that never triggers, triggers at
once, misses samples, or shows a waveform that cannot be right. It gives a method, the registers
that tell the state of a capture, the usual causes of each symptom, and the known issues of the
code.

## Method {#debug-method}

Work from the host towards the gateware, and check each step before the next one.

1. Check the bridge and the SoC: `litex_server` runs, and `litex_cli --ident` prints the identifier
   of the build you expect.
2. Check that `analyzer.csv` and `csr.csv` come from that build ([Register access and
   files](#debug-files)).
3. List the probes with `litescope_cli --list` and take the names from there.
4. Make an immediate capture, without trigger. It checks the whole read path without depending on
   the design.
5. Add the trigger, one term at a time.

```sh
# Identifier of the SoC, then the state registers of the analyzer
litex_cli --ident
litex_cli --regs --filter analyzer_storage_done
litex_cli --regs --filter analyzer_trigger_done
# Probes, then an immediate capture
litescope_cli --list
litescope_cli --offset 0
```

The `AGENTS.md` file of the repository and the LiteX wiki page on debugging a SoC on hardware
describe the same method for the whole SoC: registers first, then narrow captures.

## Reading the state of a capture {#debug-state}

Three registers tell where a capture stands. Read them with `litex_cli` while the CLI waits, or
from a script with the driver ([Register reference](#registers)). Do not read `storage_mem_data`
by hand: each read takes a word out of the capture. `litex_cli --regs` reads every register whose
name contains the filter, so a filter on `analyzer` alone reads it and drains the capture.

| `storage_done` | `trigger_done` | State |
|------------------|------------------|------------------------------------------------------|
| 0 | 0 | Armed, waiting for the trigger: at least one term is pending |
| 0 | 1 | Triggered, or no term: the storage fills the post-trigger samples |
| 1 | 0 | Idle with terms loaded: not armed yet, or the storage was never enabled |
| 1 | 1 | Capture complete, or nothing started; `storage_mem_level` gives the stored words |

A capture that stays in the first state for long waits for an event that does not come, or for a
term that cannot match. One that stays in the second state fills slowly: with a large subsampling
factor, the post-trigger part of the capture takes `length` times the factor cycles.

`storage_mem_level` crosses into the system clock domain bit by bit, without Gray coding. Read it
once `storage_done` is 1; a value read during the capture may be wrong.

## The capture never triggers {#debug-no-trigger}

Check the terms before the design. The usual causes:

- **The value is not a string.** The driver parses `"0x10"`, `"0b1x0"` or `"16"`. An integer
  raises a `TypeError` in `add_trigger()`; the CLI always passes strings
  ([Value strings](#trig-values)).
- **The value does not mean what you think.** In `0b1x0`, `x` is a don't care bit; in `0x1x`, `x`
  is a don't care hexadecimal digit, four bits. Give values that fit the signal: the extra bits
  of a wider value spill into the next signal of the same term ([Known issues](#debug-known)).
- **The terms make a sequence.** Each term must match after the previous one, on a later sample.
  The CLI orders the terms by option type: all `-r`, then all `-f`, then one term with every `-v`.
  So `-r stb -v adr 0x100` waits for a rising edge of `stb`, then for `adr` at `0x100` later; it
  does not mean "a rising edge while `adr` is `0x100`" ([Trigger terms](#host-cli-triggers)).
- **The group differs.** The driver resolves a signal at its position in the group selected when
  the term is added. In a script, call `configure_group()` before `add_trigger()`.
- **The group does not exist.** `configure_group()` writes any number. With a group that the
  build does not have, no samples reach the trigger and the storage, and the capture never
  completes. Take the group numbers from `analyzer.csv`.
- **The name matches another signal.** The CLI matches names as regular expressions: an exact
  name first, else the longest match, and an error when several signals tie
  ([Signal names](#host-cli-names)).
- **The event came before the arming.** Writes through `litex_server` are buffered. Read a
  register after `run()` and before causing the event, so that the arming has reached the SoC
  ([Register access timing](#host-posted-writes)).

For a condition at the time of an edge, build the two terms yourself with the driver: the signal
at 0, then the signal at 1 together with the condition.

```python
analyzer.configure_group(0)
analyzer.add_trigger(cond={"stb": "0"})
analyzer.add_trigger(cond={"stb": "1", "adr": "0x100"})
analyzer.run(offset=32, length=256)
```

In scripts, never wait forever: `litescope_cli --timeout S` exits with code 2 when the trigger did
not fire, and `wait_done()` of the driver has no timeout, so poll `done()` instead. The term
memory holds `trigger_depth + 1` terms, 17 by default: a longer sequence makes `run()` raise
`ValueError` ("Trigger memory full").

## The capture triggers at once {#debug-immediate}

A capture with no term fires at once: the CLI prints `No trigger, immediate capture.`. When terms
are loaded, the first one matched on the first samples. A value term on a level that is already
true matches at once; trigger on the edge that starts the level instead, or start the sequence
with the opposite value.

When you write the registers by hand, drop `trigger_enable` to 0 and wait for `trigger_done`
before loading new terms: the falling edge flushes the terms left by the previous capture. Load
the terms before the rising edge of `storage_enable`, then set `trigger_enable`, in the order of
`run()` ([Trigger](#trigger)).

## Samples are missing {#debug-missing}

**At the end of the capture.** `upload()` reads as many words as `storage_mem_level` reports. Once
the capture is complete, the last four words have already moved from the memory into the
clock-crossing FIFO of the read path, and the level does not count them. The upload then misses
them: the CLI prints `upload (words=N)` with N four below the length, and a capture of 4 words or
less uploads nothing, which makes `get_instant_value()` raise `IndexError`. Ask for a length a few
words larger than needed ([Upload](#stor-upload)).

**With RLE.** The length counts stored words, not samples. A run of identical samples takes one
word plus one per `rle_length - 1` repeats; `upload(max_samples=N)` caps the decoded samples
([Subsampler and run-length encoding](#subsampler-rle)). On this revision the encoder also drops
one sample each time it stores a repeat word, the value that ends a run, or the word at the end of
the capture: decoded runs are shorter than the real ones, and a value that lasts one sample right
after a run is missing ([Limitation](#rle-limitation)). Use a raw capture to measure durations or
to see every value. With subsampling above 1, an RLE capture never completes.

**With subsampling.** The trigger sees every cycle, but only one sample in N is stored. A pulse
shorter than N cycles may be absent from the capture, and the matching sample itself may not be
stored.

## The trigger is not where expected {#debug-position}

The trigger sample does not land at index `offset` of the capture but at index `offset - 2`, or
0 when `offset` is 2 or less; the Migen tests lock this position ([Trigger position in the
capture](#trig-position)). Look for the matching value in the data rather than counting samples
from the start.

The `scope_trig` marker of the dumps does not mark the trigger either. The dumps write each sample
twice, next to a generated `scope_clk`, and the marker rises at entry `offset` of that doubled
list, which is sample `offset / 2` ([What every dump contains](#fmt-common)).

The pre-trigger window is shorter than `offset` when the trigger fires soon after the arming: the
memory holds only the samples taken since the end of the flush. The storage drops every sample for
`depth` cycles after the arming, while it flushes. When the arming of the trigger reaches the
analyzer before the flush ends (a CPU in the SoC, a simulation), a match in that window is lost
and the capture starts at the end of the flush, without a pre-trigger window ([Limitation: match
during the flush](#stor-flush)).

## Wrong time scale {#debug-timescale}

The dumps take their time scale from the `samplerate` of the analyzer, divided by the subsampling
factor. The default, `1e12`, is a placeholder: a VCD file then has `$timescale 0ps`, which gives no
usable time axis. `litex_sim --with-analyzer` keeps that default ([Time scale](#fmt-vcd-timescale)).

Pass the frequency of `clock_domain` when building the analyzer, or give it to the dump in a
script: `analyzer.save("dump.vcd", samplerate=100e6)`. The sigrok writer rounds the rate down to a
whole number of MHz, so rates below 1 MHz are written as 0 MHz.

## Timing failures and wrong clock domain {#debug-timing}

The analyzer adds a wide comparator, a group multiplexer and a memory in `clock_domain`. Wide
groups in a fast domain are the usual cause of timing failures, and a design that fails timing can
show captures that look plausible but are wrong.

Keep groups well below 128 bits, prefer the system clock domain, and read the timing report
before trusting a capture.

`register=True` adds a register stage on each group before the multiplexer, which cuts the path
from the probes. The comparator already works on a registered sample, and the terms come from
registers.

Every probe must be in `clock_domain`. A probe from another domain is sampled without
synchronization: a bus can be captured in the middle of a change.

Copy a slow signal into the domain of the analyzer first, as the LitePCIe benches do with a
`MultiReg` ([Examples and uses in the ecosystem](#examples)). A `MultiReg` suits single bits and
values that change rarely: on a change of a multi-bit value, one sample can mix old and new bits.
Use a Gray code or a `BusSynchronizer` when every sample must be a valid value. The internal clock
domain of the analyzer has no reset: a reset of the SoC does not reset its state machines.

## Register access and files {#debug-files}

**`analyzer.csv` not found.** The analyzer writes it when the LiteX build returns, to the path of
`csr_csv`, relative to the current directory and not to the build directory. On a board this is
after the vendor tools, and a failed toolchain run leaves no file; `--no-compile` writes it after
the elaboration. With `litex_sim`, the simulation does not exit while you capture: generate the
file first with `--no-compile` ([Capturing in a simulated design](#sim-litex-sim)).

**A stale `analyzer.csv`.** The file gives the position of every probe in a sample. A file from
another build gives wrong values and triggers on the wrong bits without any error. Keep
`analyzer.csv` and `csr.csv` from the same build, and rebuild both after a change of the probes.

**The name of the analyzer.** The driver binds the registers whose names start with its name. The
CLI takes that name from the file name of `--csv`: `analyzer.csv` binds `analyzer_*`. A renamed
file, or an analyzer under another attribute name, ends in `AttributeError` on `trigger_enable`.
Name the CSV file of each analyzer after its attribute, as the LiteSATA KC705 target does with
`global_analyzer.csv`.

**RLE not available.** `--rle` or `configure_rle(True)` raises "RLE is not available on this
analyzer" when the build has no `with_rle`.

## Known issues {#debug-known}

These behaviours of the code on this revision explain some symptoms; they are listed so that a
reader does not chase them in the design. The status of each feature is in
[the introduction](#intro-status).

| Issue | Effect | Workaround |
|----------------------------------------|------------------------------------------|------------------------------------|
| Trigger position | The match is at index `offset - 2`, 0 for `offset` up to 2 | Find the matching value in the data |
| `scope_trig` marker | Rises at sample `offset / 2` | Ignore it; use the data |
| `upload()` reads `storage_mem_level` words | The last four words are missing; nothing for a length of 4 or less | Ask for a longer capture |
| `get_instant_value()` | `IndexError`: the one-word capture is already in the read path | Capture a few words with `run()` and read the first |
| `run()` with `offset` not below `length` | The capture ignores `length` and holds pre-trigger samples only | Keep `offset` below `length` |
| CLI `--offset` default 32 | Assertion with a depth of 32 or less; no post-trigger sample with `--length` 32 or less | Give `--offset` |
| `configure_group()` with an unknown group | The capture never completes | Use a group listed in `analyzer.csv` |
| Match during the flush | With a fast arming, the match is lost and the capture has no pre-trigger window | Cause the event well after the arming |
| Trigger value wider than its signal | The extra bits compare the next signal of the term | Give values that fit the signal |
| RLE encoder | One sample dropped per repeat word, per run end and at the end: runs too short, single-sample values lost | Measure durations on a raw capture |
| RLE with subsampling | The capture never completes | Do not combine them |
| `analyzer.csv` | Written when the build returns: after the vendor tools, not at all when they fail | Elaborate with `--no-compile` |
| Default `samplerate` | VCD with `$timescale 0ps` | Pass `samplerate` at build or save |
| GTKWave save file | The state name trace is shown in binary | Select it, Data Format, ASCII |
| sigrok dump | Saving `x.sr` deletes a directory `x/` next to it | Save in a directory of its own |
| sigrok rate | Rounded down to whole MHz | Use VCD below 1 MHz |
| `save()` before the subsampling is set | `AttributeError` on `subsampling` | Set the subsampling first, even to 1 |
| CLI exit code 2 | Means a trigger timeout or a command-line error (usage, no JSON) | Check that the output holds a JSON object |
| CLI term order | Fixed by option type, not command line order | Use the driver for other orders |
| CLI name matching | With one probe, any name selects it; with several and no match, "Found multiple candidates" | Use exact names from `--list` |
| `examples/arty.py` comments | Signal names of an older LiteX | Take the names from `--list` |
| GUI (`--gui`) | Experimental: fixed default length, group and subsampling, one value term | Use the CLI or the driver |

The two RLE rows are described in [Limitation: lost samples and subsampling](#rle-limitation).

## Where to go next {#debug-next}

[Host tools: CLI, driver and GUI](#host-tools) describes every option used here;
[Simulation and verification](#simulation) reproduces a problem without a board.
