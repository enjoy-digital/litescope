# Build options {#build-options}

This appendix lists the parameters and options of every part of the project: the analyzer and the
IO probe, the driver, `litescope_cli`, and the LiteX tools used with them. The chapters explain
when to use them; this appendix gives their names and defaults.

## Analyzer {#opt-analyzer}

`LiteScopeAnalyzer` (`litescope/core.py`) is a LiteX module: add it to a SoC as an attribute, and
its registers join the bank named after that attribute.

| Parameter | Default | Meaning |
|----------------------------|-------------------------|-----------------------------------------------|
| `groups` | required | A signal, a list, or a dictionary `{n: list}`; a signal or a list is group 0 |
| `depth` | required | Words of the sample memory |
| `samplerate` | `1e12` | Frequency of `clock_domain` in Hz, written to `analyzer.csv` for the dumps; no effect on the gateware |
| `clock_domain` | `"sys"` | Clock domain whose clock samples the probes |
| `trigger_depth` | `16` | Depth of the term memory, a power of two of at least 4; the memory holds `trigger_depth + 1` terms (one in its output register) |
| `subsampler_width` | `16` | Width of the subsampler counter: factors up to `2**subsampler_width` |
| `register` | `False` | Adds a register stage on each group, in `clock_domain`, before the multiplexer |
| `with_rle` | `False` | Adds the run-length encoder and the `rle_enable` register |
| `rle_length` | `256` | Longest run of one RLE word, at least 2 |
| `csr_csv` | `"analyzer.csv"` | File written when the LiteX build returns; `None` writes none |

A group accepts signals, records (flattened into their fields), finalized state machines (their
state signal, with the names of the states), and any other expression, such as a slice or a `Cat`,
which the analyzer drives into a new named signal. Duplicates in a group are removed.

The widths of the analyzer follow from the groups:

| Width | Value |
|----------------------|-------------------------------------------------------------------------|
| `data_width` | Sum of the widths of the probes of the widest group; narrower groups are padded with zeros |
| `storage_width` | `data_width`, or with RLE `max(data_width, bits_for(rle_length - 1)) + 1` |

[Analyzer architecture](#analyzer-architecture) explains the pipeline, and
[Register reference](#registers) the registers these parameters size.

## IO probe {#opt-io}

| Class | Parameter | Meaning |
|-------------------|------------------|------------------------------------------------------------|
| `LiteScopeIO` | `data_width` | Width of the `input` and `output` signals and of the `in` and `out` registers |

## Driver {#opt-driver}

`LiteScopeAnalyzerDriver(regs, name, config_csv=None, debug=False)` binds the registers of `regs`
whose names start with `name`. `config_csv` defaults to `<name>.csv`; `debug=True` prints each
step and a progress bar.

| Method | Effect |
|----------------------------------------------------------|------------------------------------------|
| `configure_group(n)` | Selects group `n` |
| `add_trigger(value, mask, cond)` | Appends a term: raw `value` and `mask`, or `cond`, a dictionary `{signal: string}` |
| `configure_trigger()` | Same as `add_trigger` |
| `add_rising_edge_trigger(name)` | Appends two terms: the signal at 0, then at 1 |
| `add_falling_edge_trigger(name)` | Appends two terms: the signal at 1, then at 0 |
| `configure_subsampler(n)` | Keeps one sample every `n` cycles, `n` from 1 to `2**subsampler_width` |
| `configure_rle(enable)` | Enables the run-length encoder; raises on a build without RLE |
| `run(offset=0, length=None)` | Loads the terms and arms; `offset` below `depth`, `length` up to `depth` (default) |
| `done()`, `wait_done(delay=0.2)` | Tests, or waits without timeout, for the end of the capture |
| `upload(max_samples=None)` | Reads the capture, decodes RLE, caps to `max_samples` samples |
| `save(filename, samplerate, flatten)` | Writes a dump; the extension selects VCD, sigrok, CSV, JSON or Python |
| `get_instant_value(group, name)` | Immediate one-sample capture, returns the value of a signal; raises `IndexError` on this revision ([Known issues](#debug-known)) |
| `clear()` | Drops the terms and the data, disarms |

`LiteScopeIODriver(regs, name)` has `read()` and `write(value)`. [Host tools: CLI, driver and
GUI](#host-tools) describes both drivers with examples.

## litescope_cli {#opt-cli}

| Option | Default | Meaning |
|------------------------------|---------------------|-----------------------------------------------|
| `-r`, `--rising-edge SIG` | | Rising-edge trigger on a signal; repeatable |
| `-f`, `--falling-edge SIG` | | Falling-edge trigger on a signal; repeatable |
| `-v`, `--value-trigger SIG VALUE` | | Value condition; every `-v` goes into one term |
| `-l`, `--list` | | Lists the signals of `--group`; needs no bridge |
| `--host`, `--port` | `localhost`, `1234` | Address of `litex_server` |
| `--csv` | `analyzer.csv` | Analyzer file; its name without extension is the analyzer name |
| `--csr-csv` | `csr.csv` | Register map of the SoC |
| `--group` | `0` | Group to capture |
| `--subsampling` | `1` | Subsampling factor |
| `--rle` | off | Enables RLE for the capture |
| `--offset` | `32` | Pre-trigger window, in words |
| `--length` | depth | Words to capture |
| `--dump` | `dump.vcd` | Dump file; the extension selects the format |
| `--timeout S` | none | Gives up after S seconds without trigger, exit code 2 |
| `--json` | | One JSON object on the output; errors as `{"error": ...}`, exit code 1 |
| `--gui` | | Experimental window built with dearpygui |

The terms are loaded in a fixed order: every `-r`, then every `-f`, then the term of the `-v`
conditions ([Host tools: CLI, driver and GUI](#host-tools)).

## LiteX tools {#opt-litex}

`litex_server` owns the bridge and serves it on a TCP port, `localhost:1234` by default
(`--bind-ip`, `--bind-port`). Choose one transport:

| Transport | Options (defaults) | Bridge in the SoC |
|--------------|--------------------------------------------------|--------------------------------|
| `--uart` | `--uart-port`, `--uart-baudrate` (115200) | `add_uartbone`, or a `crossover+uartbone` UART |
| `--jtag` | `--jtag-config` (`openocd_xc7_ft232.cfg`), `--jtag-chain` (1) | `add_jtagbone` |
| `--udp` | `--udp-ip` (192.168.1.50), `--udp-port` (1234), `--udp-scan` | `add_etherbone` |
| `--pcie` | `--pcie-bar` | LitePCIe with its BAR |
| `--usb` | `--usb-vid`, `--usb-pid` | A USB bridge |
| `--devmem` | `--devmem-base` (`0xff200000`), `--devmem-size` | Hard CPU with `/dev/mem` access |

| LiteX option | Effect |
|--------------------------------------|------------------------------------------------------|
| `litex_sim --with-analyzer` | Analyzer on the CPU buses of the simulated SoC, depth 512 |
| `--build --no-compile` (LiteX-Boards targets), `--no-compile` (`litex_sim`) | Elaborates only: writes `csr.csv` and `analyzer.csv`, compiles nothing |
| `--csr-csv` (any LiteX target) | Path of the register map |

The targets of the other cores add their analyzer with switches of their own, usually
`--with-analyzer`; some benches always build it ([Examples and uses in the ecosystem](#examples)).
