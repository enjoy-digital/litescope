#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Capture window: before the trigger the memory keeps only the most recent samples (the
# pre-trigger window, offset); after it, it fills up to the capture length, at most the depth.

from primer_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 255)
    x0 = 130
    # Time axis of the probe stream.
    row_name(d, x0, 60, "Samples")
    old, pre, post = 150, 150, 210
    cells(d, x0, 60, [(old, "dropped", COLOR_SHADE), (pre, "pre-trigger", COLOR_ACCENT_LIGHT),
        (post, "post-trigger", COLOR_ACCENT)])
    t = x0 + old + pre
    tick(d, t, 30, 200)
    d.add(Text(t, 18, "trigger", size=13))
    d.add(Arrow((x0, 95), (x0 + old + pre + post + 30, 95), kind="control", label="time",
        label_pos=(x0 + old + pre + post + 10, 82)))
    span(d, x0 + old, t, 120, "offset", side="below")
    # Memory content after the capture.
    row_name(d, x0, 175, "Memory")
    cells(d, x0 + old, 175, [(pre, "pre-trigger", COLOR_ACCENT_LIGHT), (post, "post-trigger", COLOR_ACCENT)])
    cells(d, x0 + old + pre + post, 175, [(60, "", COLOR_FILL)])
    span(d, x0 + old, x0 + old + pre + post, 215, "length", side="below")
    span(d, x0 + old, x0 + old + pre + post + 60, 148, "depth")
    return d
