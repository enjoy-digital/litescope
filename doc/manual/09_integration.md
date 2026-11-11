# Adding LiteScope to a SoC {#integration}

This chapter adds an analyzer to a LiteX SoC of your own: the code in the target, the probes
and groups, the depth, the clock domain, the files for the host and the bridge. It is for the
designer of a target; [Getting started](#getting-started) runs the flow on a SoC that already has
an analyzer.

## At a glance {#integ-glance}

| Item | Value |
|---------------------------|------------------------------------------------------------------|
| Class | `LiteScopeAnalyzer` of `litescope/core.py` |
| Added as | An attribute of the SoC; its name is the prefix of its registers |
| LiteX helper | None: the analyzer is a plain submodule |
| Needs | A bridge on the SoC bus, and `litex_server` on the host |
| Files for the host | `analyzer.csv` (the analyzer), `csr.csv` (the register map) |
| Clock | One domain per analyzer, `clock_domain`, `sys` by default |
| Cost | `depth` words of the sample width in block RAM, and a comparator on the probes |

## The analyzer in a target {#integ-target}

An integration has three parts, shown in the figure below. The analyzer takes probes from the
design, its registers join the bus of the SoC, and a bridge gives the host access to that bus.
The build writes two files that the host tools read: `analyzer.csv` describes the probes, and
`csr.csv` gives the addresses of the registers.

![LiteScope in a SoC. The probes (cyan arrow) go from the design to the analyzer; the host
reaches the registers of the analyzer through the bridge and litex_server, and the CLI reads the
two files of the build to name the probes and find the registers.](integ_soc.svg)

The example below adds an analyzer to the `__init__` of a target, behind a switch. `self.dut`
stands for your design: a module with a state machine, an output stream and two status signals.

```python
from litescope import LiteScopeAnalyzer

if with_analyzer:
    analyzer_groups = {
        # Group 0: the state machine and the output stream.
        0: [
            self.dut.fsm,
            self.dut.source.valid,
            self.dut.source.ready,
            self.dut.source.data,
        ],
        # Group 1: status.
        1: [
            self.dut.count,
            self.dut.error,
        ],
    }
    self.analyzer = LiteScopeAnalyzer(analyzer_groups,
        depth        = 512,
        clock_domain = "sys",
        samplerate   = sys_clk_freq,
        csr_csv      = "analyzer.csv",
    )
```

No call to a LiteX helper is needed. The SoC collects the registers of the analyzer like those of
any other module and names them after the attribute: `self.analyzer` gives `analyzer_mux_value`,
`analyzer_trigger_enable` and so on ([Register reference](#registers)). Some targets also call
`self.add_csr("analyzer")`, which is not needed.

The host tools find the analyzer by that name. `litescope_cli` takes it from the file name of
`--csv`, so keep the file name equal to the attribute name: `analyzer.csv` for `self.analyzer`
([Host tools](#host-tools)). [Parameters and options](#opt-analyzer) lists every parameter.

## Choosing the probes {#integ-probes}

A probe can be a signal, a record, a state machine or an expression. The table below gives what
the analyzer does with each kind.

| Probe | What the analyzer stores |
|----------------------------|------------------------------------------------------------------|
| `Signal` | The signal, under its name in the design |
| `Record` (a stream, a bus) | Every field, as separate probes |
| `FSM` | The state signal, with the names of the states for the viewers |
| Slice, `Cat`, operator | A new signal driven by the expression: `count_7_4` for `count[4:8]`, `expr` otherwise |

A state machine is the most useful probe of a design: one probe gives the state, and the dumps
show the state names. The analyzer finalizes the state machine when it is created, so create the
analyzer after the last state of the machine is defined.

A record is convenient, but it brings all its fields: a stream endpoint adds `first`, `last` and
its parameters to the data and the handshake. Probe the fields you need instead, as the example
does, to keep the sample narrow. A signal that appears twice in a group is stored once; two
identical expressions are stored twice.

The names in `analyzer.csv` are the names of the signals in the generated Verilog, which come from
the hierarchy of the design. They change when the design changes, so take them from
`litescope_cli --list` after each build. A signal created with `name=` keeps that name when no
other signal uses it, which helps for signals you trigger on often. Only a slice of a named
signal is named after it; `Cat`, operators and slices of expressions are named `expr`.

## Groups {#integ-groups}

A group is one list of probes. The analyzer has several groups and captures one at a time,
chosen at run time with `--group` or `configure_group()`, without a new build. A list, or a single
signal, is group 0.

The figure below shows the groups of the example. Each group is the concatenation of its probes,
the first probe in the low bits. The widest group sets the width of the sample, and the narrower
groups are padded with zeros.

![Probe groups of the example. Each group is laid out from bit 0, first probe first; group 1 is
padded with zeros to the width of group 0, and the mux_value register selects the group that the
trigger and the storage see.](integ_groups.svg)

Groups trade time for width. With a group per subsystem, the sample, the block RAM and the
comparator have the size of the widest group, not of all groups together. Two groups are never
captured together, so put the signals that must be seen on the same cycle in the same group.
[Probe groups](#arch-groups) gives the details.

## Depth and width {#integ-sizing}

The sample memory holds `depth` words of the sample width: `depth` times the width of the widest
group, in block RAM. The time a capture covers is `depth` samples of the scope clock, multiplied
by the subsampling factor. [Performance and resources](#performance) gives the memories of the
analyzer and the time window in detail.

- Start narrow and short. A few hundred samples of the signals that answer one question are
  usually enough, and a narrow analyzer is easy to fit and to time.
- Widen the window in time with subsampling (`--subsampling`), which costs nothing at build
  time, or with run-length encoding (`with_rle=True`), which adds a marker bit to the stored
  word and widens words narrower than the run counter ([Subsampler and run-length
  encoding](#subsampler-rle)).
- `depth` is fixed by the build. The capture length and the pre-trigger window are chosen at run
  time, up to the depth ([Choosing depth, offset and length](#stor-sizing)).

## Clock domain and sample rate {#integ-clocks}

The analyzer samples its probes on the clock of `clock_domain`. Set it to the domain where the
probes live: the probe path has no synchronizer, so a probe from another domain can give wrong
values. Probes from two domains need two analyzers, or a synchronizer that brings one signal
into the domain of the other.

The registers stay in `sys`, and the analyzer crosses its control and its read-back between the
two domains ([Clock domains](#arch-clocks)). `samplerate` must be the frequency of
`clock_domain`, not of `sys` when the two differ. It sets the time axis of the dumps only; a
wrong value does not change the capture ([Wrong time scale](#debug-timescale)).

Prefer the `sys` domain when the signals allow it. In a fast domain, such as the clock of a
transceiver, the comparator and the memory of the analyzer must meet the timing of that clock.
Keep such an analyzer narrow, well below 128 bits, and use `register=True`, which adds one
register stage on the probes ([Register stage on the probes](#arch-register)).

## Files for the host {#integ-files}

The host tools need two files from the build, as the first figure of this chapter shows.

| File | Written by | Read for |
|------------------------|-------------------------------------|---------------------------------|
| `analyzer.csv` | The analyzer, when the build returns | Probe names, widths, groups, depth |
| `csr.csv` | The LiteX `Builder` (`--csr-csv`) | Register addresses |
| `build_info.json` | The LiteX `Builder`, in the output directory | Path of `analyzer.csv`, for scripts |

The analyzer writes `analyzer.csv` to the path given by `csr_csv`, relative to the directory the
build runs from, not to the output directory. Some targets, such as the USB3-PIPE bench SoC, join
it to the output directory instead, so that each build keeps its own file:

```python
# output_dir: the output directory of the Builder (--output-dir).
csr_csv = os.path.join(output_dir, "analyzer.csv")
```

The file is written when the build returns, after the vendor tools when they run, so a failed
toolchain run leaves no file. A build with `--no-compile` writes it in seconds, since it stops
after the elaboration ([Capture files](#fmt-analyzer-csv)). `build_info.json` records the
absolute path of the file of the first analyzer it finds in the SoC, under `files`,
`analyzer_csv`, when the file exists. `litescope_cli` does not read it (it takes `--csv`); the
build report of `litex_mcp` shows it, and scripts can use it.

## Adding a bridge {#integ-bridge}

The host reaches the registers through any bridge of the SoC. A SoC that already has one for
other debugging needs nothing more. The table below gives, for each bridge, the LiteX method that
adds it and the matching transport option of `litex_server`; the switches of the targets follow.

| Bridge | In the SoC | `litex_server` |
|--------------|------------------------------|--------------------------------------------|
| UARTBone | `add_uartbone()` | `--uart --uart-port <port>` |
| JTAGBone | `add_jtagbone()` | `--jtag` |
| Etherbone | `add_etherbone()` | `--udp` |
| PCIe | `add_pcie()` | `--pcie --pcie-bar <bar>` |

- **UARTBone** puts the bridge on the serial port. With the switch
  `--uart-name=crossover+uartbone`, the BIOS console moves to a crossover UART, which
  `litex_term crossover` reads through the bridge. `--uart-name=crossover --with-uartbone` gives
  the same result. UARTBone is slow, but it only needs the serial port of the board.
- **JTAGBone** uses the JTAG port of the FPGA, on the families whose platform supports it. The
  switch is `--with-jtagbone`, and `--jtagbone-chain` selects the user chain, 1 by default.
- **Etherbone** carries the accesses in UDP packets, port 1234, at the IP address of the target
  (192.168.1.50 by default). Many targets with an Ethernet port expose it as `--with-etherbone`.
  It uploads long captures much faster than a serial port.
- **PCIe** reaches the bus through a BAR of a LitePCIe endpoint, on boards in a PC; each PCIe
  target has its own switch.

Choose a bridge that does not travel on the link you observe: probing an Ethernet stream through
Etherbone changes the traffic you capture. [Starting litex_server](#host-server) gives the
options of each transport.

## Build switches and probe sets {#integ-switches}

The cores of the LiteX ecosystem follow one pattern that keeps the analyzer out of the normal
build. A target switch, usually `--with-analyzer`, adds the analyzer; the core under test provides
its probe lists, so that the target does not need to know its internals.

| Pattern | Example |
|-------------------------------|------------------------------------------------------------|
| Switch on the target | `--with-analyzer` in the LiteDRAM bench targets |
| Probe list of a core | `get_litescope_probes()` of the LiteX `FT245PHYSynchronous` |
| Probe groups of a core | `get_litescope_groups()` in the LiteX-Boards `adiuvo_forgix` target (`--with-demo-scope`) |
| Group chosen at build | `--analyzer-group` of the USB3-PIPE bench SoC |

A method of the core that returns the probe list keeps the list next to the code it observes.
The target passes the result to `LiteScopeAnalyzer` and adds its own signals if needed. The
`limesdr_mini_v2` target of LiteX-Boards does this with the USB FIFO PHY, in its `usb` domain; it
passes the `sys` frequency as `samplerate`, where the frequency of the probed domain belongs.

When a SoC has too many interesting signals for one analyzer, a build switch that picks one of
several named groups keeps each bitstream small. [Uses across the
ecosystem](#ex-ecosystem) describes these targets and what their captures show.

## Several analyzers {#integ-several}

A SoC can hold several analyzers, for example one per clock domain. Give each one its own
attribute name and a file of the same name, then select it on the host with `--csv`:

```python
self.analyzer_rx = LiteScopeAnalyzer(rx_probes, depth=512, clock_domain="rx",
    samplerate=rx_clk_freq, csr_csv="analyzer_rx.csv")
self.analyzer_tx = LiteScopeAnalyzer(tx_probes, depth=512, clock_domain="tx",
    samplerate=tx_clk_freq, csr_csv="analyzer_tx.csv")
```

```sh
litescope_cli --csv analyzer_rx.csv --list
```

The analyzers are independent: each has its own trigger and memory, and there is no trigger
shared between them. `build_info.json` records the file of one analyzer only.

## Outside LiteX {#integ-outside}

The analyzer is a LiteX module and is built as part of a LiteX design. The repository has no
generator that turns it into a standalone Verilog core with its own bus interface, so a design
outside LiteX cannot instantiate it directly.

## Where to go next {#integ-next}

[Host tools](#host-tools) to capture from the host, [Examples and uses in the
ecosystem](#examples) for complete targets, [Debugging LiteScope itself](#debugging) when a
capture does not behave.
