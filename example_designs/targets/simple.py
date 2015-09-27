from migen.genlib.io import CRG

from misoclib.soc import SoC

from litescope.common import *
from litescope.core.port import LiteScopeTerm
from litescope.frontend.inout import LiteScopeInOut
from litescope.frontend.logic_analyzer import LiteScopeLogicAnalyzer

from misoclib.com.uart.bridge import UARTWishboneBridge

class LiteScopeSoC(SoC):
    csr_map = {
        "inout" :          16,
        "logic_analyzer" : 17
    }
    csr_map.update(SoC.csr_map)

    def __init__(self, platform):
        clk_freq = int((1/(platform.default_clk_period))*1000000000)
        SoC.__init__(self, platform, clk_freq,
            cpu_type="none",
            with_csr=True, csr_data_width=32,
            with_uart=False,
            with_identifier=True,
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

        self.submodules.counter0 = counter0 = Counter(8)
        self.submodules.counter1 = counter1 = Counter(8)
        self.comb += [
            counter0.ce.eq(1),
            If(counter0.value == 16,
                counter0.reset.eq(1),
                counter1.ce.eq(1)
            )
        ]

        self.debug = (
            counter1.value
        )
        self.submodules.logic_analyzer = LiteScopeLogicAnalyzer(self.debug, 512, with_rle=True, with_subsampler=True)
        self.logic_analyzer.trigger.add_port(LiteScopeTerm(self.logic_analyzer.dw))

    def do_exit(self, vns):
        self.logic_analyzer.export(vns, "test/logic_analyzer.csv")

default_subtarget = LiteScopeSoC
