from litex.gen.genlib.io import CRG

from litescope.common import *
from litescope.core.port import LiteScopeTerm
from litescope.frontend.inout import LiteScopeInOut
from litescope.frontend.logic_analyzer import LiteScopeLogicAnalyzer

from litex.soc.integration.soc_core import SoCCore
from litex.soc.cores.uart.bridge import UARTWishboneBridge

class LiteScopeSoC(SoCCore):
    csr_map = {
        "inout" :          16,
        "logic_analyzer" : 17
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform):
        clk_freq = int((1/(platform.default_clk_period))*1000000000)
        SoCCore.__init__(self, platform, clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design",
            with_timer=False
        )
        self.add_cpu_or_bridge(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        self.submodules.inout = LiteScopeInOut(8)
        for i in range(8):
            try:
                self.comb += platform.request("user_led", i).eq(self.inout.o[i])
            except:
                pass

        counter = Signal(16)
        self.sync += counter.eq(counter + 1)

        self.debug = (counter)
        self.submodules.logic_analyzer = LiteScopeLogicAnalyzer(self.debug, 512, with_rle=True, with_subsampler=True)
        self.logic_analyzer.trigger.add_port(LiteScopeTerm(self.logic_analyzer.dw))

    def do_exit(self, vns):
        self.logic_analyzer.export(vns, "test/logic_analyzer.csv")

default_subtarget = LiteScopeSoC
