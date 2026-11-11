#
# This file is part of LiteScope.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Host tools stack: litescope_cli or a Python script drive LiteScopeAnalyzerDriver, which reads the
# analyzer registers through RemoteClient, litex_server and a bridge of the SoC.

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 260)
    d.add(Container(10, 20, 430, 225, title="Host", title_pos="br"))
    d.add(Container(580, 20, 170, 225, title="FPGA", title_pos="br"))
    cli    = d.add(Box(25, 40, 120, 44, label="litescope_cli"))
    script = d.add(Box(25, 105, 120, 44, label="Python script"))
    files  = d.add(Box(25, 170, 120, 50, label="analyzer.csv\ncsr.csv", fill=COLOR_ACCENT_LIGHT))
    drv    = d.add(Box(180, 80, 100, 44, label="Driver", fill=COLOR_ACCENT))
    server = d.add(Box(310, 80, 115, 44, label="litex_server", fill=COLOR_ACCENT_LIGHT))
    bridge = d.add(Box(600, 80, 130, 44, label="Bridge"))
    ana    = d.add(Box(600, 165, 130, 44, label="Analyzer", fill=COLOR_ACCENT))
    d.add(Arrow((cli, "r"), (180, 95), via=[(160, 62), (160, 95)], kind="control"))
    d.add(Arrow((script, "r"), (180, 110), via=[(160, 127), (160, 110)], kind="control"))
    d.add(Arrow((files, "r"), (230, 124), via=[(230, 195)], kind="control"))
    d.add(Arrow((drv, "r"), (server, "l"), kind="data", heads="both", label="TCP",
        label_pos=(295, 70)))
    d.add(Arrow((server, "r"), (bridge, "l"), kind="accent", heads="both",
        label="UART, JTAG,\nEthernet, PCIe", label_pos=(510, 75)))
    d.add(Arrow((bridge, "b"), (ana, "t"), kind="data", heads="both", label="registers",
        label_side="right"))
    return d
