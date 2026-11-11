#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# A sequence of two terms: the analyzer waits for term 1, then for term 2 from the next sample on;
# it fires when the last term matches. Drawn without the pipeline delays of the gateware.

from primer_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 200)
    x0, p = 150, 50
    vals  = ["0x03", "0x02", "0x05", "0x01", "0x07", "0x02", "0x04", "0x01", "0x02", "0x06", "0x03"]
    row_name(d, x0, 40, "Clock")
    clock(d, x0, 40, p, len(vals))
    row_name(d, x0, 80, "Probe")
    m1, m2 = 3, 5
    items = []
    for i, v in enumerate(vals):
        fill = COLOR_ACCENT if i in (m1, m2) else COLOR_FILL
        items.append((p, v, fill))
    cells(d, x0, 80, items)
    row_name(d, x0, 125, "Waiting for")
    cells(d, x0, 125, [((m1 + 1)*p, "term 1: 0x01", COLOR_ACCENT_LIGHT),
        ((m2 - m1)*p, "term 2: 0x02", COLOR_ACCENT_LIGHT), ((len(vals) - m2 - 1)*p, "fired", COLOR_ACCENT)])
    row_name(d, x0, 170, "Trigger")
    wave(d, x0, 170, p, [0]*(m2 + 1) + [1]*(len(vals) - m2 - 1))
    tick(d, x0 + (m2 + 1)*p, 60, 185)
    return d
