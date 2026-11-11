#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# End-to-end simulation test (test/test_sim.py): the driver reaches the analyzer of a Verilator
# SoC through the BIOS console, which the test drives over a TCP socket (serial2tcp).

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 290)
    d.add(Container(10, 10, 740, 110, title="pytest process", title_pos="bl"))
    d.add(Container(10, 170, 740, 110, title="Verilator simulation", title_pos="bl"))
    driver  = d.add(Box(40,  35, 130, 50, label="Driver", fill=COLOR_ACCENT_LIGHT))
    builder = d.add(Box(315, 35, 130, 50, label="CSRBuilder", fill=COLOR_FILL))
    access  = d.add(Box(590, 35, 130, 50, label="BIOSMemAccess", fill=COLOR_FILL))
    serial  = d.add(Box(590, 195, 130, 50, label="serial2tcp", fill=COLOR_FILL))
    bios    = d.add(Box(315, 195, 130, 50, label="BIOS on CPU", fill=COLOR_FILL))
    scope   = d.add(Box(40,  195, 130, 50, label="Analyzer", fill=COLOR_ACCENT))
    d.add(Arrow((driver, "r"), (builder, "l"), kind="data", heads="both", label="registers",
        label_pos=(242, 48)))
    d.add(Arrow((builder, "r"), (access, "l"), kind="data", heads="both", label="read, write",
        label_pos=(517, 48)))
    d.add(Arrow((access, "b"), (serial, "t"), kind="accent", heads="both", label="TCP",
        label_pos=(680, 145)))
    d.add(Arrow((serial, "l"), (bios, "r"), kind="data", heads="both", label="mem_read/write",
        label_pos=(517, 208)))
    d.add(Arrow((bios, "l"), (scope, "r"), kind="data", heads="both", label="CSR bus",
        label_pos=(242, 208)))
    return d
