# Simulation and verification {#simulation}

This chapter describes how LiteScope is checked: the Migen simulations of the gateware, the tests
of the driver, the CLI and the dump writers with fake registers, the end-to-end test of a simulated
SoC in Verilator, and the continuous integration. It is for contributors who change the core and
for users who want to capture in a simulated design.

## Verification strategy {#sim-strategy}

An analyzer that captures wrong data is worse than no analyzer: the waveform looks plausible and
leads the debugging astray. Each part is therefore checked at the cheapest level that exercises
it, and one test runs the whole chain, from the driver to the gateware, through a real bus.

| Level | What runs | Register access | File |
|------------|------------------------------|--------------------|----------------------------|
| Gateware | Trigger, subsampler, RLE, storage, groups, in Migen | Register objects, or a `CSRBank` | `test_analyzer.py` |
| Driver | Configuration, triggers, run, upload, save | Fake registers | `test_driver.py` |
| CLI | Options, triggers, `--json`, `--timeout` | Fake bus and driver | `test_cli.py` |
| Dumps | RLE decoding, VCD, sigrok, CSV, Python | None | `test_dump.py` |
| Example | Elaboration of `examples/arty.py` | None | `test_examples.py` |
| End to end | SoC with a CPU, BIOS and two analyzers, in Verilator | BIOS console | `test_sim.py` |
| Hardware | A board with a bridge | `litex_server` | Not in CI |

The suite collects 62 tests. All but the end-to-end test run in pure Python, with Migen's
simulator for the gateware.

## Running the tests {#sim-run}

The tests are Python `unittest` classes in `test/`, collected by pytest.

```sh
# Whole suite, as the CI runs it
python3 -m pytest -v
# One file, or one test
python3 -m pytest -v test/test_driver.py
python3 -m pytest -v test/test_analyzer.py -k group_mux
# Everything but the Verilator test
python3 -m pytest -v --deselect test/test_sim.py
```

The end-to-end test needs Verilator, the `pexpect` Python package and a RISC-V toolchain for the
BIOS. Without Verilator or `pexpect`, it is skipped, not failed: check that the summary does not
report it as skipped when a change touches the register path.

