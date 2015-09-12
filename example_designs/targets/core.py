from migen.genlib.io import CRG
from migen.genlib.resetsync import AsyncResetSynchronizer

from mibuild.generic_platform import *
from mibuild.xilinx.platform import XilinxPlatform

from targets import *

from misoclib.soc import SoC
from litescope.common import *
from litescope.core.port import LiteScopeTerm
from litescope.frontend.io import LiteScopeIO
from litescope.frontend.la import LiteScopeLA


_io = [
    ("sys_clk", 0, Pins("X")),
    ("sys_rst", 1, Pins("X")),
    ("serial", 0,
        Subsignal("tx", Pins("X")),
        Subsignal("rx", Pins("X")),
    ),
    ("bus", 0, Pins(" ".join(["X" for i in range(128)])))
]

from misoclib.com.uart.bridge import UARTWishboneBridge

class CorePlatform(XilinxPlatform):
    name = "core"
    default_clk_name = "sys_clk"
    def __init__(self):
        XilinxPlatform.__init__(self, "", _io)

    def do_finalize(self, *args, **kwargs):
        pass


class Core(SoC):
    platform = CorePlatform()
    csr_map = {
        "la":    16
    }
    csr_map.update(SoC.csr_map)

    def __init__(self, platform, clk_freq=100*1000000):
        self.clk_freq = clk_freq
        self.clock_domains.cd_sys = ClockDomain("sys")
        SoC.__init__(self, platform, clk_freq,
            cpu_type="none",
            with_csr=True, csr_data_width=32,
            with_uart=False,
            with_identifier=True,
            with_timer=False
        )
        self.add_cpu_or_bridge(UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu_or_bridge.wishbone)

        self.bus = platform.request("bus")
        self.submodules.la = LiteScopeLA((self.bus), 512, with_rle=True, with_subsampler=True)
        self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

    def get_ios(self):
        ios = set()
        ios = ios.union({self.cd_sys.clk,
                         self.cd_sys.rst})
        ios = ios.union({self.platform.lookup_request("serial").rx,
                         self.platform.lookup_request("serial").tx})
        ios = ios.union({self.bus})
        return ios

default_subtarget = Core
