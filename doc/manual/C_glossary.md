# Glossary {#glossary}

The terms of logic analysis and of LiteScope used in this manual, in alphabetical order. Each entry
points to the chapter that explains it.

| Term | Meaning |
|---------------------|----------------------------------------------------------------------------------|
| Analyzer | `LiteScopeAnalyzer`: the gateware that samples the probes, triggers and stores a capture. See [Analyzer architecture](#analyzer-architecture) |
| `analyzer.csv` | File written by the analyzer when the LiteX build returns: widths, depth, rate, probes per group, state names. See [Capture files](#file-formats) |
| Arm | Start a capture: load the terms, enable the storage, then the trigger (`run()` of the driver). See [Analyzer architecture](#analyzer-architecture) |
| AsyncFIFO | FIFO with its write and read sides in two clock domains; the analyzer uses one for the terms and one on the read path. See [Analyzer architecture](#analyzer-architecture) |
| Bridge | SoC block that turns a host link into bus accesses: UARTBone, JTAGBone, Etherbone, PCIe. See [Embedded logic analysis in a nutshell](#la-primer) |
| Capture | One run of the analyzer, from the arming to the upload. See [Getting started](#getting-started) |
| Capture length | Words stored by a capture (`length`), up to the depth. See [Storage and read-back](#storage) |
| CDC | Clock domain crossing: passing a signal from one clock domain to another. See [Analyzer architecture](#analyzer-architecture) |
| CLI | `litescope_cli`, the command-line capture tool. See [Host tools: CLI, driver and GUI](#host-tools) |
| Depth | Size of the sample memory in words, fixed at build time. See [Storage and read-back](#storage) |
| Don't care | A bit of a term that is not compared, written `x` in a value. See [Trigger](#trigger) |
| Driver | `LiteScopeAnalyzerDriver`, the Python class that configures, arms and reads the analyzer from the host. See [Host tools: CLI, driver and GUI](#host-tools) |
| Dump | File written by the driver from a capture: VCD, sigrok, CSV, JSON or Python. See [Capture files](#file-formats) |
| Edge trigger | A rising or falling edge, built by the driver as two terms: the signal at 0 then at 1, or the reverse. See [Trigger](#trigger) |
| Etherbone | LiteX bridge that carries bus accesses in UDP packets over Ethernet. See [Adding LiteScope to a SoC](#integration) |
| Group | One list of probes; the group to capture is selected at run time. See [Analyzer architecture](#analyzer-architecture) |
| Immediate capture | Capture without terms: the analyzer fires at once. See [Trigger](#trigger) |
| IO probe | `LiteScopeIO`: inputs and outputs read and written through registers. See [IO probe](#io-probe) |
| JTAGBone | LiteX bridge over the JTAG port of the FPGA. See [Adding LiteScope to a SoC](#integration) |
| `litex_server` | Host program that owns the bridge and serves it to the host tools on a TCP port. See [Host tools: CLI, driver and GUI](#host-tools) |
| Mask | The bits of a sample that a term compares. See [Trigger](#trigger) |
| MultiReg | LiteX synchronizer: a chain of registers that brings a signal into another clock domain. See [Analyzer architecture](#analyzer-architecture) |
| Pre-trigger window | Samples kept before the trigger, set by `offset`. See [Storage and read-back](#storage) |
| Probe | One signal given to the analyzer. See [Embedded logic analysis in a nutshell](#la-primer) |
| PulseView | The graphical viewer of sigrok, which opens `.sr` files. See [Capture files](#file-formats) |
| RLE | Run-length encoding: a repeated sample is stored once, then as a repeat count. See [Subsampler and run-length encoding](#subsampler-rle) |
| Sample | The value of all the probes of the selected group at one edge of the scope clock. See [Embedded logic analysis in a nutshell](#la-primer) |
| Scope clock domain | The clock domain in which the analyzer samples the probes (`clock_domain`). See [Analyzer architecture](#analyzer-architecture) |
| Sequence | Terms that must match one after the other before the analyzer fires. See [Trigger](#trigger) |
| sigrok | Open-source signal analysis suite; its session format is `.sr`. See [Capture files](#file-formats) |
| Subsampling factor | N when one sample in N is kept. See [Subsampler and run-length encoding](#subsampler-rle) |
| Term | One mask and value condition on a sample. See [Trigger](#trigger) |
| Term memory | The FIFO that holds the terms of the sequence until they match, `trigger_depth + 1` terms. See [Trigger](#trigger) |
| Trigger | The moment the last term of the sequence matches; the analyzer then fires. See [Trigger](#trigger) |
| UARTBone | LiteX bridge over a serial port. See [Adding LiteScope to a SoC](#integration) |
| VCD | Value Change Dump, the waveform text format of IEEE 1364, opened by GTKWave. See [Capture files](#file-formats) |
| Word | One entry of the sample memory: a sample or, with RLE, a repeat count. See [Subsampler and run-length encoding](#subsampler-rle) |
