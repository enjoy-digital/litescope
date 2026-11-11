#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# One trigger term: the mask selects the bits that count, the value gives their expected level;
# the term matches when every selected bit of the sample equals the value.

from primer_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 215)
    x0, w = 200, 50
    sample = "10110110"
    mask   = "11110000"
    value  = "1011xxxx"
    for i in range(8):
        d.add(Text(x0 + i*w + w/2, 18, f"{7 - i}", size=12))
    rows = [("Sample", sample), ("Mask", mask), ("Value", value)]
    for r, (name, bits) in enumerate(rows):
        y = 50 + r*40
        row_name(d, x0, y, name)
        items = []
        for i, b in enumerate(bits):
            care = mask[i] == "1"
            fill = (COLOR_ACCENT if care else COLOR_SHADE) if name != "Mask" else COLOR_FILL
            items.append((w, b, fill))
        cells(d, x0, y, items)
    row_name(d, x0, 175, "Result")
    cells(d, x0, 175, [(4*w, "4 bits equal", COLOR_ACCENT), (4*w, "don't care", COLOR_SHADE)])
    d.add(Box(x0 + 8*w + 25, 162, 100, 26, label="match", fill=COLOR_ACCENT))
    d.add(Mark(x0 + 8*w + 25 + 88, 175))
    d.add(Arrow((x0 + 8*w, 175), (x0 + 8*w + 25, 175), kind="control"))
    return d
