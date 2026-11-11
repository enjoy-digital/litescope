#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Subsampling by 4: one sample is kept every 4 clock cycles; a pulse that starts and ends between
# two kept samples never reaches the memory.

from primer_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 205)
    x0, p, n = 150, 45, 12
    row_name(d, x0, 40, "Clock")
    clock(d, x0, 40, p, n)
    row_name(d, x0, 85, "Slow signal")
    wave(d, x0, 85, p, [0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0])
    row_name(d, x0, 125, "Short pulse")
    wave(d, x0, 125, p, [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0])
    d.add(Text(x0 + 5.5*p, 101, "missed", size=12))
    row_name(d, x0, 170, "Kept (N = 4)")
    for k in range(0, n, 4):
        cells(d, x0 + k*p, 170, [(p, f"S{k//4}", COLOR_ACCENT)])
        tick(d, x0 + k*p, 30, 157)
    return d
