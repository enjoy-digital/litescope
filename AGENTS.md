# AGENTS.md: LiteScope

Embedded logic analyzer for LiteX: signal groups, triggers, subsampling, RLE, BRAM storage, read
back through any LiteX bridge, exported to VCD/sigrok/CSV.

Read the LiteX agent page first: https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents (framework map, conventions, how to
verify a change, contribute back). Index of the whole wiki for agents: https://github.com/enjoy-digital/litex/wiki/llms.txt.

## Where things are

- `litescope/core.py`: `LiteScopeAnalyzer` (gateware), writes `analyzer.csv` (signals, groups, depth).
- `litescope/software/driver/analyzer.py`: `LiteScopeAnalyzerDriver`; `litescope/software/dump/`: VCD/sigrok/CSV.
- `litescope/software/litescope_cli.py` (`litescope_cli`): list, trigger, capture, dump.

## Verify a change

```sh
python3 -m pytest -v                                               # what CI runs (includes simulations)
litescope_cli --csv analyzer.csv --csr-csv csr.csv --list          # against a running SoC (litex_server)
```

- Trigger values are strings (`"0b1"`, `"0x10"`).
- `analyzer.csv` is written when the build/run exits; with `litex_sim`, generate it first with
  `--no-compile`.
- Keep analyzers in one clock domain (prefer `sys`) and below ~128 bits: an analyzer in a fast
  transceiver domain can fail timing itself and give wrong captures.

## Rules

- Style: https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md (match the
  surrounding file; `module: Description of the change.` commit titles; one change per commit).
- Never edit generated files (`build/`, `csr.h`, `csr.csv`, the Verilog): change the Python.
- One topic per pull request, from `master`, with what was tested and on which hardware; say
  that an agent wrote it and who supervised. Do not rename options or reformat unrelated code.
- Hardware: never flash a board or write its SPI flash unless the user asked; `--load` (volatile)
  is the default for experiments.

## Debug on hardware

Method: https://github.com/enjoy-digital/litex/wiki/Debug-A-SoC-On-Hardware (check the link and `--ident` first, registers before
traces, narrow LiteScope captures). `litex_mcp` gives the same loop as MCP tools (CSRs by name,
LiteScope captures, builds with parsed timing, simulation): https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#drive-a-soc-through-mcp.