The continuous integration (`.github/workflows/ci.yml`) runs on Ubuntu 22.04 with Python 3.9. It
installs Verilator, LiteX and its cores with `litex_setup.py`, the RISC-V GCC toolchain, then
LiteScope. It checks that the register appendix of this manual is up to date with the gateware
([Register reference](#registers)), then runs `python3 -m pytest -v`. A second workflow,
`.github/workflows/doc.yml`, checks the figures and the sources of this manual ([Maintaining this
manual](#maintenance)).

## Migen simulations of the gateware {#sim-migen}

`test_analyzer.py` instantiates `LiteScopeAnalyzer` in a small Migen module, with a counter or a
pattern as probe, and drives it the way the driver does: load a term, set the subsampling, the
length and the offset, arm the storage then the trigger, wait for `done`, read the memory.

```python
class DUT(Module):
    def __init__(self):
        counter = Signal(32)
        self.sync += counter.eq(counter + 1)
        self.submodules.analyzer = LiteScopeAnalyzer(counter, depth=512, csr_csv=None)

def generator(dut):
    yield from dut.analyzer.trigger.mem_value.write(0x400)
    yield from dut.analyzer.trigger.mem_mask.write(0xffff)
    yield from dut.analyzer.trigger.mem_write.write(1)
    # [...] subsampler, length, offset, then storage and trigger enables

dut = DUT()
run_simulation(dut, {"sys": [generator(dut)]}, {"sys": 10, "scope": 10})
```

The analyzer has its own clock domain, `scope`, driven by the clock of `clock_domain`. The
simulation must give a clock to both `sys` and `scope`, with the same period for a `sys` analyzer.
The analyzer is a submodule (`self.submodules`): a plain Migen `Module` does not register an
attribute as a submodule, and the simulation would then run without it. `csr_csv=None` keeps the
analyzer from writing an `analyzer.csv` when the design is built; `run_simulation()` writes none
in any case, and the tests write no VCD file.

| Area | What the tests check |
|------------------------|--------------------------------------------------------------------|
| Capture | Value trigger, offset 8, subsampling 3: consecutive kept samples, match at index 6 |
| Groups | Trigger and capture on group 1 of two groups |
| Raw data | Without RLE, a set most significant bit is data, not a marker |
| RLE | A constant probe, runs of different lengths, an RLE build with RLE disabled |
| Probe lists | Records flattened, duplicates removed, expressions and slices accepted and named |
| `analyzer.csv` | Configuration and signal rows, state names of a state machine |
| Host access | 128-bit trigger and read-back through a `CSRBank`, twice in a row |

The last test drives the analyzer only through a `CSRBank` on a 32-bit bus, as the host does: wide
registers are written most significant word first, and each stored word is read as four 32-bit
sub-words. It captures twice in a row, so it also checks the re-arming.

Three tests lock the position of the matching sample in the capture: index 6 for an offset of 8,
with and without subsampling, and index 0 for an offset of 0. A change of the trigger pipeline must
keep them, since dumps and scripts rely on the position ([Storage and read-back](#storage)).

## Driver, CLI and dump tests {#sim-host}

The host side is tested without any gateware. `test_driver.py` gives the driver a fake register
set (`FakeRegs`), whose registers record their writes and return programmed reads. A test writes an
`analyzer.csv`, creates the driver, calls its methods and checks the register writes or the
decoded data.

| Area | What the tests check |
|------------------------|--------------------------------------------------------------------|
| Configuration | Offsets and masks of the signals per group; initial disable of the analyzer |
| Triggers | Parsing of `0b` and `0x` values with don't care digits; edges as two terms; memory full |
| Run | Subsampler range, offset and length writes, terms reloaded on each run |
| Upload | Packing of 32-bit sub-words, `max_samples`, RLE decoding of random streams |
| Save | sigrok session, VCD with GTKWave filter files for enumerations |

`test_cli.py` replaces the `RemoteClient` and the driver with fakes and runs the entry points of
`litescope_cli`. It checks the options, the wiring of the triggers, the JSON output of `--list` and
of a capture, the error object and the exit code 2 of `--timeout`. `test_dump.py` checks the dump
writers and the RLE decoder on hand-made data.

## End-to-end test in Verilator {#sim-e2e}

`test_sim.py` builds a `litex_sim` SoC with a VexRiscv CPU and its BIOS, adds two analyzers, and
runs it in Verilator. The test then drives the analyzers with the real driver, through the BIOS
console, as the figure below shows.

![End-to-end test. The driver reads and writes registers through `CSRBuilder`; `BIOSMemAccess`
turns each access into a `mem_read` or `mem_write` command of the BIOS, sent over the TCP socket of
the simulated serial port.](sim_e2e.svg)

| Item | Value |
|------------------------|----------------------------------------------------------------|
| SoC | `SimSoC` of `litex_sim`, 128 KiB ROM, 64 KiB main RAM, `sys` at 1 MHz |
| Serial port | `serial2tcp` module on a free TCP port of the host |
| `analyzer` | 32-bit counter, depth 64, `samplerate` = system clock |
| `analyzer_rle` | 4-bit constant 5, depth 64, `with_rle=True`, `rle_length=8` |
| Register access | `CSRBuilder` on `BIOSMemAccess`: one BIOS `mem_read` or `mem_write` per 32-bit word; `mem_read` reads the four bytes one by one |

The SoC never exits while the test runs, so `analyzer.csv` would not be written at exit. The test
passes a `pre_run_callback` to the builder that calls `export_csv()` of each analyzer before the
simulation starts.

The test first checks the scratch register of the SoC, then makes two captures. The raw capture
has no trigger, an offset of 0 and a length of 16. The test accepts 8 to 16 samples that do not
decrease, for two reasons. The upload reads the level of the memory, which misses the last words
([Known issues](#debug-known)). Each byte read of `mem_read` is a read of `storage_mem_data`, which
takes a word out of the capture, so one 32-bit read consumes four words and the samples are not
consecutive. The RLE capture has a length of 32 encoded words and an upload capped at 10 samples:
the 10 samples must all be 5.

## Adding a test {#sim-adding}

Pick the cheapest level that shows the behaviour:

- A change of the gateware: a Migen test in `test_analyzer.py`, with a counter as probe so that
  every sample is known. Check the samples, not only the count.
- A change of the register map or of the host access pattern: a test through a `CSRBank`, as the
  wide trigger test does.
- A change of the driver, the CLI or a dump writer: a test with the fakes of `test_driver.py` or
  `test_cli.py`.
- A change that crosses the bus: run `test_sim.py` locally, with Verilator installed.

Keep the tests fast and silent: temporary directories for written files, no VCD file. Trigger well
after the arming: the storage drops the samples of its first `depth` cycles while it flushes, so a
match in that window is not where the test expects it.

## Capturing in a simulated design {#sim-litex-sim}

`litex_sim --with-analyzer` gives a simulated SoC with an analyzer on the CPU buses
([The simulated SoC of LiteX](#ex-litex-sim)). The host reaches it with `litex_server` through a
bridge of the simulation, and captures with `litescope_cli` as on a board.

The simulation runs until it is stopped, so `analyzer.csv` is not written by the run. Generate it
first with an elaboration that compiles nothing, from the same directory:

```sh
# Elaborate only, with the options of the run: writes analyzer.csv and csr.csv, then exits
litex_sim --with-analyzer --uart-name=crossover+uartbone --csr-csv csr.csv --no-compile
# Then build and run the simulation with the same options
```

The register map in `csr.csv` depends on the options, the bridge in particular: give the
elaboration the options of the run.

[Getting started](#getting-started) gives the full session, with the bridge and the capture. To
add an analyzer to a simulated design of your own, either run the same elaboration first, or call
`export_csv()` from a `pre_run_callback`, as `test_sim.py` does. Pass `samplerate` with the
frequency of the simulated clock, so that the dumps carry the right time scale.

## Where to go next {#sim-next}

[Debugging LiteScope itself](#debugging) lists what to check when a capture misbehaves;
[Examples and uses in the ecosystem](#examples) gives designs to start from.
