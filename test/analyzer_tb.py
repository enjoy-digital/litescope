#!/usr/bin/env python3
from litex.gen import *

from litescope import LiteScopeAnalyzer

class TB(Module):
    def __init__(self):
        counter = Signal(16)
        self.sync += counter.eq(counter + 1)

        self.submodules.analyzer = LiteScopeAnalyzer(counter, 512)

def main_generator(dut):
    yield dut.analyzer.frontend.trigger.value.storage.eq(0x0080)
    yield dut.analyzer.frontend.trigger.mask.storage.eq(0xfff0)
    yield dut.analyzer.frontend.subsampler.value.storage.eq(2)
    yield
    yield dut.analyzer.storage.length.storage.eq(256)
    yield dut.analyzer.storage.offset.storage.eq(8)
    for i in range(16):
        yield
    yield dut.analyzer.storage.start.re.eq(1)
    yield
    yield dut.analyzer.storage.start.re.eq(0)
    yield
    while not (yield dut.analyzer.storage.idle.status):
        yield
    data = []
    while (yield dut.analyzer.storage.mem_valid.status):
        data.append((yield dut.analyzer.storage.mem_data.status))
        yield dut.analyzer.storage.mem_ready.re.eq(1)
        yield dut.analyzer.storage.mem_ready.r.eq(1)
        yield
        yield dut.analyzer.storage.mem_ready.re.eq(0)
        yield dut.analyzer.storage.mem_ready.r.eq(0)
        yield

    print(data)
    print(len(data))

if __name__ == "__main__":
    tb = TB()
    generators = {"sys" : [main_generator(tb)]}
    clocks = {"sys": 10}
    run_simulation(tb, generators, clocks, vcd_name="sim.vcd")
