#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Storage state machine: IDLE, FLUSH, WAIT, RUN, with what each state does to the sample FIFO.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 170)
    w, y = 140, 60
    xs = [20, 213, 406, 599]
    names = ["IDLE", "FLUSH", "WAIT", "RUN"]
    notes = ["drain to read path", "drop everything", "keep offset words", "fill up to length"]
    fills = [COLOR_FILL, COLOR_FILL, COLOR_ACCENT_LIGHT, COLOR_ACCENT]
    boxes = [state(d, x, y, n, w=w, fill=f) for x, n, f in zip(xs, names, fills)]
    for b, n in zip(boxes, notes):
        d.add(Text(b.cx, b.y + b.h + 16, n, size=13, color=COLOR_STROKE))
    labels = ["enable rises", "depth cycles", "hit"]
    for a, b, l in zip(boxes, boxes[1:], labels):
        d.add(Arrow((a, "r"), (b, "l"), label=l, label_pos=((a.x + a.w + b.x)/2, y - 12)))
    run, idle = boxes[3], boxes[0]
    d.add(Arrow((run, "t"), (idle, "t"), via=[(run.cx, 22), (idle.cx, 22)], label="level reaches length",
        label_pos=(380, 12)))
    return d
