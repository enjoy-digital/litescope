#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Run-length encoder state machine: BYPASS, RUN, EMIT_RAW.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 250)
    w = 150
    byp = state(d, 30,  100, "BYPASS",   w=w)
    run = state(d, 305, 100, "RUN",      w=w, fill=COLOR_ACCENT)
    raw = state(d, 580, 100, "EMIT_RAW", w=w, fill=COLOR_ACCENT_LIGHT)
    d.add(Arrow((byp, "r"), (run, "l"), label="post-trigger\nsample", label_pos=(242, 96)))
    d.add(Arrow((run.x + 110, run.y), (run.x + 40, run.y), via=[(run.x + 110, 40), (run.x + 40, 40)],
        label="same sample: count + 1", label_pos=(run.cx, 28)))
    d.add(Arrow((run, "r"), (raw, "l"), label="new value after\na run: emit count", label_pos=(517, 96)))
    d.add(Arrow((raw, "b"), (run.x + 110, run.y + run.h), via=[(raw.cx, 205), (run.x + 110, 205)],
        label="emit raw sample", label_pos=(570, 193)))
    d.add(Arrow((run.x + 40, run.y + run.h), (byp, "b"), via=[(run.x + 40, 205), (byp.cx, 205)],
        label="capture over", label_pos=(200, 193)))
    return d
