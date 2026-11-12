# Examples and uses in the ecosystem {#examples}

This chapter describes the ready-made designs that contain an analyzer: the example of the
repository, the simulated SoC of LiteX, and the targets of the other LiteX cores that carry probe
lists for their own bring-up. Use them as a starting point for a design of your own, or to see how
a core of the ecosystem is usually observed.

## At a glance {#ex-glance}

| Design | Where | Probes | Depth | Clock domain |
|--------------|------------------------------------|-----------------|--------|-----------------|
| Arty example | `examples/arty.py` | CPU instruction bus, 8-bit counter | 1024 | `sys` |
| Simulated SoC | LiteX `litex_sim` | CPU instruction and data buses | 512 | `sys` |
| End-to-end test | `test/test_sim.py` | 32-bit counter; 4-bit value with RLE | 64 | `sys` |
| USB3-PIPE | `bench/usb3_soc.py` | Six probe lists of the PHY, one per build | 4096 | `sys` |
| LiteDRAM | `bench/*.py` | DFI of the PHY | 256, 512 | `sys` |
| LiteSATA | `bench/*.py` | State machines of every layer | 512, 2048 | `sys` |
| LiteEth | `bench/butterstick.py` | Handshakes of the core streams | 512 | `sys` |
| LitePCIe | `bench/soft/*.py` | Lane 0 of the soft PHY | 2048 | `pcie_pipe` |
| LiteICLink | `bench/serdes`, `serwb` | Transceiver and link states | 256, 512 | `sys` |

