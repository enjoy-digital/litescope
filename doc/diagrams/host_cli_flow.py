#
# This file is part of LiteScope.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# What one litescope_cli capture does, in order, and its three exit codes.

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 210)
    w, h, y, gap = 105, 50, 30, 21
    labels = ["Read\nanalyzer.csv", "Configure\ngroup, RLE", "Load terms\nand arm",
        "Wait for\ntrigger", "Upload\nwords", "Save\ndump"]
    boxes = []
    for i, label in enumerate(labels):
        fill = COLOR_ACCENT if i in (2, 3) else COLOR_FILL
        boxes.append(d.add(Box(10 + i*(w + gap), y, w, h, label=label, fill=fill)))
    for a, b in zip(boxes, boxes[1:]):
        d.add(Arrow((a, "r"), (b, "l"), kind="data"))
    ok      = d.add(Box(640, 140, 105, 44, label="exit 0"))
    timeout = d.add(Box(388, 140, 105, 44, label="exit 2"))
    error   = d.add(Box(10, 140, 105, 44, label="exit 1"))
    d.add(Arrow((boxes[5], "b"), (ok, "t"), kind="control"))
    d.add(Arrow((boxes[3], "b"), (timeout, "t"), kind="control",
        label="--timeout", label_pos=(483, 112)))
    d.add(Arrow((boxes[0], "b"), (error, "t"), kind="control", label="any error",
        label_pos=(105, 112), label_anchor="start"))
    return d
