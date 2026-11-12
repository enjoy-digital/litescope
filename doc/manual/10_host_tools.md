# Host tools: CLI, driver and GUI {#host-tools}

This chapter describes the software that runs on the host: how it reaches the analyzer through
`litex_server`, the `litescope_cli` command, the Python driver for scripted captures, the
GUI and the `litex_mcp` tools. It is the reference for every option and method; the
first capture, step by step, is in [Getting started](#getting-started).

## At a glance {#host-glance}

| Tool | Role | Code |
|--------------------|------------------------------------|------------------------------------|
| `litescope_cli` | One capture from the shell, to a dump | `litescope_cli.py` |
| The driver | Captures from Python scripts | `LiteScopeAnalyzerDriver` |
| IO probe driver | Read and write the IO probe | `LiteScopeIODriver` |
| GUI | Capture window, `litescope_cli --gui` | `run_gui()`, dearpygui |
| `litex_server` | Bridge between TCP and the SoC bus | LiteX |
| `litex_mcp` | Captures as MCP tools for agents | LiteX |

All of them read two files of the build: `analyzer.csv`, which describes the probes and groups
([Capture files](#file-formats)), and `csr.csv`, which gives the register addresses.

## From the host to the analyzer {#host-stack}

The analyzer is a set of registers on the SoC bus. The host tools never talk to the FPGA
directly: they send register reads and writes over TCP to `litex_server`, which forwards them
over the bridge of the SoC. The figure below shows the chain.

![Host tools stack. The CLI and Python scripts use the driver, which needs analyzer.csv and
csr.csv and reaches litex_server over TCP; litex_server carries the register accesses over the
bridge of the SoC to the analyzer.](host_stack.svg)

On the host, the TCP client is `RemoteClient` of LiteX. It loads the register map from `csr.csv`
and exposes every register by name in `bus.regs`, each with `read()` and `write()` methods. The
driver takes this object and binds the registers whose names start with the analyzer name.

### Starting `litex_server` {#host-server}

`litex_server` takes one transport option, which must match the bridge built into the SoC
([Integration](#integration) adds the bridge). It listens on `localhost:1234` by default
(`--bind-ip`, `--bind-port`); `litescope_cli` connects there unless `--host` and `--port` say
otherwise.

| Bridge in the SoC | Server options | Defaults |
|--------------|--------------------------------------|----------------------------------------|
| UARTBone | `--uart --uart-port PORT` | `--uart-baudrate 115200` |
| JTAGBone | `--jtag` | see below |
| Etherbone (UDP) | `--udp` | `--udp-ip 192.168.1.50`, `--udp-port 1234` |
| PCIe (LitePCIe) | `--pcie --pcie-bar BAR` | none, the BAR is required |
| USB | `--usb` | `--usb-vid` or `--usb-pid` required |
| Hard CPU memory | `--devmem` | `--devmem-base 0xff200000` |

`--jtag` drives OpenOCD with `--jtag-config` (`openocd_xc7_ft232.cfg` by default), `--jtag-chain`
(1) and `--jtag-port` (20000, the OpenOCD stream port). `--udp-scan` lists the Etherbone devices
on the subnet of `--udp-ip` and exits. The server serves several clients at once, so
`litescope_cli` can capture while a script reads other registers.

```sh
# Etherbone board at the LiteX default address
litex_server --udp --udp-ip 192.168.1.50
# UARTBone on a USB serial adapter
litex_server --uart --uart-port /dev/ttyUSB1
```

### Register access timing {#host-posted-writes}

`RemoteClient` sends a write and returns without waiting for the SoC. A read waits for its
answer, so it also guarantees that the writes sent before it are done. `run()` ends with a write:
read any register afterwards, for example with `analyzer.done()`, before causing the event to
capture, or the event can happen before the trigger is armed.

A read that gets no answer within the client timeout (2 s) returns zeros instead of raising an
error, unless the client is created with `raise_on_timeout=True`. A capture uploaded over a
broken link can then come back as zeros; scripts should pass `raise_on_timeout=True`, as
`litescope_cli` does.

## `litescope_cli` {#host-cli}

`litescope_cli` runs one capture: it selects the group, the subsampling and the run-length encoding
(RLE) setting, loads the trigger terms, arms the analyzer, waits, uploads the words and writes a
dump. The figure below shows the steps and the three exit codes.

![One litescope_cli capture. The tinted steps are the ones that touch the trigger. An error
after the command line is parsed exits with code 1; a trigger that does not fire within --timeout
exits with code 2; a written dump exits with code 0.](host_cli_flow.svg)

### Options {#host-cli-options}

| Option | Default | Meaning |
|------------------------|------------------|----------------------------------------------|
| `-r`, `--rising-edge` | none | Rising edge of a signal; repeatable |
| `-f`, `--falling-edge` | none | Falling edge of a signal; repeatable |
| `-v`, `--value-trigger` | none | Signal and value; repeatable, one term |
| `-l`, `--list` | off | Print the signals of `--group` and exit |
| `--host` | `localhost` | Address of `litex_server` |
| `--port` | `1234` | Port of `litex_server` |
| `--csv` | `analyzer.csv` | Analyzer description written by the build |
| `--csr-csv` | `csr.csv` | Register map of the SoC |
| `--name` | `--csv` base name | Name of the analyzer in the SoC, prefix of its registers |
| `--group` | `0` | Group to capture |
| `--subsampling` | `1` | Keep one sample every N cycles |
| `--rle` | off | Enable run-length encoding |
| `--offset` | `32` | Pre-trigger samples |
| `--length` | the depth | Words to capture |
| `--dump` | `dump.vcd` | Output file; the extension picks the format |
| `--gui` | off | Open the GUI instead of a batch capture |
| `--timeout` | none | Give up after N seconds, exit code 2 |
| `--json` | off | Print one JSON object; errors exit 1 |

`--offset` and `--length` accept any Python integer literal, such as `256` or `0x100`. The driver
checks that the offset is smaller than the depth and than the length, and that the length is at
most the depth (`AssertionError`). The default offset of 32 therefore fails on an analyzer with a
depth of 32 or less, and with a `--length` of 32 or less: give `--offset` with them.

`--group` must be a group of `analyzer.csv`: with another number, `--list` and a capture stop with
`ValueError: Group N not in analyzer.csv.`. Take the group numbers from the `signal` rows of
`analyzer.csv`.

With `--rle`, `--length` counts stored words, not decoded samples; [Subsampler and run-length
encoding](#subsampler-rle) explains the difference. `--rle` on an analyzer built without RLE
stops with an error. `--subsampling` accepts 1 to `2**subsampler_width`, which is 65536 with the
default width.

The analyzer name is `--name`, else the base name of the `--csv` file: `--csv build/analyzer.csv`
drives the registers `analyzer_*`. With a CSV file that does not carry the name of the analyzer in
the SoC, pass `--name`; otherwise the driver looks for registers that do not exist.

### Signal names {#host-cli-names}

Each signal given to `-r`, `-f` or `-v` is looked up once among the signals of `--group`. An
exact name is used as is, and the CLI prints `Exact:` with the name. Otherwise the argument is a
Python regular expression: the signal with the longest matching text wins, a tie stops with
`Found multiple candidates`, and a name that matches no signal stops with `No signal matching`,
followed by the name and the signals of the group. Run `litescope_cli --list --group N` first and
copy the full names.

### Trigger terms {#host-cli-triggers}

The CLI builds a [sequence](#trigger) from its options, in a fixed order that does not depend on
their order on the command line:

1. two terms per `-r`: the signal at 0, then at 1;
2. two terms per `-f`: the signal at 1, then at 0;
3. one term for all the `-v` options together, which must all match on the same sample.

Each term must match after the previous one, so `-r a -v b 0x10` fires on the first sample with
`b` equal to `0x10` after a rising edge of `a`. There is no OR between options. Without any
trigger option, the CLI prints `No trigger, immediate capture.` and captures at once.

An edge on a signal wider than one bit compares the whole signal: `-r count` waits for `count`
at 0, then for `count` at 1, not for any increase. The values of `-v` are strings, parsed as
follows.

| Value | Meaning | Example |
|--------------|---------------------------------------------|-----------------------------|
| `0b...` | Binary; `x` is a don't care bit | `0b1x0`: bits 2 and 0 only |
| `0x...` | Hexadecimal; `x` is a don't care nibble | `0x1x`: bits 7 to 4 only |
| other | Any Python integer literal | `16`, `0o20` |

The driver cuts the mask and the value of a term to the bits of the signal: the bits of a value
wider than the signal are ignored. A plain integer value compares every bit of the signal.

### What the CLI prints {#host-cli-output}

Without `--json`, the driver logs each step with the analyzer name as a prefix, after the trigger
lines of the CLI. The lines follow the steps of the figure above.

| Line | Step |
|------------------------------------------|-----------------------------------------------|
| `Rising edge:`, `Condition:` | Trigger terms, with the full signal names |
| `run (offset=..., length=...)` | Terms loaded, storage and trigger armed |
| `wait_done (delay=0.2s)` | Polling of `storage_done` every 0.2 s |
| `upload (words=...)` | Words to read back: the length of the run |
| progress bar | Upload in bursts |
| `write dump.vcd` | Dump written |

The `upload (words=...)` count is the length of the run, `--length` or the depth;
[Upload](#stor-upload) describes the read path.

### Scripts and agents: `--json` and `--timeout` {#host-cli-json}

`--json` prints one JSON object on the standard output and no progress lines, so a script or an
agent can parse the result. The warning of the driver about a signal present in several groups at
different positions goes to the standard error. `--timeout` bounds the wait for the trigger;
without it, the CLI waits forever. The exit codes are listed below.

| Exit code | Meaning | JSON object |
|-----------|----------------------------------|------------------------------------------------|
| 0 | Dump written, or signals listed | `triggered: true`, `dump`, `samples`, `offset` |
| 1 | Error: command line, file, connection, value, read timeout | `{"schema": 1, "error": "..."}` |
| 2 | No trigger within `--timeout` | `triggered: false` |

With `--json`, a command-line error, such as an unknown option or a missing argument, is also an
error object, `{"schema": 1, "error": "ArgumentError: ..."}`, with exit code 1: code 2 always
means a timeout. Without `--json`, the argument parser prints the usage on the standard error and
exits with code 2, the code of a timeout too ([Known issues](#debug-known)).

Listing needs only `analyzer.csv`, not a running SoC, and with `--json` each signal comes with
its width. With the `analyzer.csv` of [the example of Capture files](#fmt-analyzer-csv), whose
group 1 holds one 4-bit slice, the command and its output are:

```console
$ litescope_cli --list --group 1 --json
{"schema": 1, "group": 1, "signals": [{"name": "count_7_4", "width": 4}]}
```

Errors keep the same shape. With no `litex_server` on the given port, a capture prints:

```console
$ litescope_cli --json --port 1299 -r flag
{"schema": 1, "error": "ConnectionRefusedError: [Errno 111] Connection refused"}
```

A capture that ends with code 2 leaves the analyzer armed. The next run of the CLI or of the
driver disarms it and loads its own terms, so no cleanup is needed.

## The GUI {#host-gui}

`litescope_cli --gui` opens a small window built with dearpygui, a package that is not
installed with LiteScope (`pip3 install dearpygui`). Its [status](#intro-status) is given in the
introduction. The connection options, `--csv`, `--name`, `--group`, `--subsampling`, `--offset`,
`--length`, `--rle` and `--dump` give the defaults of its fields.

| Field | Default | Note |
|-----------------|-----------------|----------------------------------------|
| Offset | `--offset` | Pre-trigger samples |
| Length | `--length` | Empty for the depth |
| Group | `--group` | Read-only |
| Subsampling | `--subsampling` | Keep one sample every N cycles |
| RLE | `--rle` | Checkbox |
| Dump | `--dump` | Output file |
| One per signal | `0bx` | Value of that signal in the trigger term |

The trigger window has one field per signal of the `--group` group, built when the window opens,
which is why the Group field is read-only. All the fields form a single value term, and `0bx`
leaves a signal out. Edges and sequences are not available. Run waits for the trigger with no
timeout.

## The Python driver {#host-driver}

The driver, `LiteScopeAnalyzerDriver`, is what the CLI, the GUI and `litex_mcp` use. Scripts use
it directly to arm several captures in a row, cause an event between arming and waiting, or
decode the samples without writing a file.

```python
LiteScopeAnalyzerDriver(regs, name, config_csv=None, debug=False)
```

`regs` is `bus.regs` of a `RemoteClient`. `name` is the analyzer name in the SoC, the prefix of
its registers, and `config_csv` defaults to `name + ".csv"`. With `debug=True`, the driver prints
the lines of [What the CLI prints](#host-cli-output).

Creating the driver writes 0 to the trigger and RLE enables, and the trigger flushes its terms.
It leaves `storage_enable` as it is, so a capture that waits to be uploaded stays in the memory.
`run()` and `clear()` write `storage_enable`. The ambiguity warning of [Scripts and
agents](#host-cli-json) is printed on the standard error when the driver is created.

### Methods {#host-driver-methods}

| Method | Effect |
|------------------------------------------|-------------------------------------------|
| `configure_group(n)` | Select group `n` |
| `add_trigger(value, mask, cond)` | Append one term |
| `add_rising_edge_trigger(name)` | Append two terms: 0, then 1 |
| `add_falling_edge_trigger(name)` | Append two terms: 1, then 0 |
| `configure_trigger(...)` | Same as `add_trigger` |
| `configure_subsampler(n)` | Keep one sample in `n`; writes `n - 1` |
| `configure_rle(enable)` | Enable RLE; error if the build has none |
| `run(offset, length)` | Load the terms, arm storage and trigger |
| `done()` | Read `storage_done` once |
| `wait_done(delay)` | Poll `done()` every `delay` s, no timeout |
| `upload(max_samples)` | Read the words, decode RLE, return samples |
| `save(filename, ...)` | Write a dump; the extension picks the format |
| `get_instant_value(group, name)` | One-sample capture of one signal |
| `clear()` | Drop terms and samples, disarm |

`add_trigger` takes either a raw `value` and `mask` over the whole sample, or `cond`, a
dictionary of signal names and value strings parsed as in [Trigger terms](#host-cli-triggers).
Names in `cond` are exact; the regular expression lookup is a CLI feature. Positions are
resolved in the group selected when the term is added, so call `configure_group()` first. A name
that is not in the selected group raises `ValueError`, with the signals of that group, even when
another group has it; the edge methods check the name the same way.

`configure_group(n)` raises `ValueError` for a group that `analyzer.csv` does not list.

The driver keeps the terms in a list. Every `run()` disarms the trigger, waits until the
gateware has flushed its term memory, then loads all the terms again. A script can therefore call
`run()` again without adding the terms again; `clear()` drops them. More terms than the term
memory holds (`trigger_depth + 1`, 17 by default) stop `run()` with `Trigger memory full`.

`run()` defaults to an offset of 0 and a length equal to the depth, and asserts that the offset
is below the depth and the length. `save(filename, samplerate=None, flatten=False)` without a
sample rate divides the rate of `analyzer.csv` by the subsampling factor recorded by
`configure_subsampler()`, 1 when that method was never called. [Capture files](#file-formats)
describes `samplerate` and `flatten`.

### A scripted capture {#host-driver-script}

The script below captures one rising edge of `flag` with 32 samples before it and writes a VCD
file. It expects `litex_server` on `localhost:1234` and the two files of the build in the current
directory.

```python
from litex import RemoteClient
from litescope import LiteScopeAnalyzerDriver

bus = RemoteClient(csr_csv="csr.csv", raise_on_timeout=True)
bus.open()

analyzer = LiteScopeAnalyzerDriver(bus.regs, "analyzer",
    config_csv="analyzer.csv", debug=True)
analyzer.configure_group(0)
analyzer.configure_subsampler(1)
analyzer.add_rising_edge_trigger("flag")
analyzer.run(offset=32, length=256)
analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

bus.close()
```

### Re-arming until the event happens {#host-driver-rearm}

An event that happens rarely, or only after a stimulus, calls for a loop: arm, cause the event,
wait a bounded time, try again. The USB3-PIPE bench script `usb3_analyzer.py` captures link
training this way, holding the PHY in reset while it arms. The pattern is below.

```python
import time

for attempt in range(10):
    analyzer.run(offset=32, length=256)
    analyzer.done()  # A read: the arming writes are done.
    cause_event()    # Your stimulus: a register write, a reset release.
    t0 = time.time()
    while not analyzer.done() and (time.time() - t0) < 1.0:
        time.sleep(0.05)
    if analyzer.done():
        break
else:
    raise RuntimeError("No trigger")

samples = list(analyzer.upload())
```

### Reading samples in Python {#host-driver-samples}

`upload()` returns a `DumpData`, a Python list with one integer per sample and the first probe
of the group in the least significant bits. Indexing it with an integer does not return a
sample: `data[i]` returns bit `i` of every sample, and `data[lo:hi]` the bits `lo` to `hi - 1` of
every sample. Iterate over it, or convert it with `list()`, to work sample by sample.

```python
data  = analyzer.upload()
count = data[0:8]      # Bits 7 to 0 of every sample, one integer per sample.
first = list(data)[0]  # The first sample, all probes.
```

The bit positions of the signals follow the `signal` rows of `analyzer.csv`, in order, from bit
0 ([Capture files](#fmt-analyzer-csv)). `upload(max_samples=n)` keeps the first `n` samples
after RLE decoding.

### One-sample reads {#host-driver-instant}

`get_instant_value(group, name)` reads the present value of one signal: it clears the terms,
captures one sample with no trigger and returns the bits of that signal. It also turns the driver
logs off for the rest of the session.

The capture has a length of 1 and goes through the whole capture flow: the flush of the storage,
then the upload over the bridge. A register of the design, or the [IO probe](#io-probe), reads a
static value with one register access.

### The IO probe driver {#host-io-driver}

`LiteScopeIODriver(regs, name)` drives the [IO probe](#io-probe). `write(value)` writes the
`<name>_out` register and `read()` returns `<name>_in`; there is nothing to configure.

## `litex_mcp` {#host-mcp}

`litex_mcp` of LiteX exposes the analyzer to agents as two MCP tools built on the same driver.
They reach the SoC through `litex_server`, like the CLI, with read timeouts raised as errors.

| Tool | Arguments | Returns |
|-------------------------------|-----------------------------|-----------------------------------|
| `litex_scope_list` | `analyzer_csv` | Depth, sample rate, groups, signals |
| `litex_scope_capture` | `analyzer_csv`, group, triggers, offset, length, subsampling, timeout, signals, max_changes | Per signal: value at trigger, changes; VCD path |

Triggers are a list of `{"signal", "type", "value"}` objects with the types `rising`, `falling`
and `value`; value triggers form one term, as in the CLI. The analyzer name is fixed to
`analyzer`, and a length of 0 means the depth. `signals` limits the answer to some signals and `max_changes` (32) the changes
listed per signal, which keeps the answer short on a wide sample. The value at trigger is read at
sample `offset`, the trigger sample ([Trigger position in the capture](#trig-position)).

## In the code {#host-code}

| Item | File |
|---------------------------------|--------------------------------------------------|
| `litescope_cli`, `Finder` | `litescope/software/litescope_cli.py` |
| `LiteScopeAnalyzerDriver` | `litescope/software/driver/analyzer.py` |
| `LiteScopeIODriver` | `litescope/software/driver/io.py` |
| `DumpData` | `litescope/software/dump/common.py` |
| `RemoteClient` | `litex/tools/litex_client.py` (LiteX) |
| `litex_server` | `litex/tools/litex_server.py` (LiteX) |
| `litex_scope_*` tools | `litex/tools/litex_mcp.py` (LiteX) |

Where to go next: [Capture files](#file-formats) for what `save()` writes, [Trigger](#trigger)
for how the terms are matched, [Debugging LiteScope itself](#debugging) when a capture does not
trigger.
