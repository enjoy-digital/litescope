# This file is Copyright (c) 2017-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import unittest

from migen import *

from litescope import LiteScopeAnalyzer

#TODO:
# - improve testing with a software model and check that the implementation
#   has a similar behaviour.


class DUT(Module):
    def __init__(self):
        counter = Signal(16)
        self.sync += counter.eq(counter + 1)

        self.submodules.analyzer = LiteScopeAnalyzer(counter, 512)


def main_generator(dut):
    yield from dut.analyzer.frontend.trigger.value.write(0x0080)
    yield from dut.analyzer.frontend.trigger.mask.write(0xfff0)
    yield from dut.analyzer.frontend.subsampler.value.write(2)
    yield
    yield from dut.analyzer.storage.length.write(256)
    yield from dut.analyzer.storage.offset.write(8)
    for i in range(16):
        yield
    yield from dut.analyzer.storage.start.write(1)
    yield
    while not (yield from dut.analyzer.storage.idle.read()):
        yield
    data = []
    while (yield from dut.analyzer.storage.mem_valid.read()):
        data.append((yield from dut.analyzer.storage.mem_data.read()))
        yield from dut.analyzer.storage.mem_ready.write(1)
        yield

    print(data)
    print(len(data))


class TestAnalyzer(unittest.TestCase):
    def test(self):
        dut = DUT()
        generators = {"sys" : [main_generator(dut)]}
        clocks = {"sys": 10}
        run_simulation(dut, generators, clocks, vcd_name="sim.vcd")
