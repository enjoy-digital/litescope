#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# What a target adds to use LiteScope: the analyzer on the probes of the design, a bridge on the
# SoC bus, and the two files of the build that the host tools read (csr.csv, analyzer.csv).

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 325)

    # SoC.
    d.add(Container(20, 20, 590, 160, title="SoC"))
    design   = d.add(Box( 40, 55, 115, 50, label="Your design"))
    analyzer = d.add(Box(205, 55, 120, 50, label="Analyzer", fill=COLOR_ACCENT))
    bus      = d.add(Box(385, 55,  60, 50, label="Bus"))
    bridge   = d.add(Box(495, 55,  95, 50, label="Bridge", fill=COLOR_ACCENT_LIGHT))
    d.add(Arrow(design.port("r"), analyzer.port("l"), kind="accent", label="probes"))
    d.add(Arrow(analyzer.port("r"), bus.port("l"), kind="control", heads="both", label="registers"))
    d.add(Arrow(bus.port("r"), bridge.port("l"), kind="data", heads="both"))

    # Host.
    d.add(Container(625, 20, 130, 280, title="Host"))
    server = d.add(Box(637, 55, 105, 50, label="litex_server"))
    cli    = d.add(Box(637, 175, 105, 50, label="litescope_cli", fill=COLOR_ACCENT_LIGHT))
    d.add(Arrow(bridge.port("r"), server.port("l"), kind="data", heads="both"))
    d.add(Arrow(server.port("b"), cli.port("t"), kind="control", heads="both", label="TCP",
        label_side="right"))

    # Files written by the build.
    acsv = d.add(Box(205, 225, 120, 50, label="analyzer.csv", fill=COLOR_ACCENT_LIGHT))
    ccsv = d.add(Box(365, 225, 120, 50, label="csr.csv", fill=COLOR_ACCENT_LIGHT))
    d.add(Arrow(analyzer.port("b"), acsv.port("t"), kind="feedback", label="build",
        label_side="right"))
    d.add(Arrow(bus.port("b"), (bus.cx, 225), kind="feedback", label="build", label_side="right"))
    d.add(Arrow(ccsv.port("r"), cli.port("l", 0.5), kind="control", via=[(560, ccsv.cy), (560, cli.cy)], label="addresses",
        label_pos=(530, 238)))
    d.add(Arrow(acsv.port("b"), cli.port("b"), kind="control", via=[(acsv.cx, 310), (cli.cx, 310)],
        label="probes", label_pos=(450, 300)))
    return d
