from migen import *
from migen.genlib.io import CRG

from litex.soc.integration.soc_core import SoCCore
from litex.soc.cores.uart import UARTWishboneBridge

from litescope import LiteScopeIO, LiteScopeAnalyzer


class LiteScopeSoC(SoCCore):
    csr_map = {
        "io":       16,
        "analyzer": 17
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform):
        clk_freq = int((1/(platform.default_clk_period))*1000000000)
        SoCCore.__init__(self, platform, clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design", ident_version=True,
            with_timer=False
        )
        self.add_cpu_or_bridge(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        self.submodules.io = LiteScopeIO(8)
        for i in range(8):
            try:
                self.comb += platform.request("user_led", i).eq(self.io.output[i])
            except:
                pass

        # use name override to keep naming in capture
        counter = Signal(16, name_override="counter")
        counter0 = Signal(name_override="counter0")
        counter1 = Signal(name_override="counter1")
        counter2 = Signal(name_override="counter2")
        counter3 = Signal(name_override="counter3")
        self.sync += counter.eq(counter + 1)
        self.comb += [
            counter0.eq(counter[0]),
            counter1.eq(counter[1]),
            counter2.eq(counter[2]),
            counter3.eq(counter[3]),
        ]
        zero = Signal()
        self.comb += zero.eq(counter == 0)

        # group for vcd capture
        vcd_group = [
            zero,
            counter,
        ]
        # group for sigrok capture (no bus support)
        sigrok_group = [
            counter0,
            counter1,
            counter2,
            counter3
        ]
        analyzer_signals = {
            0 : vcd_group,
            1 : sigrok_group
        }
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 512)

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "test/analyzer.csv")

default_subtarget = LiteScopeSoC
