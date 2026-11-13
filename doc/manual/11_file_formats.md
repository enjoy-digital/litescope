# Capture files {#file-formats}

This chapter describes the files around a capture: `analyzer.csv`, which the build writes and the
host tools read, and the dumps that the driver writes after an upload, in VCD, sigrok, CSV, JSON
and Python formats. It gives the layout of each file as the code writes it, so that a script can
post-process a capture and a reader can tell what the viewer shows.

## At a glance {#fmt-glance}

| File | Written by | Read by | Content |
|---------------------|------------------------------|-----------------------|---------------------|
| `analyzer.csv` | `LiteScopeAnalyzer` | driver, CLI, `litex_mcp` | Parameters, signals, enums |
| `.vcd` | `save()`, `VCDDump` | GTKWave, PulseView | Waveform |
| `.gtkw`, `.txt` | `save()`, with enums | GTKWave | Trace list, state names |
| `.sr` | `save()`, `SigrokDump` | PulseView, `SigrokDump` | sigrok session |
| `.csv` | `save()`, `CSVDump` | spreadsheets, scripts | Binary values per time step |
| `.json`, `.py` | `JSONDump`, `PythonDump` | scripts | Lists of integers |

`save()` of the driver picks the format from the extension of the file name, and `litescope_cli`
passes `--dump` to it; any other extension stops with `NotImplementedError`. Only the sigrok
writer can read its files back.

## `analyzer.csv` {#fmt-analyzer-csv}

