```{=latex}
\frontmatter
```

# About this document {.unnumbered}

This manual is the reference of LiteScope, the embedded logic analyzer of the LiteX ecosystem. It
captures internal signals of a running FPGA design into block RAM, under the control of
triggers, and brings the samples back to a PC over the bus bridge the design already has: UART,
JTAG, Ethernet or PCIe.

The manual is written for FPGA engineers who want to see inside their design, and it explains
embedded logic analysis along the way: no prior knowledge of logic analyzers is assumed. Part I explains what an embedded logic analyzer
does and the vocabulary of a capture: probes, triggers, windows, subsampling, run-length
encoding.

Part II describes the gateware block by block. Part III is the user guide: the first
capture, the integration in a SoC, the host tools, the capture files, the examples, the
simulation and the debugging. The appendices hold the register reference, the parameters and
options, the glossary, the resources and the maintenance of this manual.

| If you want to | Read |
|------------------------------------------|----------------------------------------------|
| Know what LiteScope does and does not | [Introduction](#introduction) |
| Learn how an embedded analyzer works | [Embedded logic analysis in a nutshell](#la-primer) |
| Run a first capture, without a board | [Getting started](#getting-started) |
| Add an analyzer to your own SoC | [Adding LiteScope to a SoC](#integration) |
| Script captures from Python or a shell | [Host tools](#host-tools) |
| Understand a capture that does not trigger | [Debugging LiteScope itself](#debugging) |

The manual follows the repository: every name, default and register is taken from the source
code, the register reference is generated from it, and the title page gives the date of the build.
When the code and the manual disagree, the code is right and the manual has a bug.

## Conventions {.unnumbered}

- Numbers: `0x` prefix for hexadecimal, `0b` for binary. In a trigger value, `x` marks a don't
  care bit (`0b1x0`) or a don't care hexadecimal digit (`0x1x`).
- Sizes in words, KiB and MiB; times in ns, µs and ms; clock frequencies in MHz.
- *The analyzer* is `LiteScopeAnalyzer`, *the IO probe* is `LiteScopeIO`, *the driver* is
  `LiteScopeAnalyzerDriver` and *the CLI* is `litescope_cli`. *The host* is the PC that runs
  `litex_server` and the host tools; *the SoC* is the FPGA design that contains the analyzer.
- *Register* means a register of the SoC CSR bus, as listed in `csr.csv`.
- `<name>` stands for the name of the analyzer in the SoC, which is also the prefix of its
  registers, such as `analyzer` in `analyzer_trigger_enable`.
- `<signal>` stands for a probe name as `litescope_cli --list` prints it.
- Paths are relative to the repository root. Shell commands are given for a Linux host.
- When the text names a source file, it is the file to open to check or extend the fact.
