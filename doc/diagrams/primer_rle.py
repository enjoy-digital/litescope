#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Run-length encoding: a run of identical samples is stored as one raw sample followed by a repeat
# word that holds the count; a sample that differs from the previous one is stored raw.

from primer_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 165)
    x0, w = 175, 52
    row_name(d, x0, 40, "Raw (9 words)")
    raw = ["A"]*6 + ["B"]*2 + ["C"]
    fill = {"A": COLOR_ACCENT, "B": COLOR_ACCENT_LIGHT, "C": COLOR_FILL}
    cells(d, x0, 40, [(w, s, fill[s]) for s in raw])
    row_name(d, x0, 110, "RLE (5 words)")
    cells(d, x0, 110, [(w, "A", COLOR_ACCENT), (w, "+5", COLOR_SHADE), (w, "B", COLOR_ACCENT_LIGHT),
        (w, "+1", COLOR_SHADE), (w, "C", COLOR_FILL)])
    d.add(Text(x0 + 2.5*w, 145, "raw sample: marker 0, repeat word: marker 1", size=12))
    return d
