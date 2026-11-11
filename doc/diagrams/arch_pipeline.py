#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Analyzer pipeline: probe groups, mux, trigger, subsampler, optional RLE, storage, register bus.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 260)
    d.add(Container(125, 15, 620, 150, title="LiteScopeAnalyzer", title_pos="tl"))
    y, h = 75, 56
    grp  = d.add(Box(15,  y, 90,  h, label="Probe\ngroups", stack=2, fill=COLOR_ACCENT_LIGHT))
    mux  = d.add(Box(140, y, 90,  h, label="Mux"))
    trig = d.add(Box(250, y, 105, h, label="Trigger", fill=COLOR_ACCENT))
    sub  = d.add(Box(375, y, 115, h, label="Subsampler", fill=COLOR_ACCENT))
    rle  = d.add(Box(510, y, 95,  h, label="RLE\n(optional)", fill=COLOR_ACCENT_LIGHT))
    stor = d.add(Box(625, y, 105, h, label="Storage", fill=COLOR_ACCENT))
    bus  = d.add(Box(125, 200, 620, 40, label="Register bus (sys)"))
    for a, b in ((grp, mux), (mux, trig), (trig, sub), (sub, rle), (rle, stor)):
        d.add(Arrow((a, "r"), (b, "l"), kind="data"))
    for b in (mux, sub, rle):
        d.add(Arrow((b.cx, bus.y), (b, "b"), heads="end"))
    for b in (trig, stor):
        d.add(Arrow((b, "b"), (b.cx, bus.y), heads="both"))
    return d
