#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Shared helpers of the primer figures (no build(): not a figure).
#
# Timing rows: one horizontal row per signal (a name on the left, adjoining cells or a digital
# waveform on a common time axis), clock rows drawn as square waves, spans (double-headed arrows)
# and dotted time markers.

from svgdiag import *


def row_name(d, x, y, name, size=13):
    """Signal name, right-aligned, left of a row whose cells start at x and are centred on y."""
    d.add(Text(x - 10, y, name, size=size, anchor="end"))


def cells(d, x, y, items, h=26, size=13):
    """Row of adjoining square cells: items is a list of (width, label, fill); fill None = gap."""
    out = []
    for w, label, fill in items:
        if fill is not None:
            out.append(d.add(Box(x, y - h/2, w, h, label=label, radius=0, fill=fill, size=size)))
        x += w
    return out


def wave(d, x, y, period, levels, h=16, kind="control"):
    """Digital waveform: levels is a list of 0/1, one per period, starting at x."""
    hi, lo = y - h/2, y + h/2
    pts = [(x, lo if levels[0] == 0 else hi)]
    for i, v in enumerate(levels):
        yy = hi if v else lo
        if abs(pts[-1][1] - yy) > 0.5:
            pts.append((x + i*period, yy))
        pts.append((x + (i + 1)*period, yy))
    clean = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - clean[-1][0]) > 0.5 or abs(p[1] - clean[-1][1]) > 0.5:
            clean.append(p)
    # Merge collinear horizontal points.
    out = [clean[0]]
    for p in clean[1:]:
        if len(out) >= 2 and abs(out[-1][1] - p[1]) < 0.5 and abs(out[-2][1] - p[1]) < 0.5:
            out[-1] = p
        else:
            out.append(p)
    d.add(Bus(out, kind=kind))


def clock(d, x, y, period, n, h=16):
    """Square wave of n periods starting at x, rising edge at the start of each period."""
    wave(d, x, y, period/2, [1, 0]*n, h=h)


def span(d, x0, x1, y, label, kind="control", side="above"):
    """Double-headed horizontal arrow from x0 to x1 at y, with its label above or below."""
    d.add(Arrow((x0, y), (x1, y), kind=kind, heads="both", label=label, label_side=side))


def tick(d, x, y0, y1):
    """Dotted vertical marker (a time reference) from y0 to y1."""
    d.add(Bus([(x, y0), (x, y1)], dash="2,3", color="#9a9a9a"))
