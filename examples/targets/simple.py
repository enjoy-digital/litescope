# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from litex.build.io import CRG

from litex.soc.integration.soc_core import SoCMini

from litescope import LiteScopeIO, LiteScopeAnalyzer

# LiteScope SoC ------------------------------------------------------------------------------------

class LiteScopeSoC(SoCMini):
    def __init__(self, platform):
        sys_clk_freq = int((1e9/platform.default_clk_period))

        # SoCMini ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, sys_clk_freq,
            csr_data_width = 32,
            with_uart      = True,
            uart_name      = "bridge",
            ident          = "Litescope example design",
            ident_version  = True,
        )

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        # Litescope IO -----------------------------------------------------------------------------
        self.submodules.io = LiteScopeIO(8)
        self.add_csr("io")
        for i in range(8):
            try:
                self.comb += platform.request("user_led", i).eq(self.io.output[i])
            except:
                pass

        # Litescope Analyzer -----------------------------------------------------------------------
        analyzer_groups = {}

        # Counter group
        counter = Signal(16, name_override="counter")
        zero    = Signal(name_override="zero")
        self.sync += counter.eq(counter + 1)
        self.comb += zero.eq(counter == 0)
        analyzer_groups[0] = [
            zero,
            counter,
        ]

        # Communication group
        analyzer_groups[1] = [
            platform.lookup_request("serial").tx,
            platform.lookup_request("serial").rx,
            self.bus.masters["uart_bridge"],
        ]

        # FSM group
        fsm = FSM(reset_state="STATE1")
        self.submodules += fsm
        fsm.act("STATE1",
            NextState("STATE2")
        )
        fsm.act("STATE2",
            NextState("STATE1")
        )
        analyzer_groups[2] = [
            fsm,
        ]

        # Analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_groups, 512, csr_csv="test/analyzer.csv")
        self.add_csr("analyzer")

default_subtarget = LiteScopeSoC
