```{=latex}
\mainmatter
\part{Understand}
```

```{=html}
<h1 class="part">Part I. Understand</h1>
```

# Introduction {#introduction}

This chapter says what LiteScope is, why it exists, what it does and what it does not do. It gives
the status of each feature, the projects that use it, the layout of the repository and a map of
the manual. Every reader should start here.

## What LiteScope is {#intro-what}

LiteScope is a logic analyzer that lives inside the FPGA. It samples internal signals of a running
design, the *probes*, into block RAM, starting from a condition the user chooses, the *trigger*.
The host then reads the samples back and writes them to a waveform file that GTKWave or PulseView
opens.

The project has four parts, shown in the figure below. The analyzer (`LiteScopeAnalyzer`) is the
gateware that captures. The IO probe (`LiteScopeIO`) reads and drives static signals through
registers. On the host, the driver and the CLI arm the analyzer, upload the samples and write the
dump files.

![LiteScope at a glance: the analyzer samples probes of the design under test; the host reads its
registers through a bridge of the SoC and `litex_server`, and the CLI or the driver writes a dump
file for a waveform viewer.](intro_overview.svg)

The analyzer is a LiteX module written in Migen. It is added to a LiteX SoC as a submodule, and
its registers appear on the SoC bus like those of any other core. The host reaches them through
the bridge the SoC already has for debugging: UART, JTAG, Ethernet or PCIe, served on the host by
`litex_server`.

## Why an embedded analyzer {#intro-why}