The depth and the domain are those of the source files. Most targets add their analyzer only with
a build switch, usually `--with-analyzer`; the LiteEth ButterStick bench and the LiteICLink SerDes
benches always build it. The end-to-end test is described in [Simulation and
verification](#simulation).

## The Arty example {#ex-arty}

`examples/arty.py` is the example of the repository. It builds the `BaseSoC` of the Arty A7 target
of LiteX-Boards with Etherbone, then adds an analyzer on the instruction bus of the CPU and on an
8-bit counter that increments every cycle.

| Item | Value |
|-------------------------|------------------------------------------------------------|
| Board | Arty A7 (Digilent), Artix-7 |
| SoC | `BaseSoC` of the `digilent_arty` target, 32 KiB integrated ROM |
| Bridge | Etherbone (`with_etherbone=True`), LiteX default IP address 192.168.1.50 |
| Probes | `self.cpu.ibus` (a Wishbone record, flattened) and `count` |
| Analyzer | `depth=1024`, `clock_domain="sys"`, `samplerate=self.sys_clk_freq` |
| Outputs | `csr.csv`, and `analyzer.csv` in the current directory |

The instruction bus record has eleven fields: address, write and read data, byte selects, the
control lines and the burst fields. With the counter, a sample is 116 bits wide, as an elaboration
of the example writes in its `analyzer.csv`. The memory of the analyzer therefore holds 1024 words
of 116 bits ([Performance and resources](#performance)).

```sh
# Elaborate only: Verilog, csr.csv and analyzer.csv, no toolchain
python3 examples/arty.py
# Build and load the bitstream (volatile)
python3 examples/arty.py --build --load
# Bridge over Ethernet, then the capture
litex_server --udp &
litescope_cli --list
litescope_cli -r <signal>
```

The comments at the top of the file give trigger examples with the names of an elaboration of the
example: the counter `main_count1` and the strobe of the instruction bus
`main_litescopesoc_ibus_stb`. The names depend on the version of LiteX: take them from
`litescope_cli --list` of your build.

`test/test_examples.py` runs the elaboration of the example and checks that the Verilog is written.
It needs LiteX-Boards but no FPGA toolchain.

## The simulated SoC of LiteX {#ex-litex-sim}

`litex_sim --with-analyzer` adds an analyzer to the SoC that LiteX simulates with Verilator. It
probes the instruction and data buses of the CPU: strobe, cycle, address, write enable,
acknowledge, byte selects, write and read data. A sample is 204 bits wide and the memory 512 words
deep.

This is the quickest way to learn the tools: no board, no bitstream, and a CPU that makes bus
traffic as soon as the BIOS starts. [Getting started](#getting-started) runs a complete session on
it, from `analyzer.csv` to the waveform. The simulated analyzer gets the frequency of the
simulated clock, 1 MHz, as `samplerate`, so its dumps carry a real time axis.

## Uses across the ecosystem {#ex-ecosystem}

The cores of the LiteX ecosystem use LiteScope for their own bring-up. Their targets are good
references for probe lists, and their manuals explain what to look for in each capture.

**USB3-PIPE.** `usb3_analyzer_groups()` in `usb3_pipe/debug.py` defines six probe lists of the
PHY, `link`, `lfps`, `ts`, `datapath`, `phase` and `u3`, each with the state of the link training
state machine; `phase` and `u3` need `--with-serdes-debug`. These lists are alternatives chosen at
build time: the bench SoC builds an analyzer on the list chosen by `--analyzer-group`, as its only
group, with `register=True` and a depth of 4096.

`bench/usb3_analyzer.py` drives the capture from Python with the driver: it loads terms on the
state machine, holds the PHY in reset while it arms, then retrains the link until the trigger
fires. See the
[Debugging](https://github.com/enjoy-digital/usb3_pipe/blob/master/doc/manual/14_debugging.md)
chapter of its manual, section "LiteScope captures".

**LiteDRAM.** The bench targets add an analyzer on the whole DFI of the PHY with `--with-analyzer`,
256 samples deep in the system clock domain, 512 on the Genesys2. The capture shows cycle
problems, such as a read latency off by one or a command on the wrong phase. See the
[Debugging](https://github.com/enjoy-digital/litedram/blob/master/doc/manual/16_debugging.md)
chapter of its manual, section "LiteScope on the DFI".

**LiteSATA.** The Xilinx bench targets add an analyzer on the state machines of the PHY and of the
link, transport and command layers, 512 samples deep. The KC705 target has three analyzers
instead, each with its own switch and its own file: `global_analyzer.csv`,
`sector2mem_analyzer.csv` and `mem2sector_analyzer.csv`.

The KC705 target is the reference for several analyzers in one SoC. See the
[Debugging](https://github.com/enjoy-digital/litesata/blob/master/doc/manual/15_debugging.md)
chapter of its manual, section "LiteScope captures".

**LiteEth.** The ButterStick bench probes the valid and ready handshakes at the boundaries of the
MAC, ARP, IP, UDP and Etherbone streams, and the Etherbone state machines, 512 samples deep. It has
a JTAGBone bridge next to Etherbone, so that a capture of the receive path can be read without
travelling on the link it observes. See the
[Debugging](https://github.com/enjoy-digital/liteeth/blob/master/doc/manual/18_debugging.md)
chapter of its manual, section "LiteScope on the streams".

**LitePCIe.** The soft PHY benches for the Acorn and the YPCB-00338-1P1 capture lane 0 in the
clock domain of the lane, `pcie_pipe`: received and transmitted symbols, electrical idle, receive
errors, training sequence and EIOS detections, 2048 samples.

The state of the link training state machine lives in another domain, so the targets copy it into
`pcie_pipe` through a `MultiReg` first. See the
[Debugging](https://github.com/enjoy-digital/litepcie/blob/master/doc/manual/16_debugging.md)
chapter of its manual, section "Soft PHY debug".

**LiteICLink.** The SerDes benches capture the initialization state machines and the lock or done
flags of the transceiver, 512 samples deep, on the ECPIX-5, the Versa ECP5 and the XCU1525. The
SerWB benches capture the initialization state machine and the data of the PHY, of both ends on
the Nexys Video, 256 samples deep.

The state machines of these benches appear with their state names in the waveforms, from the
enumeration rows of `analyzer.csv` ([Capture files](#file-formats)).

Other designs follow the same pattern: the LiteSDCard benches capture the SD card pads and the
command and data streams, 2048 samples deep. Among the LiteX-Boards targets, `adiuvo_forgix`
adds an analyzer with two groups and `register=True` with `--with-demo-scope`, and
`limesdr_mini_v2` captures its USB FIFO interface in the `usb` clock domain whenever the USB FIFO
is built.

## Agents and scripts {#ex-agents}

`litex_mcp`, the Model Context Protocol server of LiteX, gives the same captures to an agent.
`litex_scope_list` lists the probes of an `analyzer.csv`. `litex_scope_capture` arms a capture
with rising-edge, falling-edge and value triggers, then returns a summary per signal and the path
of the VCD file.

A plain script gets the same from `litescope_cli --json --timeout`
([Host tools: CLI, driver and GUI](#host-tools)).

## Where to go next {#ex-next}

[Adding LiteScope to a SoC](#integration) explains the choices behind these probe lists;
[Simulation and verification](#simulation) runs the analyzer without a board.
