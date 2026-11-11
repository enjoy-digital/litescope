#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Stored word with RLE: marker bit (MSB), then a raw sample or a repeat count.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 190)
    x0 = 150
    d.add(Text(x0 + 30, 22, "MSB", size=12, color=COLOR_STROKE))
    d.add(Text(745, 22, "bit 0", size=12, anchor="end", color=COLOR_STROKE))
    d.add(Text(135, 60, "Raw word", size=14, anchor="end"))
    fields(d, x0, 40, [
        (60,  "0",                COLOR_ACCENT),
        (535, "sample (data_width bits, zero-extended)", COLOR_FILL),
    ])
    d.add(Text(135, 120, "Repeat word", size=14, anchor="end"))
    fields(d, x0, 100, [
        (60,  "1",       COLOR_ACCENT),
        (335, "zero",    COLOR_SHADE),
        (200, "count",   COLOR_ACCENT_LIGHT),
    ])
    d.add(Text(x0 + 495, 160, "bits_for(rle_length - 1) bits", size=12, color=COLOR_STROKE))
    return d
