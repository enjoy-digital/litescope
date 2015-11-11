from migen import *
from migen.genlib.io import CRG

from targets import *

from litex.build.generic_platform import *
from litex.build.xilinx.platform import XilinxPlatform

from litex.soc.integration.soc_core import SoCCore
from litex.soc.cores.uart.bridge import UARTWishboneBridge

from litescope.core.port import LiteScopeTerm
from litescope.frontend.inout import LiteScopeInOut
from litescope.frontend.logic_analyzer import LiteScopeLogicAnalyzer


_io = [
    ("sys_clk", 0, Pins("X")),
    ("sys_rst", 1, Pins("X")),
    ("serial", 0,
        Subsignal("tx", Pins("X")),
        Subsignal("rx", Pins("X")),
    ),
    ("bus", 0, Pins(" ".join(["X" for i in range(128)])))
]

class CorePlatform(XilinxPlatform):
    name = "core"
    default_clk_name = "sys_clk"
    def __init__(self):
        XilinxPlatform.__init__(self, "", _io)

    def do_finalize(self, *args, **kwargs):
        pass


class Core(SoCCore):
    platform = CorePlatform()
    csr_map = {
        "logic_analyzer":    16
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform, clk_freq=100*1000000):
        self.clk_freq = clk_freq
        self.clock_domains.cd_sys = ClockDomain("sys")
        SoCCore.__init__(self, platform, clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design",
            with_timer=False
        )
        self.add_cpu_or_bridge(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)

        self.bus = platform.request("bus")
        self.submodules.logic_analyzer = LiteScopeLogicAnalyzer((self.bus), 512, with_rle=True, with_subsampler=True)
        self.logic_analyzer.trigger.add_port(LiteScopeTerm(self.logic_analyzer.dw))

    def get_ios(self):
        ios = set()
        ios = ios.union({self.cd_sys.clk,
                         self.cd_sys.rst})
        ios = ios.union({self.platform.lookup_request("serial").rx,
                         self.platform.lookup_request("serial").tx})
        ios = ios.union({self.bus})
        return ios

default_subtarget = Core
