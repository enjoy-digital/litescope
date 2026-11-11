#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Storage read path: sample FIFO (scope), clock-crossing FIFO, 32-bit converter, mem_data and
# mem_level registers, bridge to the host.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 260)
    h = 56
    fifo = d.add(Box(15,  50, 135, h, label="Sample FIFO\n(depth words)", fill=COLOR_ACCENT))
    cdc  = d.add(Box(200, 50, 125, h, label="CDC FIFO\n(4 words)", fill=COLOR_ACCENT_LIGHT))
    conv = d.add(Box(375, 50, 125, h, label="Converter\n(> 32 bits only)", fill=COLOR_ACCENT_LIGHT))
    data = d.add(Box(550, 50, 120, h, label="mem_data", fill=COLOR_ACCENT))
    lvl  = d.add(Box(550, 170, 120, h, label="mem_level"))
    host = d.add(Box(705, 50, 40, 176, label="Bus", fill=COLOR_HARDWARE))
    d.add(Arrow((fifo, "r"), (cdc, "l"), kind="data"))
    d.add(Arrow((cdc, "r"), (conv, "l"), kind="data"))
    d.add(Arrow((conv, "r"), (data, "l"), kind="data"))
    d.add(Arrow((data, "r"), (host.x, data.cy), kind="data"))
    d.add(Arrow((lvl, "r"), (host.x, lvl.cy)))
    d.add(Arrow((fifo, "b"), (lvl, "l"), via=[(fifo.cx, lvl.cy)], label="level (MultiReg)",
        label_pos=(420, lvl.cy - 12)))
    # Clock boundary through the clock-crossing FIFO, above and below it.
    d.add(Bus([(cdc.cx, 12), (cdc.cx, cdc.y)], dash="4,4"))
    d.add(Bus([(cdc.cx, cdc.y + cdc.h), (cdc.cx, lvl.cy - 24)], dash="4,4"))
    d.add(Text(cdc.cx - 10, 22, "scope", size=13, anchor="end", italic=True))
    d.add(Text(cdc.cx + 10, 22, "sys", size=13, anchor="start", italic=True))
    return d
