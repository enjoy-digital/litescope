# IO probe {#io-probe}

This chapter describes the IO probe, `LiteScopeIO`: a pair of registers that let the host read
signals of the design and drive others, without a capture. Use it for virtual switches and LEDs,
or to read a status value at any time. The [status](#intro-status) of the IO probe is given in the
introduction.

## At a glance {#io-glance}

| Item | Value |
|---------------------|---------------------------------------------------------------------|
| Class | `LiteScopeIO(data_width)` (`litescope/core.py`) |
| Signals | `input` (read by the host), `output` (driven by the host), `data_width` bits each |
| Registers | `in` (read-only), `out` (read-write), named after the instance |
| Clock domain | `sys` |
| Built on | `GPIOInOut` of LiteX (`litex/soc/cores/gpio.py`) |
| Driver | `LiteScopeIODriver(regs, name)`: `read()`, `write(value)` |

## Gateware {#io-gateware}

The IO probe wraps a `GPIOInOut` of LiteX, as the figure below shows. The design drives `input`,
which the host reads through the `in` register. The host writes the `out` register, whose value
drives `output` into the design.

![IO probe. Look at the two directions: input goes through a synchronizer into the in register
read by the host; the out register written by the host drives output.](io_probe.svg)

`input` crosses into `sys` through a `MultiReg`, so a signal of another clock domain can be read
safely bit by bit. The bits of a multi-bit value are synchronized one by one: a value read while
it changes may mix old and new bits. Read such a value until two reads agree, or use the analyzer.

`out` is a register of the `sys` domain and resets to 0. `output` follows it directly, without
synchronization: resynchronize it in the design when it drives logic of another clock domain.

Unlike the analyzer, the IO probe takes no signals as arguments: connect them to its `input` and
`output` signals.

```python
from litescope import LiteScopeIO

# In the SoC: 8 switches read by the host, 8 LEDs driven by the host.
self.io = LiteScopeIO(8)
self.comb += [
    self.io.input.eq(switches),
    leds.eq(self.io.output),
]
```

## Driver {#io-driver}

The host reaches the IO probe through the register bus and a bridge, as for the analyzer.
`LiteScopeIODriver` binds the two registers by the name of the instance, `io` in the example.

```python
from litex import RemoteClient
from litescope import LiteScopeIODriver

bus = RemoteClient(csr_csv="csr.csv")
bus.open()
io = LiteScopeIODriver(bus.regs, "io")
io.write(0x55)   # Drive the LEDs.
print(io.read()) # Read the switches.
bus.close()
```

The same registers are reachable from any register access tool, by their names in `csr.csv`:
`io_in` and `io_out` for an instance named `io`. [Adding LiteScope to a SoC](#integration) covers
the bridges and `litex_server`.

## Uses {#io-uses}

- **Virtual switches and LEDs**: control a design on a board without buttons or LEDs, or remotely.
- **Static status**: read a lock flag, an error counter or a version value at any time.
- **Simple stimulus**: drive an enable or a mode bit of the design under test between two
  analyzer captures.

The IO probe sees one value at the time of the read. For anything that changes faster than the
register accesses, capture it with the analyzer.

## In the code {#io-code}

| Item | Place |
|----------------------|------------------------------------------------------------------|
| Gateware | `LiteScopeIO`, `litescope/core.py` |
| Driver | `LiteScopeIODriver`, `litescope/software/driver/io.py` |
| Registers | `GPIOIn` and `GPIOOut`, `litex/soc/cores/gpio.py` in LiteX |

Where to go next: [Analyzer architecture](#analyzer-architecture) to capture signals over time,
[Host tools](#host-tools) for the analyzer driver.
