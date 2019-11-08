#!/usr/bin/env python3

# This file is Copyright (c) 2019 kees.jongenburger <kees.jongenburger@gmail.com>
# License: BSD

from migen import *

from litex.boards.platforms import arty
from migen.genlib.io import CRG,DifferentialInput
from litex.soc.integration.soc_core import SoCCore
from litex.soc.cores.uart import UARTWishboneBridge
from litex.build.generic_platform import Subsignal
from litex.build.generic_platform import Pins
from litex.build.generic_platform import IOStandard
from litex.soc.cores.clock import *

from litescope import LiteScopeIO, LiteScopeAnalyzer

#
# Use the 8 input on the dual PMOD connector B as input
# Those are the fast and not so well protected pins.
_serdes_io = [
    ("serdes_io", 0,
        Subsignal("d0", Pins("E15"),IOStandard("LVCMOS33")),
        Subsignal("d1", Pins("E16"),IOStandard("LVCMOS33")),
        Subsignal("d2", Pins("D15"),IOStandard("LVCMOS33")),
        Subsignal("d3", Pins("C15"),IOStandard("LVCMOS33")),
        Subsignal("d4", Pins("J17"),IOStandard("LVCMOS33")),
        Subsignal("d5", Pins("J18"),IOStandard("LVCMOS33")),
        Subsignal("d6", Pins("K15"),IOStandard("LVCMOS33")),
        Subsignal("d7", Pins("J15"),IOStandard("LVCMOS33")),
    )
]

class SerdesInputSignal(Module):
    def __init__(self, pad):

        self.signals = Signal(8)
        #
        # Based on a 100MHz input clock and a 400MHz sample clock and
        # Measuring at ddr speed we are sampling at 800Mhz
        #
        self.specials += Instance("ISERDESE2",
                p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="NONE",

                i_D=pad,
                i_CE1=1,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKB=~ClockSignal("sys4x"),
                i_CLKDIV=ClockSignal("sys"),
                i_BITSLIP=0,
                o_Q8=self.signals[0], o_Q7=self.signals[1],
                o_Q6=self.signals[2], o_Q5=self.signals[3],
                o_Q4=self.signals[4], o_Q3=self.signals[5],
                o_Q2=self.signals[6], o_Q1=self.signals[7]
            )

class SerdesIO(Module):

    def __init__(self,platform):
        platform.add_extension(_serdes_io)

        pads  = platform.request("serdes_io")
        self.submodules.d0 = SerdesInputSignal(pads.d0)
        self.submodules.d1 = SerdesInputSignal(pads.d1)
        self.submodules.d2 = SerdesInputSignal(pads.d2)
        self.submodules.d3 = SerdesInputSignal(pads.d3)
        self.submodules.d4 = SerdesInputSignal(pads.d4)
        self.submodules.d5 = SerdesInputSignal(pads.d5)
        self.submodules.d6 = SerdesInputSignal(pads.d6)
        self.submodules.d7 = SerdesInputSignal(pads.d7)

        platform.add_platform_command("""
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
""")

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)

        self.cd_sys.clk.attr.add("keep")
        self.cd_sys4x.clk.attr.add("keep")

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        self.comb += pll.reset.eq(~platform.request("cpu_reset"))
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys4x, 4*sys_clk_freq)

class LiteScopeSoC(SoCCore):
    csr_map = {
        "analyzer": 17
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform):
        sys_clk_freq = int(100e6)

        SoCCore.__init__(self, platform, sys_clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Fast scope", ident_version=True,
            with_timer=False
        )
        self.submodules.serdes = SerdesIO(platform)
        # crg
        self.submodules.crg = _CRG(platform,sys_clk_freq)

        # bridge
        bridge = UARTWishboneBridge(platform.request("serial"), sys_clk_freq, baudrate=115200)
        self.submodules.bridge = bridge
        self.add_wb_master(bridge.wishbone)

        # Litescope Analyzer
        analyzer_groups = {}

        # Analyzer group
        analyzer_groups[0] = [
           self.serdes.d0.signals,
           self.serdes.d1.signals,
           self.serdes.d2.signals,
           self.serdes.d3.signals,
        ]

        # analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_groups, 512)

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "test/analyzer.csv")


platform = arty.Platform()

soc = LiteScopeSoC(platform)
vns = platform.build(soc)

#
# Create csr and analyzer files
#
soc.finalize()
csr_regions = soc.get_csr_regions()
csr_constants = soc.get_constants()
from litex.build.tools import write_to_file
from litex.soc.integration import cpu_interface

csr_csv = cpu_interface.get_csr_csv(csr_regions, csr_constants)
write_to_file("test/csr.csv", csr_csv)
soc.do_exit(vns)


#
# Program
#
platform.create_programmer().load_bitstream("build/top.bit")
