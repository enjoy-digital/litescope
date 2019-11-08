# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.io import CRG

from targets import *

from litex.build.generic_platform import *
from litex.build.xilinx.platform import XilinxPlatform

from litex.soc.integration.soc_core import SoCCore
from litex.soc.cores.uart import UARTWishboneBridge

from litescope import LiteScopeAnalyzer


_io = [
    ("sys_clock", 0, Pins(1)),
    ("sys_reset", 1, Pins(1)),
    ("serial", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
    ("bus", 0, Pins(128))
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
        "analyzer":    16
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform, clk_freq=100*1000000):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.comb += [
            self.cd_sys.clk.eq(platform.request("sys_clock")),
            self.cd_sys.rst.eq(platform.request("sys_reset"))
        ]
        SoCCore.__init__(self, platform, clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design",
            with_timer=False
        )
        bridge = UARTWishboneBridge(platform.request("serial"), clk_freq, baudrate=115200)
        self.submodules.bridge = bridge
        self.add_wb_master(bridge.wishbone)

        self.bus = platform.request("bus")
        self.submodules.analyzer = LiteScopeAnalyzer((self.bus), 512)

default_subtarget = Core
