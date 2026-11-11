#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Clock domains of the analyzer: registers in sys, pipeline in scope, and the four kinds of
# crossings between them.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 360)
    d.add(Container(15,  15, 220, 330, title="sys", title_pos="bl"))
    d.add(Container(525, 15, 220, 330, title="scope", title_pos="br"))
    w, h = 180, 50
    rows = [
        ("Control\nregisters",   "Mux, trigger, subsampler,\nRLE, storage", "MultiReg",                True),
        ("Term\nregisters",      "Trigger\nterm memory",          "AsyncFIFO (trigger_depth)", True),
        ("Status\nregisters",    "Trigger and\nstorage state",     "MultiReg",                False),
        ("mem_data\nregister",   "Storage\nFIFO",                  "AsyncFIFO (4 words)",       False),
    ]
    for i, (left, right, label, to_scope) in enumerate(rows):
        y = 35 + i*72
        l = d.add(Box(35,  y, w, h, label=left))
        r = d.add(Box(545, y, w, h, label=right, fill=COLOR_ACCENT))
        a, b = ((l, "r"), (r, "l")) if to_scope else ((r, "l"), (l, "r"))
        d.add(Arrow(a, b, kind="data" if "FIFO" in label else "control", label=label,
            label_pos=(380, y + h/2 - 12)))
    # Clock boundary, interrupted around the arrow labels.
    top = 25
    for i in range(len(rows)):
        y = 35 + i*72
        d.add(Bus([(380, top), (380, y + 3)], dash="4,4"))
        top = y + 23
    d.add(Bus([(380, top), (380, 335)], dash="4,4"))
    return d
