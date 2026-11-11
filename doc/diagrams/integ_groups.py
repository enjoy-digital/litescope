#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Probe groups: each group is the concatenation of its probes, first probe in the low bits; the
# widest group sets the sample width and the narrower ones are padded with zeros. The group
# register selects one group at run time. Same groups as the example of the Integration chapter.

from primer_helpers import *


def build():
    d  = Diagram(CANVAS_WIDTH, 240)
    x0 = 110

    # Group 0, the widest: state, valid, ready, data (first probe in bit 0, drawn on the right).
    row_name(d, x0, 70, "group 0")
    cells(d, x0, 70, [(250, "source.data", COLOR_ACCENT_LIGHT), (60, "ready", COLOR_ACCENT_LIGHT),
        (60, "valid", COLOR_ACCENT_LIGHT), (90, "fsm state", COLOR_ACCENT_LIGHT)])
    # Group 1, narrower: count, error, then zero padding up to the width of group 0.
    row_name(d, x0, 130, "group 1")
    cells(d, x0, 130, [(250, "zero padding", COLOR_SHADE), (60, "error", COLOR_ACCENT_LIGHT),
        (150, "count", COLOR_ACCENT_LIGHT)])
    d.add(Text(x0 + 460, 34, "bit 0", size=12, anchor="end", color=COLOR_STROKE))
    span(d, x0, x0 + 460, 172, "data_width: widest group", side="below")

    # Mux.
    mux = d.add(Box(615, 45, 60, 110, label="Mux", fill=COLOR_ACCENT))
    d.add(Arrow((x0 + 460, 70), (615, 70), kind="data"))
    d.add(Arrow((x0 + 460, 130), (615, 130), kind="data"))
    d.add(Arrow((645, 225), mux.port("b"), kind="control", label="mux_value",
        label_pos=(690, 200)))
    d.add(Arrow(mux.port("r"), (750, 100), kind="accent", label="sample"))
    return d
