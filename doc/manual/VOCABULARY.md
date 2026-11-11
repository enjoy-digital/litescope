# Vocabulary of the LiteScope manual

Project-specific writing rules, completing the generic `STYLE.md` of the manual kit.

## Names of the parts

- *the analyzer* is `LiteScopeAnalyzer` (the gateware that captures); *the IO probe* is
  `LiteScopeIO` (static inputs and outputs read and written through registers); *LiteScope* or
  *the project* is the whole repository.
- *the driver* is `LiteScopeAnalyzerDriver` (Python, on the host); *the CLI* is `litescope_cli`;
  *the GUI* is `litescope_cli --gui`.
- *the host* is the PC that runs `litex_server`, the driver and the CLI; *the SoC* is the FPGA
  design that contains the analyzer.
- *bridge* is the SoC block that turns a host link into bus accesses: UARTBone, JTAGBone,
  Etherbone, PCIe. `litex_server` is the host program that owns the bridge and serves it on a
  TCP port.
- *target* is a board script (a LiteX-Boards target, a `bench/` script of another core);
  *example* is a file of `examples/`.
- *register* in prose, never "CSR", except in the bus name "CSR bus" and in file names
  (`csr.csv`).

## Capture vocabulary

- *probe*: one signal given to the analyzer. *group*: one list of probes, selected at run time;
  group 0 is the default.
- *sample*: the value of all probes of the selected group at one edge of the scope clock.
  *word*: one storage entry, a sample or, with run-length encoding, a repeat count.
- *term*: one mask and value condition on a sample. *sequence*: terms matched one after the
  other. *trigger*: the moment the last term of the sequence matches (the analyzer *fires*).
  *immediate capture*: a capture with no term, which fires at once.
- *arm*: start a capture (the driver's `run()`). *done*: the capture has filled its length.
- *pre-trigger window*: the samples kept before the trigger, set by `offset`. *capture length*:
  the number of words stored, set by `length`. *depth*: the size of the sample memory in words,
  fixed at build time.
- *subsampling factor*: N when one sample in N is kept (N = 1 keeps every sample).
- *run-length encoding*: written out at its first use in a chapter, then RLE.
- *scope clock domain*: the clock the probes are sampled in (`clock_domain`, `sys` by default).
- *capture*: one run from arm to upload. *dump*: a file written by the driver (VCD, sigrok, CSV,
  JSON, Python).

## Placeholders

- `<name>` is the name of the analyzer in the SoC, which is also the prefix of its registers
  (`analyzer` in the examples). `<signal>` is a probe name as `litescope_cli --list` prints it.
  Both are defined once in the Conventions of the front matter.

## Hardware and tool names

- Viewers: GTKWave, PulseView (sigrok). Simulators: Verilator, `litex_sim`.
- FPGA families and boards as LiteX-Boards names them (Arty A7, ECPIX-5, KC705).
- Vendor analyzers, when compared: AMD ILA, Intel SignalTap, Lattice Reveal.
