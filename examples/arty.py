#!/usr/bin/env python3

#
# This file is part of LiteScope.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Use:
# ./arty.py --build --load
# lxserver --udp (for LiteScope over UDP)
# litescope_cli: will trigget an immediate capture!
# litescope_cli --help: list the available trigger option.
# litescope_cli --list: list the signals that can be used as triggers.
# litescope_cli -v main_count 128: trigger on count value == 128.
# litescope_cli -r litescopesoc_cpu_ibus_stb: trigger in ibus_stb rising edge
# For more information: https://github.com/enjoy-digital/litex/wiki/Use-LiteScope-To-Debug-A-SoC

import os
import argparse

from migen import *

from litex.boards.platforms import arty
from litex.boards.targets.arty import *

from litescope import LiteScopeAnalyzer

# LiteScopeSoC -------------------------------------------------------------------------------------

class LiteScopeSoC(BaseSoC):
    def __init__(self):
        platform = arty.Platform()

        # BaseSoC ----------------------------------------------------------------------------------
        BaseSoC.__init__(self,
            integrated_rom_size = 0x8000,
            with_etherbone      = True,
        )

        # LiteScope Analyzer -----------------------------------------------------------------------
        count = Signal(8)
        self.sync += count.eq(count + 1)
        analyzer_signals = [
            self.cpu.ibus,
            count,
        ]
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
            depth        = 1024,
            clock_domain = "sys",
            csr_csv      = "analyzer.csv")
        self.add_csr("analyzer")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteScope example on Arty A7")
    parser.add_argument("--build", action="store_true", help="Build bitstream")
    parser.add_argument("--load",  action="store_true", help="Load bitstream")
    args = parser.parse_args()

    soc     = LiteScopeSoC()
    builder = Builder(soc, csr_csv="csr.csv")
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