An embedded analyzer sees the nets inside the FPGA, at the cost of some block RAM and logic;
[External and embedded analyzers](#primer-embedded) compares it with a bench analyzer and with the
vendor tools. LiteScope works over any bridge of the SoC, including Ethernet and PCIe, and every
step is a Python call or a command line, so captures can be scripted, repeated and run by an
automated test or an agent.

## Features at a glance {#intro-features}

| Area | Features |
|------------------|--------------------------------------------------------------------------|
| Probes | Any signals, records, slices, expressions and FSM states; several probe groups selected at run time |
| Trigger | Mask and value terms with don't care bits, sequences of terms, rising and falling edges, immediate capture |
| Capture | Pre-trigger window, capture length up to the depth, subsampling, optional run-length encoding |
| Storage | Block RAM, `depth` words as wide as the widest group (at least one bit wider with run-length encoding) |
| Clocking | Probes sampled in one clock domain of the design; control and read-back on the bus clock |
| Host access | Any LiteX bridge served by `litex_server`: UART, JTAG, Ethernet, PCIe, USB, `/dev/mem` |
| Host tools | Python driver, `litescope_cli` (batch, `--json`, `--timeout`), GUI |
| Dump files | VCD (with GTKWave save file for FSM state names), sigrok, CSV, JSON, Python |
| IO probe | Static inputs and outputs read and written through registers |
| Verification | Migen unit simulations, driver, dump and CLI tests, example build, Verilator end-to-end capture with `litex_sim` |

## Status {#intro-status}

This is the one status table of the manual; other chapters link here. The table below gives the
status of each feature, with the tests of the repository that cover it.

| Feature | Status | Tests |
|------------------------------------|----------------|------------------------------------|
| Analyzer: probes, groups, storage, pre-trigger window | Supported | Migen simulations, Verilator |
| Trigger: terms, don't care bits, sequences, immediate capture | Supported | Migen simulations (one term, immediate capture), driver tests (parsing, sequences), Verilator |
| Edge triggers (built by the driver) | Supported | Driver tests, CLI tests |
| Subsampler | Supported | Migen simulations, driver tests |
| Driver, CLI batch mode, dump files | Supported | Driver, dump and CLI tests, Verilator |
| Run-length encoding (`with_rle`) | Known issues | Migen simulations, driver and dump tests, Verilator |
| IO probe (`LiteScopeIO`) | Available | None |
| `register` option of the analyzer | Available | None |
| GUI (`litescope_cli --gui`) | Experimental | None |

The status words mean:

- **Supported**: the main capture flow. The manual gives its behaviour as the reference, and the
  test suite covers it.
- **Available**: in the code and usable. The manual describes exactly what the code does, with
  no claim beyond it.
- **Known issues**: in the code and usable, with confirmed bugs on this revision that change the
  result of a capture. The chapter of the feature describes them as limitations, and [Known
  issues](#debug-known) lists them. The run-length encoder loses samples, and never completes a
  capture when subsampling is on ([Limitation](#rle-limitation)).
- **Experimental**: marked as unfinished in the code (`# FIXME`); its behaviour may change. The
  GUI has such marks on its default values.

The tests run in simulation; [Simulation and verification](#simulation) lists them. The supported
features have known issues too, such as the position of the trigger sample and the length of the
upload; [Known issues](#debug-known) lists every one of this revision.

## What it is not {#intro-limits}

LiteScope captures a bounded window into on-chip memory, then uploads it. It is not a streaming
analyzer: samples do not flow to the host or to DRAM during the capture, and the time window is
set by the depth, the clock and the subsampling factor.

The trigger compares samples with mask and value terms, matched one after the other. It has:

- no OR of terms, no counter of occurrences and no timeout in the gateware;
- no edge detector in the gateware: the driver builds an edge from two terms, as
  [Sequences and edges](#primer-sequence) explains;
- no external trigger input or output, and no trigger shared between two analyzers.

LiteScope does not decode protocols, does not inject or generate signals, and does not compress
beyond the optional run-length encoding. Protocol analyzers, signal injection and storage in DRAM
are listed as possible improvements in the README of the repository.

## Where it is used {#intro-users}

The analyzer is part of the debug flow of most cores of the LiteX ecosystem. The table below
lists the users found in the public repositories, one line each; [Examples and uses in the
ecosystem](#examples) describes the main ones.

| Project | Use |
|----------------|------------------------------------------------------------------------------|
| LiteX | `litex_sim --with-analyzer` (CPU bus probes, in simulation), `litex_mcp` capture tools |
| LiteDRAM | `--with-analyzer` in the bench targets, probes on the DFI interface |
| LiteSATA | `--with-analyzer` and per-module analyzers in the bench targets |
| LitePCIe | `--with-analyzer` in the soft PHY benches, lane 0 in the PIPE clock domain |
| LiteEth | Bench target with an analyzer |
| LiteICLink | Transceiver and SerWB benches |
| LiteSDCard | Bench targets |
| USB3-PIPE | Six probe lists of the PHY (`--analyzer-group`), scripted re-arm and decode |
| LiteX-Boards | Analyzers in a few board targets, in the system clock or another domain |

## Repository layout {#intro-layout}

| Path | Content |
|----------------------------------------|----------------------------------------------------|
| `litescope/core.py` | The gateware: `LiteScopeIO`, `LiteScopeAnalyzer` and its blocks |
| `litescope/software/driver/` | The driver (`analyzer.py`) and the IO probe driver (`io.py`) |
| `litescope/software/dump/` | Dump writers: VCD, sigrok, CSV, JSON, Python |
| `litescope/software/` | The CLI and its GUI (`litescope_cli.py`) |
| `examples/arty.py` | Arty A7 SoC with Etherbone and an analyzer |
| `test/` | Unit, driver, dump, CLI and Verilator tests (pytest) |
| `doc/` | This manual (`doc/manual/`), its figures (`doc/diagrams/`), the logos and the former architecture figure |

## License and credits {#intro-license}

LiteScope is released under the BSD 2-Clause license by Enjoy-Digital, and can be used in
closed-source designs. It is written in Python with Migen and LiteX. The contributors are listed
in the `CONTRIBUTORS` file and in the history of the repository.

## How to read this manual {#intro-reading}

The figure below shows the flow of a capture, from the build to the dump file. The chapters of
Part II follow the gateware along this flow, and Part III follows the user.

![Flow of a capture: the build writes `analyzer.csv` (probes and parameters) and `csr.csv`
(register addresses); the host then configures and arms the analyzer, waits for the trigger,
uploads the samples and saves a dump.](intro_flow.svg)

If embedded logic analysis is new to you, read [Embedded logic analysis in a
nutshell](#la-primer) next. Otherwise, the table below sends each question to its chapter.

| Question | Chapter |
|-----------------------------------------------|----------------------------------------|
| How does an embedded analyzer work? | [Embedded logic analysis in a nutshell](#la-primer) |
| How is the analyzer organised? | [Analyzer architecture](#analyzer-architecture) |
| How do terms and sequences match? | [Trigger](#trigger) |
| How are samples thinned and compressed? | [Subsampler and run-length encoding](#subsampler-rle) |
| How are samples stored and read back? | [Storage and read-back](#storage) |
| How do I read or drive a static signal? | [IO probe](#io-probe) |
| How do I run a first capture? | [Getting started](#getting-started) |
| How do I add an analyzer to my SoC? | [Adding LiteScope to a SoC](#integration) |
| How do I script captures? | [Host tools](#host-tools) |
| What is in a dump file? | [Capture files](#file-formats) |
| How do other cores use LiteScope? | [Examples and uses in the ecosystem](#examples) |
| How is LiteScope tested? | [Simulation and verification](#simulation) |
| My capture does not trigger: what now? | [Debugging LiteScope itself](#debugging) |
| Which register does what? | [Register reference](#registers) |
| What does this term mean? | [Glossary](#glossary) |
