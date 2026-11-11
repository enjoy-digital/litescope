```{=latex}
\part{Use it}
```

```{=html}
<h1 class="part">Part III. Use it</h1>
```

# Getting started {#getting-started}

This chapter takes you from a fresh machine to a first capture, with no board. It runs the
simulated SoC of LiteX, which has an analyzer on the buses of its CPU, captures on a value and on
a rising edge, and reads the result. A last section applies the flow to a board. Every output
shown comes from a real run.

## Install {#gs-install}

LiteScope is a Python package built on LiteX. Install LiteX by following the installation page of
its wiki (`litex_setup.py`): it installs Migen, LiteX, LiteX-Boards and the cores, LiteScope
included. To work on a clone of the repository, install it in development mode:

```sh
git clone https://github.com/enjoy-digital/litescope
cd litescope
pip3 install -e .
```

The package needs Python 3.7 or newer and installs the `litescope_cli` command. The other tools
depend on what you run, as the table below shows.

| Task | Tools |
|------------------------------|------------------------------------------------------------------|
| Captures in simulation | Verilator, a C++ compiler, libevent, json-c, zlib, Meson, Ninja, RISC-V GCC, `socat` |
| Captures on a board | The FPGA toolchain of the board, its programmer |
| Bridge and capture | `litex_server`, `litex_term` (LiteX), `litescope_cli` (LiteScope) |
| Viewing a dump | GTKWave (VCD) or PulseView (sigrok session) |

`litex_setup.py --gcc=riscv` installs the RISC-V GCC toolchain that the BIOS of the simulated SoC
needs; Meson and Ninja build its C library. `socat` creates the virtual serial port of step 2.

## The simulated SoC {#gs-sim-soc}

