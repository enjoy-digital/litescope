#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Flow of a capture: the build writes analyzer.csv and csr.csv; the host then configures and arms
# the analyzer, waits for the trigger, uploads the samples and saves a dump.

from svgdiag import *


def build():
    d = Diagram(CANVAS_WIDTH, 250)
    d.add(Container(10, 10, 560, 95, title="Build time", title_pos="br"))
    d.add(Container(10, 135, 740, 105, title="Run time", title_pos="br"))
    soc  = d.add(Box(30,  32, 150, 50, label="Build the SoC", fill=COLOR_FILL))
    csv  = d.add(Box(230, 32, 140, 50, label="analyzer.csv\ncsr.csv", fill=COLOR_ACCENT_LIGHT))
    w, g, x0, y = 115, 30, 30, 155
    names = ["Configure", "Arm", "Trigger\nfires", "Upload", "Save dump"]
    fills = [COLOR_FILL, COLOR_ACCENT, COLOR_ACCENT, COLOR_ACCENT_LIGHT, COLOR_FILL]
    boxes = [d.add(Box(x0 + i*(w + g), y, w, 50, label=n, fill=f)) for i, (n, f) in enumerate(zip(names, fills))]
    d.add(Arrow((soc, "r"), (csv, "l"), kind="data"))
    d.add(Arrow((csv, "b"), (boxes[0], "t"), kind="data", via=[(csv.cx, 120), (boxes[0].cx, 120)]))
    for a, b in zip(boxes, boxes[1:]):
        d.add(Arrow((a, "r"), (b, "l"), kind="data"))
    return d
