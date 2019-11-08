# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

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
        sys_clk_freq = int((1e9/platform.default_clk_period))
        SoCCore.__init__(self, platform, sys_clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design", ident_version=True,
            with_timer=False
        )
        # crg
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        # bridge
        bridge = UARTWishboneBridge(platform.request("serial"), sys_clk_freq, baudrate=115200)
        self.submodules.bridge = bridge
        self.add_wb_master(bridge.wishbone)

        # Litescope IO
        self.submodules.io = LiteScopeIO(8)
        for i in range(8):
            try:
                self.comb += platform.request("user_led", i).eq(self.io.output[i])
            except:
                pass

        # Litescope Analyzer
        analyzer_groups = {}

        # counter group
        counter = Signal(16, name_override="counter")
        zero = Signal(name_override="zero")
        self.sync += counter.eq(counter + 1)
        self.comb += zero.eq(counter == 0)
        analyzer_groups[0] = [
            zero,
            counter
        ]

        # communication group
        analyzer_groups[1] = [
            platform.lookup_request("serial").tx,
            platform.lookup_request("serial").rx,
            bridge.wishbone
        ]

        # fsm group
        fsm = FSM(reset_state="STATE1")
        self.submodules += fsm
        fsm.act("STATE1",
            NextState("STATE2")
        )
        fsm.act("STATE2",
            NextState("STATE1")
        )
        analyzer_groups[2] = [
            fsm
        ]

        # analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_groups, 512)

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "test/analyzer.csv")

default_subtarget = LiteScopeSoC