`analyzer.csv` tells the host what the gateware captures: the parameters of the analyzer, then
the probes of every group with their widths. `LiteScopeAnalyzer` writes it when the LiteX build
returns: after the vendor tools on a board, at once with `--no-compile`, and not at all when the
toolchain fails. With `litex_sim`, it is written when the simulation exits; build with `--no-compile` first to get it ([Getting
started](#getting-started)).

The file name and directory come from the `csr_csv` parameter of `LiteScopeAnalyzer`, which
defaults to `analyzer.csv` in the current directory; `None` writes no file. The rows have no
header, and each row starts with its kind.

| Row | Fields | Meaning |
|---------|--------------------------------------------------------|---------------------------|
| `config` | `config,None,<key>,<value>` | One parameter of the analyzer |
| `signal` | `signal,<group>,<name>,<width>` | One probe of a group, from bit 0 up |
| `enum` | `enum,<group>,<name>,<value>,<label>` | One state name of an FSM probe |

The `config` keys are `data_width`, `storage_width`, `depth`, `samplerate`, `subsampler_width`,
`with_rle` and `rle_length`, all integers. The `signal` rows of a group are in the order of the
bits: the first row is bit 0 of the sample. The names are the names of the signals in the
generated Verilog, so they change with the hierarchy of the design.

The file below comes from an analyzer with two groups: group 0 holds an 8-bit counter `count` and
a 1-bit `flag`, group 1 the slice `count[4:8]`. It was built with `depth=1024`,
`samplerate=100e6` and `with_rle=True`.

```text
config,None,data_width,9
config,None,storage_width,10
config,None,depth,1024
config,None,samplerate,100000000
config,None,subsampler_width,16
config,None,with_rle,1
config,None,rle_length,256
signal,0,count,8
signal,0,flag,1
signal,1,count_7_4,4
```

`data_width` is the width of the widest group, and `storage_width` adds the marker bit of run-length
encoding (RLE) ([Subsampler and run-length encoding](#subsampler-rle)). An FSM given as a probe adds
one `enum` row per state after its `signal` row, for example `enum,0,fsm_state,1,RUN`.

`samplerate` is the `samplerate` parameter of `LiteScopeAnalyzer`, an integer number of samples
per second. It has no effect on the gateware: only the dumps use it, for their time scale. Its
default is `1e12`, a placeholder that gives wrong time scales ([VCD](#fmt-vcd)); give the
frequency of the analyzer clock domain when building.

The driver accepts a file without the `storage_width`, `subsampler_width`, `with_rle` or
`rle_length` rows, as older builds wrote it: it then assumes no RLE, a storage width equal to the
data width and a 16-bit subsampler. Rebuild the SoC whenever its probes change; a stale
`analyzer.csv` decodes the samples with the wrong bit positions.

## What every dump contains {#fmt-common}

All the dump formats start from the same list of variables, built by `save()`:

1. one variable per probe of the selected group, cut from the samples by the bit positions of
   `analyzer.csv`;
2. `scope_clk`, a generated clock;
3. `scope_trig`, a generated trigger marker.

Every uploaded sample is written twice, as two time steps. `scope_clk` is 1 on the first step of
each sample and 0 on the second, so a viewer shows one clock period per sample. The figure below
shows four samples of the example of the next sections.

![Sample doubling in the dumps. Each uploaded sample takes two time steps; scope_clk is high on
the first one. scope_trig rises at time step 2 x offset, here 4, which is sample 2, the trigger
sample.](fmt_vcd.svg)

`scope_trig` is 0 for the first `2 x offset` time steps and 1 after, where `offset` is the
pre-trigger length given to `run()`. The marker thus rises at sample `offset`, the trigger sample
([Trigger position in the capture](#trig-position)). With the CLI default `--offset 32`, it rises
at sample 32. In a dump with `offset` samples or fewer, such as an upload cut by `max_samples`, the
marker stays at 0 and adds no time step.

The time scale comes from the `samplerate` of `analyzer.csv`, divided by the subsampling factor.
`save(filename, samplerate=...)` replaces this value, and is used as given, without the
division: pass the rate of the stored samples. The CLI has no option for it.

## VCD {#fmt-vcd}

The VCD writer, `VCDDump`, produces a text Value Change Dump that GTKWave and PulseView open. The
excerpts below come from the dump writers run on four hand-made samples of the probes `flag` (1
bit) and `count` (3 bits), with an offset of 2 and a sample rate of 100 MHz:

```python
from litescope.software.dump import *

data = DumpData(4)
data.extend([0b0000, 0b0011, 0b0100, 0b0111])  # flag in bit 0, count in bits 3..1
for dump, name in [(VCDDump(samplerate=100e6), "dump.vcd"), (CSVDump(), "dump.csv"),
                   (JSONDump(), "dump.json"), (PythonDump(), "dump.py"),
                   (SigrokDump(samplerate=100e6), "dump.sr")]:
    dump.add_from_layout([("flag", 1), ("count", 3)], data)
    dump.add_scope_clk()
    dump.add_scope_trig(2)
    dump.write(name)
```

The VCD file starts with a `$date` block (the local time of the write), then the time scale, one
`$var wire` per variable in a `top` module, and initial `x` values. Value changes follow, one
`#n` block per time step that changes something. Every value is written as a binary vector, even
for 1-bit variables.

```text
$date
[...]
$end
$timescale 5000ps $end
$scope module top $end
$var wire 1 ! flag $end
$var wire 3 " count $end
$var wire 1 # scope_clk $end
$var wire 1 $ scope_trig $end
$upscope  $end
$enddefinitions  $end
$dumpvars
bx !
bxxx "
bx #
bx $
$end
#0
b0 !
b000 "
b1 #
b0 $
#1
b0 #
#2
b1 !
b001 "
b1 #
#3
b0 #
#4
b0 !
b010 "
b1 #
b1 $
[...]
```

### Time scale {#fmt-vcd-timescale}

The time steps `#n` are numbered 0, 1, 2 and so on, and `$timescale` gives the duration of one
step: half a sample period, rounded down to an integer number of picoseconds,
`int(1e12 / (2 * samplerate))`, with the sample rate after subsampling. When that number is below
100, the writer counts in femtoseconds instead, so that the rounding stays small.

| Sample rate | `$timescale` | Note |
|-------------------|---------------|----------------------------------------------|
| 1 MHz | `500000ps` | Exact; the rate of `litex_sim --with-analyzer` |
| 100 MHz | `5000ps` | Exact |
| 125 MHz | `4000ps` | Exact |
| 150 MHz | `3333ps` | Rounded down: the time axis runs about 0.01 % short |
| `1e12` (default) | `500fs` | Placeholder rate: 1 ps per sample |

The `500fs` case is the one of an analyzer built without `samplerate`. The order of the values is
right; only the time axis is wrong. Pass the real rate with `save(filename, samplerate=...)` from
a script, or build the analyzer with `samplerate` set.

### FSM states in GTKWave {#fmt-vcd-enums}

A probe with `enum` rows in `analyzer.csv` gets two variables in the VCD: the state number under
its name, and `<name>_text`, a vector that holds the state name as ASCII characters, 8 bits per
character. A viewer that shows a vector as ASCII text then shows the state names without any
setup.

For GTKWave, `save()` also writes two kinds of side files next to the VCD, only for a group with
an enum and without `flatten`:

- `<dump>_<name>.txt`, a translate filter with one `<value> <label>` line per state;
- `<dump>.gtkw`, a save file that lists every trace and attaches the filter to the state number.
  It lists the `_text` variable with the ASCII data format (`@820`), so GTKWave shows the state
  names on it too.

For a 3-bit `state` probe with the states `IDLE`, `RUN` and `DONE`, saved as `enum.vcd`, the two
files are:

```text
$ cat enum_state.txt
0 IDLE
1 RUN
2 DONE
$ cat enum.gtkw
[*] Auto-Generated by LiteScope
[dumpfile] "enum.vcd"
@22
top.flag
@2022
^1 enum_state.txt
top.state[2:0]
@820
top.state_text[31:0]
@22
top.scope_clk
@22
top.scope_trig
```

Open the save file, `gtkwave enum.gtkw`, rather than the VCD, to get the traces and the state
numbers with their names at once. The paths in the save file are the ones given to `save()`, so open it from the
same directory. The VCD writer cannot read a VCD file back.

## sigrok session {#fmt-sigrok}

A `.sr` file is a sigrok session, the native format of PulseView. It is a zip archive of three
files:

| Member | Content |
|-------------|-------------------------------------------------------------------|
| `version` | `1` |
| `metadata` | Sample rate, probe count, unit size, one name per probe |
| `logic-1-1` | Samples, one little-endian unit of `unitsize` bytes per time step |

sigrok handles only 1-bit probes, so every bit of every variable becomes one probe named
`<name>[<bit>]`, a 1-bit variable keeping its name. The probes are numbered from bit 0 of the
first variable, which is also bit 0 of each unit. The probe count is rounded up to a multiple of
8. The metadata of the example above is:

```text
[global]
sigrok version=0.3.0
[device 1]
capturefile=logic-1-1
total probes=8
samplerate=200 MHz
unitsize=1
probe1=flag
probe2=count[0]
probe3=count[1]
probe4=count[2]
probe5=scope_clk
probe6=scope_trig
```

The sample rate written is twice the sample rate, as the time steps are doubled. It is written in
the largest unit, GHz, MHz, kHz or Hz, that gives a whole number, without rounding: 1 MHz
samples give `2 MHz`, 300 kHz samples give `600 kHz`. Multi-bit values appear in PulseView as
separate bits; group them in the viewer.

The writer builds the archive in a temporary directory, so nothing next to the `.sr` file is
created or deleted. `SigrokDump().read(filename)` reads a session back, through a temporary
directory too, into a list of 1-bit variables, one per probe, and takes the sample rate from the
metadata (`Hz`, `kHz`, `MHz` or `GHz`).

## CSV, JSON and Python {#fmt-text}

These three formats hold the same values as the VCD for scripts, one value per time step: every
sample appears twice, and `scope_clk` and `scope_trig` are included. None of them writes the
time scale or the state names, and none of them can be read back by LiteScope.

The CSV file has a row of variable names, a row of widths, then one row per time step with every
value in binary, padded to its width. The fields are separated by one comma, with no separator at
the end of a row. The first lines of the example are:

```text
flag,count,scope_clk,scope_trig
1,3,1,1
0,000,1,0
0,000,0,0
1,001,1,0
```

The JSON file is one object that maps each variable name to its list of integers. The Python
file holds the same data as a dictionary named `dump`, ready to `exec()` or import.

```text
{"flag": [0, 0, 1, 1, 0, 0, 1, 1], "count": [0, 0, 1, 1, 2, 2, 3, 3], [...]}
```

To work on samples rather than time steps, skip the dump: take the list returned by `upload()`
([Reading samples in Python](#host-driver-samples)), or keep every second value of a JSON list.

## Flattened dumps {#fmt-flatten}

`save(filename, flatten=True)` replaces each probe by a 1-bit variable that carries its bits one
after the other in time, bit 0 first. A probe of width `w` takes `w` time steps per sample, and
the samples are not doubled. `scope_clk` follows the longest variable, and `scope_trig` rises at
time step `2 x offset`, which in this mode is not a sample boundary of a probe wider than one
bit.

The result is a serial view of each probe. Probes of different widths no longer line up in time,
and no `.gtkw` or filter file is written. The CLI never sets this option.

## In the code {#fmt-code}

| Item | File |
|--------------------------------|-------------------------------------------------------|
| `export_csv()`, `do_exit()` | `litescope/core.py`: writes `analyzer.csv` |
| `get_config()`, `get_layouts()` | `litescope/software/driver/analyzer.py` |
| `save()`, `write_gtkw_filters()` | `litescope/software/driver/analyzer.py` |
| `Dump`, `DumpData`, `DumpVariable` | `litescope/software/dump/common.py` |
| `VCDDump` | `litescope/software/dump/vcd.py` |
| `SigrokDump` | `litescope/software/dump/sigrok.py` |
| `CSVDump`, `JSONDump`, `PythonDump` | `csv.py`, `json.py`, `python.py` of the dump package |

Where to go next: [Host tools](#host-tools) for the driver and the CLI that write these files,
[Getting started](#getting-started) for a capture opened in GTKWave, [Debugging LiteScope
itself](#debugging) for a wrong time scale or a missing `analyzer.csv`.