`litex_sim` builds a LiteX SoC with a VexRiscv CPU and runs it in Verilator, with a system
clock of 1 MHz. With `--with-analyzer`, it adds an analyzer named `analyzer` on the instruction
bus and the data bus of the CPU: 16 probes in one group, 512 samples deep, in the `sys` clock
domain ([The simulated SoC of LiteX](#ex-litex-sim)).

The host needs a bridge to reach the registers of the analyzer. `--uart-name=crossover+uartbone`
turns the simulated serial port into a UARTBone bridge and moves the console of the BIOS to a
crossover UART, which the host reads through the same bridge. `--uart-tcp` exposes the serial
port on a TCP port; `--uart-pty` also links a virtual serial device of the host to it, through a
`socat` process.

## Step 1: generate `analyzer.csv` {#gs-elaborate}

The analyzer writes `analyzer.csv` when the build of the SoC exits. A running simulation does not
exit, so the file comes from a first elaboration that compiles nothing (`--no-compile`). Run it
in an empty directory, the working directory of every later step.

```sh
mkdir sim && cd sim
litex_sim --with-analyzer --uart-name=crossover+uartbone --uart-tcp \
    --uart-tcp-port 2345 --csr-csv csr.csv --no-compile
```

This step uses `--uart-tcp` rather than `--uart-pty`: `litex_sim` starts its `socat` process even
with `--no-compile` and does not stop it, and a `socat` left from this step would compete with the
one of step 2 for the bridge. Both options give the same `analyzer.csv` and `csr.csv`.

`--uart-tcp-port 2345` moves the TCP port of the simulated serial port away from 1234, the
default port of `litex_server`; with both on 1234, `litex_server` cannot start. `--csr-csv
csr.csv` writes the register map next to `analyzer.csv`, where the host tools look for both by
default.

**What you should see.** The log of the build lists `analyzer (LiteScopeAnalyzer)` in the
hierarchy of the SoC, and the directory holds `analyzer.csv` and `csr.csv`. The excerpt below is
the start and the end of the generated `analyzer.csv`:

```text
config,None,data_width,204
config,None,storage_width,204
config,None,depth,512
config,None,samplerate,1000000000000
config,None,subsampler_width,16
config,None,with_rle,0
config,None,rle_length,256
signal,0,simsoc_ibus_stb,1
signal,0,simsoc_ibus_cyc,1
signal,0,simsoc_ibus_adr,30
[...]
signal,0,simsoc_dbus_dat_r,32
```

A sample is 204 bits, the sum of the widths of the 16 probes. The sample rate is the default of
the analyzer, a placeholder: `litex_sim` does not pass the frequency of its clock, which shows
when the dump is opened (step 7). [Capture files](#fmt-analyzer-csv) describes every row.

## Step 2: run the simulation {#gs-sim}

Run the command again in a first terminal, with `--uart-pty --uart-pty-path ./pty0` in place of
`--uart-tcp` and without `--no-compile`. `--non-interactive` keeps the terminal out of the
simulation; the console of the BIOS is on the crossover UART anyway.

```sh
litex_sim --with-analyzer --uart-name=crossover+uartbone --uart-pty \
    --uart-pty-path ./pty0 --uart-tcp-port 2345 --csr-csv csr.csv --non-interactive
```

**What you should see.** LiteX compiles the BIOS, then Verilator compiles the SoC, which takes a
while the first time. The simulation then starts and `./pty0` appears: a link to the virtual
serial device that carries the bridge.

## Step 3: start `litex_server` {#gs-server}

`litex_server` opens the bridge and serves it to the host tools over TCP, on `localhost:1234` by
default. Start it in a second terminal, from the same directory.

```sh
litex_server --uart --uart-port=./pty0
```

The BIOS console is on the crossover UART, so open it through the server in a third terminal.
`litex_term` finds the registers of the crossover UART in `csr.csv`.

```sh
litex_term crossover
```

**What you should see.** The BIOS banner, then the `litex>` prompt. The BIOS boots during step
2, so the banner may have gone by already: if the console stays empty, press Enter, and the BIOS
answers with a new `litex>` prompt. The lines below are the end of the banner, from the same run:

```console
--================ SoC =================--
CPU:		VexRiscv @ 1MHz
BUS:		wishbone 32-bit data/32-bit addr
CSR:		32-bit data big ordering
ROM:		128.0KiB
SRAM:		8.0KiB

--================ Boot ================--
Booting from serial...
Press Q or ESC to abort boot completely.
[...]
Timeout
No boot medium found

--============== Console ===============--

litex>
```

## Step 4: list the probes {#gs-list}

`litescope_cli --list` prints the probes of group 0 from `analyzer.csv`. It does not use the
bridge, so it is also a quick check that the file is the right one.

```console
$ litescope_cli --list
simsoc_ibus_stb
simsoc_ibus_cyc
simsoc_ibus_adr
simsoc_ibus_we
simsoc_ibus_ack
simsoc_ibus_sel
simsoc_ibus_dat_w
simsoc_ibus_dat_r
simsoc_dbus_stb
simsoc_dbus_cyc
simsoc_dbus_adr
simsoc_dbus_we
simsoc_dbus_ack
simsoc_dbus_sel
simsoc_dbus_dat_w
simsoc_dbus_dat_r
```

The names come from the design, and change with it and with the version of LiteX. Take them from
this list rather than from an older document. The CLI also accepts part of a name, as a regular
expression, when it matches one probe only ([Signal names](#host-cli-names)).

## Step 5: trigger on a value {#gs-value}

A value trigger fires on the first sample where a probe holds a given value. The capture below
waits for the CPU to put `0x12345678` on the write data of its data bus. Arm it first:

```console
$ litescope_cli -v simsoc_dbus_dat_w 0x12345678 --dump value.vcd
Exact: simsoc_dbus_dat_w
Exact: simsoc_dbus_dat_w
Condition: simsoc_dbus_dat_w == 0x12345678
analyzer: run (offset=32, length=512)
analyzer: wait_done (delay=0.2s)
```

Each lookup of a name prints an `Exact:` line; `-v` looks its name up twice ([Signal
names](#host-cli-names)).

Then make the CPU write that value. The BIOS command `mem_write` writes a word at an address,
here the scratch register of the SoC (`ctrl_scratch`, at `0xf0000804` in `csr.csv`), which
nothing else uses.

```console
litex> mem_write 0xf0000804 0x12345678
```

The CLI was waiting at `wait_done`. The write fires the trigger, and the CLI uploads the samples
and writes the dump:

```console
analyzer: upload (words=508)
analyzer: [====================] 100%
analyzer: write value.vcd
```

The `run` line shows the defaults of the CLI: 32 samples before the trigger, and a capture as long
as the depth. The upload reads 508 of the 512 captured words; [Upload](#stor-upload) explains
the missing ones. The upload is slow in simulation, where the serial bridge runs at the speed of
the simulated clock.

**What the capture holds.** The matching write is sample 30, two samples before the 32 of
`--offset` ([Trigger position in the capture](#trig-position)). It is not the write to the
scratch register: it is the BIOS saving the parsed value on its stack, in the SRAM. The scratch
register write comes about 200 samples later.

The data bus carries word addresses: the stack write shows `0x40007af`, which is the byte
address `0x10001ebc`.

A trigger watches the probes, not the intent of the software. To catch the register write itself,
add a condition on the address: several `-v` options are ANDed into one term. The word address of
`0xf0000804` is `0xf0000804 >> 2`, that is `0x3c000201`.

```console
$ litescope_cli -v simsoc_dbus_dat_w 0x12345678 -v simsoc_dbus_adr 0x3c000201 \
    --dump value_adr.vcd
Exact: simsoc_dbus_dat_w
Exact: simsoc_dbus_dat_w
Condition: simsoc_dbus_dat_w == 0x12345678
Exact: simsoc_dbus_adr
Exact: simsoc_dbus_adr
Condition: simsoc_dbus_adr == 0x3c000201
analyzer: run (offset=32, length=512)
analyzer: wait_done (delay=0.2s)
analyzer: upload (words=508)
analyzer: [====================] 100%
analyzer: write value_adr.vcd
```

With the same `mem_write` in the console, the capture now holds the register write at samples 30
to 32. The cycle, strobe and write enable lines are high on the three samples, and the
acknowledge of the bus comes on the third. Values take a `0b` or `0x` prefix, and `x` digits are
don't care bits or nibbles ([Value strings](#trig-values)).

## Step 6: trigger on a rising edge {#gs-edge}

An edge trigger fires when a 1-bit probe goes from 0 to 1 (`-r`) or from 1 to 0 (`-f`). The
analyzer has no edge detector: the driver loads a sequence of two terms, the probe at 0 and then
at 1 ([Edges](#trig-edges)). The capture below fires on the first instruction fetch of the CPU
that misses its cache.

```console
$ litescope_cli -r simsoc_ibus_stb --dump rising.vcd
Exact: simsoc_ibus_stb
Rising edge: simsoc_ibus_stb
analyzer: run (offset=32, length=512)
analyzer: wait_done (delay=0.2s)
```

While the BIOS waits at its prompt, its code runs from the instruction cache and the instruction
bus stays idle. Press Enter in the console of `litex_term`: the BIOS runs code outside the cache,
the CPU fetches it, and the CLI ends as in step 5, with `write rising.vcd`.

The figure below is drawn from `rising.vcd`, around the trigger. Bus values are in hexadecimal,
and addresses are word addresses.

![A real capture: the rising edge of ibus_stb, drawn from the dump of litescope_cli -r
simsoc_ibus_stb. The strobe rises at sample 30, where the trigger fires; the CPU then reads eight
consecutive words, one acknowledge every other cycle, to refill one line of its instruction cache.
The read data is shaded until the first acknowledge. Probe names are shown without their
`simsoc_` prefix.](gs_capture.svg)

The strobe and the cycle line rise together at sample 30 and stay high for the whole refill. The
address starts at `0x6b0` and moves to the next word after each acknowledge, and the read data
changes with each acknowledge. After eight words the cycle line falls, and the CPU runs from the
cache again.

## Step 7: open the dump {#gs-view}

The dumps are Value Change Dump files, which GTKWave opens:

```sh
gtkwave rising.vcd
```

The start of the file shows its layout: one variable per probe, then `scope_clk` and
`scope_trig`, two variables that the driver adds.

```text
$date
	2026-11-11 12:56
$end
$timescale 0ps $end
$scope module top $end
$var wire 1 ! simsoc_ibus_stb $end
$var wire 1 " simsoc_ibus_cyc $end
$var wire 30 # simsoc_ibus_adr $end
[...]
$var wire 32 0 simsoc_dbus_dat_r $end
$var wire 1 1 scope_clk $end
$var wire 1 2 scope_trig $end
$upscope  $end
$enddefinitions  $end
```

`$timescale 0ps` comes from the placeholder sample rate of step 1. The order of the samples is
right but the time axis is not ([Wrong time scale](#debug-timescale)). Count samples instead of
reading times: each sample takes two time steps, one with `scope_clk` high and one with it low
([What every dump contains](#fmt-common)).

Do not use `scope_trig` to find the trigger in these dumps: it rises at sample 16, half of
`--offset`, while the match is at sample 30. Look for the matching value in the data, as the
figure of step 6 does. `--dump` with a `.sr`, `.csv`, `.json` or `.py` name writes the other
formats ([Capture files](#file-formats)).

## On a board {#gs-board}

On a board, the flow is the same, with a real bridge in place of the simulated serial port. The
example of the repository, `examples/arty.py`, builds the Arty A7 target of LiteX-Boards with an
Etherbone bridge, and an analyzer on the instruction bus of the CPU and on a counter ([The Arty
example](#ex-arty)).

```sh
# Build and load the bitstream (Vivado); writes analyzer.csv and csr.csv
python3 examples/arty.py --build --load
# Bridge over Ethernet, to the LiteX default IP address 192.168.1.50
litex_server --udp
# Probes, then a capture
litescope_cli --list
litescope_cli -r <signal>
```

Connect the Ethernet port of the board to the host, and give the host an address on the same
subnet, such as 192.168.1.100. `litescope_cli` without a trigger option captures at once, which
checks the whole chain before the first real trigger.

**What to look for.** `litescope_cli --list` prints the names of your build, which differ from
the names in the comments of `examples/arty.py`. A capture ends with `write dump.vcd`. The
counter probe counts the cycles of the `sys` clock, so it increments by one on each sample.
This analyzer passes `samplerate`, so its dumps have a real time axis.

For a design of your own, [Adding LiteScope to a SoC](#integration) adds the analyzer and the
bridge to any LiteX target.

## If it does not work {#gs-failures}

- **`litex_server` cannot bind its port**: another program uses `localhost:1234`, often the
  simulated serial port when `--uart-tcp-port` is left at its default. Move one of them:
  `--uart-tcp-port`, or `litex_server --bind-port` with `litescope_cli --port`.
- **`litescope_cli` cannot find `analyzer.csv` or `csr.csv`**: run it from the build directory,
  or pass `--csv` and `--csr-csv`.
- **The CLI stays at `wait_done`**: the event did not happen after the trigger was armed. Check
  the value and the signal name, and use `--timeout` in scripts ([The capture never
  triggers](#debug-no-trigger)).
- **The dump has no usable time axis**: the analyzer was built without `samplerate` ([Wrong time
  scale](#debug-timescale)).

## Where to go next {#gs-next}

[Adding LiteScope to a SoC](#integration) to probe your own design, [Host tools](#host-tools) for
every option of the CLI and the Python driver, [Trigger](#trigger) for sequences and edges.
