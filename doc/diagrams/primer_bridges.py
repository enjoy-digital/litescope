#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Getting data out: the host tools talk to litex_server over TCP; litex_server drives one bridge
# of the SoC (UART, JTAG, Ethernet or PCIe), which issues bus accesses to the analyzer registers.

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 300)
    d.add(Container(10, 15, 290, 270, title="Host", title_pos="bl"))
    d.add(Container(400, 15, 350, 270, title="FPGA (SoC)", title_pos="br"))
    cli    = d.add(Box(25, 113, 95, 60, label="CLI or\ndriver", fill=COLOR_ACCENT))
    server = d.add(Box(160, 35, 110, 216, label="litex_server", fill=COLOR_FILL))
    names  = [("UARTBone", "UART"), ("JTAGBone", "JTAG"), ("Etherbone", "Ethernet"), ("PCIe", "PCIe")]
    bridges = []
    for i, (n, link) in enumerate(names):
        y = 35 + i*58
        b = d.add(Box(420, y, 105, 42, label=n, fill=COLOR_ACCENT_LIGHT))
        bridges.append(b)
        d.add(Arrow((server.x + server.w, b.cy), (b, "l"), kind="accent", heads="both",
            label=link, label_pos=(350, b.cy - 12)))
    bus      = d.add(Box(555, 35, 50, 216, label="Bus", fill=COLOR_FILL))
    analyzer = d.add(Box(640, 113, 95, 60, label="Analyzer", fill=COLOR_ACCENT))
    for b in bridges:
        d.add(Arrow((b, "r"), (bus.x, b.cy), kind="data", heads="both"))
    d.add(Arrow((bus.x + bus.w, analyzer.cy), (analyzer, "l"), kind="data", heads="both"))
    d.add(Arrow((cli, "r"), (server, "l"), kind="data", heads="both", label="TCP", label_pos=(140, 131)))
    return d
