#
# This file is part of LiteScope.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Sample doubling in the dumps: each uploaded sample takes two time steps, scope_clk is 1 then 0
# within a sample, and scope_trig rises at time step `offset` (here offset 2, sample 1). Same data
# as the VCD excerpt of the File formats chapter (flag, count, four samples).

from svgdiag import *


def row_name(d, x, y, name):
    d.add(Text(x - 10, y, name, size=13, anchor="end"))


def cells(d, x, y, items, h=26):
    for w, label, fill in items:
        d.add(Box(x, y - h/2, w, h, label=label, radius=0, fill=fill, size=13))
        x += w


def wave(d, x, y, step, levels, h=16):
    """Square wave, one level per time step (1 high, 0 low)."""
    ys  = [y - h/2 if v else y + h/2 for v in levels]
    pts = [(x, ys[0])]
    for i in range(1, len(levels)):
        if ys[i] != ys[i - 1]:
            pts += [(x + i*step, ys[i - 1]), (x + i*step, ys[i])]
    pts.append((x + len(levels)*step, ys[-1]))
    d.add(Bus(pts, kind="control"))


def build():
    d = Diagram(CANVAS_WIDTH, 290)
    x0, p = 170, 70
    row_name(d, x0, 30, "Uploaded sample")
    cells(d, x0, 30, [(2*p, f"sample {i}", COLOR_ACCENT_LIGHT) for i in range(4)])
    row_name(d, x0, 75, "VCD time step")
    cells(d, x0, 75, [(p, f"#{i}", COLOR_FILL) for i in range(8)])
    row_name(d, x0, 120, "count")
    cells(d, x0, 120, [(2*p, str(i), COLOR_FILL) for i in range(4)])
    row_name(d, x0, 165, "scope_clk")
    wave(d, x0, 165, p, [1, 0]*4)
    row_name(d, x0, 210, "scope_trig")
    wave(d, x0, 210, p, [0, 0, 1, 1, 1, 1, 1, 1])
    d.add(Arrow((x0, 255), (x0 + 2*p, 255), kind="control", heads="both", label="offset = 2 steps",
        label_side="below"))
    for x in (x0 + 2*p,):
        d.add(Bus([(x, 222), (x, 245)], dash="2,3", color="#9a9a9a"))
    return d
