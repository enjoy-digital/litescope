#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# A two-term sequence (a rising edge of x as the driver builds it): the first term is consumed on
# its match, the second is compared from the next sample, hit follows the last match.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 200)
    w = Waves(d, x0=130, y0=10, cycles=10, cw=60, rh=36, label_x=118)
    w.clock("scope clock")
    w.bit("x", "1100011100")
    w.bus("term compared", ["x = 0"]*3 + ["x = 1"]*3 + [None]*4, accent=["x = 1"])
    w.bit("hit", "0000001111")
    w.marker(2, "term 1\nmatch", dy=22)
    w.marker(5, "term 2\nmatch", dy=22)
    w.marker(6, "first hit\nsample", dy=22)
    return d
