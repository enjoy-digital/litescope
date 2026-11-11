#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Trigger: term registers, term memory (AsyncFIFO), register stage, comparator, hit from the
# empty memory.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 330)
    h = 56
    regs = d.add(Box(15,  50, 150, h, label="Term registers\n(sys)"))
    mem  = d.add(Box(225, 50, 160, h, label="Term memory\n(AsyncFIFO)", fill=COLOR_ACCENT))
    cmp_ = d.add(Box(455, 50, 140, h, label="Compare\nunder mask", fill=COLOR_ACCENT))
    reg  = d.add(Box(455, 170, 140, h, label="Register\nstage"))
    emp  = d.add(Box(225, 260, 160, h, label="Memory empty", fill=COLOR_ACCENT_LIGHT))
    out  = d.add(Box(640, 170, 105, h, label="Subsampler", fill=COLOR_ACCENT_LIGHT))
    d.add(Arrow((regs, "r"), (mem, "l"), kind="data", label="push", label_pos=(195, 66)))
    d.add(Arrow((mem, "r"), (cmp_, "l"), kind="data", label="mask, value", label_pos=(420, 66)))
    d.add(Arrow((cmp_, "t"), (mem, "t"), via=[(cmp_.cx, 20), (mem.cx, 20)], label="pop on match",
        label_pos=(415, 10)))
    d.add(Arrow((15, reg.cy), (reg, "l"), kind="data", label="probes", label_pos=(60, reg.cy - 12)))
    d.add(Arrow((reg, "t"), (cmp_, "b"), kind="data", label="sample", label_pos=(570, 138)))
    d.add(Arrow((reg, "r"), (out, "l"), kind="data", label="data", label_pos=(617, reg.cy - 12)))
    d.add(Arrow((mem, "b"), (emp, "t")))
    d.add(Arrow((emp, "r"), (out, "b"), via=[(out.cx, emp.cy)], label="hit",
        label_pos=(640, emp.cy - 10)))
    return d
