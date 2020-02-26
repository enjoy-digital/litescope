# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from targets import *

from litex.build.generic_platform import *
from litex.build.xilinx.platform import XilinxPlatform

from litex.soc.integration.soc_core import SoCMini

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
    def __init__(self):
        XilinxPlatform.__init__(self, "", _io)


class Core(SoCMini):
    platform = CorePlatform()
    def __init__(self, platform, clk_freq=100*1000000):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.comb += [
            self.cd_sys.clk.eq(platform.request("sys_clock")),
            self.cd_sys.rst.eq(platform.request("sys_reset"))
        ]
        SoCMini.__init__(self, platform, clk_freq, csr_data_width=32,
            with_uart=True, uart_name="bridge",
            ident="Litescope example design", ident_version=True,
        )

        self.submodules.analyzer = LiteScopeAnalyzer(platform.request("bus"), 512)
        self.add_csr("analyzer")

default_subtarget = Core
