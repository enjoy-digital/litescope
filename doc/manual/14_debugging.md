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
  is a don't care hexadecimal digit, four bits. The driver cuts a value to the width of its
  signal: the extra bits of a wider value are ignored, not compared ([Value
  strings](#trig-values)).
- **The terms make a sequence.** Each term must match after the previous one, on a later sample.
  The CLI orders the terms by option type: all `-r`, then all `-f`, then one term with every `-v`.
  So `-r stb -v adr 0x100` waits for a rising edge of `stb`, then for `adr` at `0x100` later; it
  does not mean "a rising edge while `adr` is `0x100`" ([Trigger terms](#host-cli-triggers)).
- **The group differs.** The driver resolves a signal at its position in the group selected when
  the term is added, and raises `ValueError` for a signal that is not in that group. In a script,
  call `configure_group()` before `add_trigger()`. `configure_group()` and the `--group` option
  of the CLI raise an error for a group that `analyzer.csv` does not list.
- **The name matches another signal.** The CLI matches names as regular expressions: an exact
  name first, else the longest match, and an error when several signals tie or when no signal
  matches ([Signal names](#host-cli-names)).
- **The event came before the arming.** Writes through `litex_server` are buffered. Read a
  register after `run()` and before causing the event, so that the arming has reached the SoC
  ([Register access timing](#host-posted-writes)). The trigger also compares nothing while the
  storage flushes, for `depth` cycles after the arming: an event in that time is not seen
  ([Flush and arming](#stor-flush)).

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

**At the end of the capture.** `upload()` reads the length given to `run()` on the same driver.
A driver that did not run the capture, such as a new script connecting to a capture taken by
another one, does not know that length: its `upload()` reads the words that `storage_mem_level`
reports, and misses the last words of the capture, already in the read path
([Upload](#stor-upload)). Upload from the driver that ran the capture.

**With RLE.** The length counts stored words, not samples. A run of identical samples takes one
word plus one per `rle_length - 1` repeats; `upload(max_samples=N)` caps the decoded samples
([Subsampler and run-length encoding](#subsampler-rle)).

**With subsampling.** The trigger sees every cycle, but only one sample in N is stored. A pulse
shorter than N cycles may be absent from the capture, and the matching sample itself may not be
stored.

## The trigger is not where expected {#debug-position}

The trigger sample is at index `offset` of the capture, and the `scope_trig` marker of the dumps
rises at that sample; the Migen tests lock this position ([Trigger position in the
capture](#trig-position)). Three cases make the capture look different:

- **Subsampling.** The trigger sample is the first kept sample from the match on: the sample that
  matched may not be in the capture.
- **A match soon after the arming.** The pre-trigger window is shorter than `offset`: the memory
  holds only the samples taken since the end of the flush, and the trigger sample sits before
  index `offset`.
- **A match during the flush.** The trigger compares nothing for `depth` cycles after the arming:
  the capture is taken around a later match, if one comes ([Flush and arming](#stor-flush)).

## Wrong time scale {#debug-timescale}

The dumps take their time scale from the `samplerate` of the analyzer, divided by the subsampling
factor. The default, `1e12`, is a placeholder: a VCD file then has `$timescale 500fs`, a time
axis of 1 ps per sample ([Time scale](#fmt-vcd-timescale)). `litex_sim --with-analyzer` passes
the frequency of its system clock.

Pass the frequency of `clock_domain` when building the analyzer, or give it to the dump in a
script: `analyzer.save("dump.vcd", samplerate=100e6)`.

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
CLI takes that name from `--name`, else from the file name of `--csv`: `analyzer.csv` binds
`analyzer_*`. A renamed file, or an analyzer under another attribute name, ends in
`AttributeError` on `trigger_enable`. Pass `--name`, or name the CSV file of each analyzer after
its attribute, as the LiteSATA KC705 target does with `global_analyzer.csv`.

**Read timeouts.** `litescope_cli` creates its `RemoteClient` with `raise_on_timeout=True`: a
register read that gets no answer stops the capture with an error, instead of returning zeros
that would look like samples. Do the same in scripts ([Register access
timing](#host-posted-writes)).

**RLE not available.** `--rle` or `configure_rle(True)` raises "RLE is not available on this
analyzer" when the build has no `with_rle`.

## Known issues {#debug-known}

These behaviours of the code on this revision explain some symptoms; they are listed so that a
reader does not chase them in the design. The status of each feature is in
[the introduction](#intro-status).

| Issue | Effect | Workaround |
|----------------------------------------|------------------------------------------|------------------------------------|
| CLI `--offset` default 32 | `AssertionError` with a depth or a `--length` of 32 or less | Give `--offset` |
| Match during the flush | Not seen: the trigger compares nothing for `depth` cycles after the arming | Cause the event well after the arming |
| `upload()` on a new driver | Without `run()`, reads `storage_mem_level` words: the last words are missing | Upload from the driver that ran the capture |
| `analyzer.csv` | Written when the build returns: after the vendor tools, not at all when they fail | Elaborate with `--no-compile` |
| Default `samplerate` | Placeholder rate: VCD time axis of 1 ps per sample | Pass `samplerate` at build or save |
| CLI exit code 2 without `--json` | Means a trigger timeout or a command-line error (usage) | Use `--json`: command-line errors exit with code 1 |
| CLI term order | Fixed by option type, not command line order | Use the driver for other orders |
| GUI (`--gui`) | One value term, no edges, no timeout | Use the CLI or the driver |

## Where to go next {#debug-next}

[Host tools: CLI, driver and GUI](#host-tools) describes every option used here;
[Simulation and verification](#simulation) reproduces a problem without a board.
