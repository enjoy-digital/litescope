#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# LiteScope at a glance: the analyzer samples probes of the design under test into block RAM; the
# host reads it through a bridge and litex_server, and the CLI or the driver writes a dump file
# that a waveform viewer opens.

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 250)
    d.add(Container(10, 15, 370, 170, title="FPGA (SoC)", title_pos="bl"))
    d.add(Container(470, 15, 280, 225, title="Host", title_pos="br"))
    dut    = d.add(Box(25,  40, 95, 60, label="Design\nunder test", fill=COLOR_FILL))
    scope  = d.add(Box(150, 40, 95, 60, label="Analyzer", fill=COLOR_ACCENT))
    bridge = d.add(Box(275, 40, 90, 60, label="Bridge", fill=COLOR_ACCENT_LIGHT))
    server = d.add(Box(485, 40, 100, 60, label="litex_server", fill=COLOR_FILL))
    cli    = d.add(Box(625, 40, 110, 60, label="CLI or\ndriver", fill=COLOR_ACCENT))
    viewer = d.add(Box(625, 150, 110, 50, label="Viewer", fill=COLOR_HARDWARE))
    d.add(Arrow((dut, "r"), (scope, "l"), kind="data", label="probes", label_pos=(135, 115)))
    d.add(Arrow((scope, "r"), (bridge, "l"), kind="data", heads="both", label="registers",
        label_pos=(260, 115)))
    d.add(Arrow((bridge, "r"), (server, "l"), kind="accent", heads="both", label="UART, JTAG,\nEthernet, PCIe",
        label_pos=(425, 125)))
    d.add(Arrow((server, "r"), (cli, "l"), kind="data", heads="both", label="TCP", label_pos=(605, 58)))
    d.add(Arrow((cli, "b"), (viewer, "t"), kind="data", label="dump file", label_side="left",
        label_pos=(672, 125), label_anchor="end"))
    return d
