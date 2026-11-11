#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# IO probe: input signal resynchronized into the in register, out register driving the output
# signal, both read and written by the host through the register bus.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 230)
    d.add(Container(215, 15, 300, 200, title="LiteScopeIO", title_pos="br"))
    h = 56
    des  = d.add(Box(15,  40,  150, 150, label="Design", fill=COLOR_ACCENT_LIGHT))
    rin  = d.add(Box(260, 40,  210, h, label="in register\n(MultiReg)", fill=COLOR_ACCENT))
    rout = d.add(Box(260, 120, 210, h, label="out register", fill=COLOR_ACCENT))
    bus  = d.add(Box(575, 40,  170, 136, label="Register bus\nand bridge", fill=COLOR_HARDWARE))
    d.add(Arrow((des.x + des.w, rin.cy), (rin, "l"), kind="data", label="input",
        label_pos=(190, rin.cy - 12)))
    d.add(Arrow((rout, "l"), (des.x + des.w, rout.cy), kind="data", label="output",
        label_pos=(190, rout.cy - 12)))
    d.add(Arrow((rin, "r"), (bus.x, rin.cy), label="read", label_pos=(545, rin.cy - 10)))
    d.add(Arrow((bus.x, rout.cy), (rout, "r"), label="write", label_pos=(545, rout.cy - 10)))
    return d
