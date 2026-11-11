#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Shared helpers of the core figures (arch_*.py, trig_*.py, rle_*.py, stor_*.py, io_*.py): bit
# fields, state boxes and synchronous waveforms. Not a figure (no build()).

from svgdiag import *

# Fields -------------------------------------------------------------------------------------------

def fields(d, x, y, cells, h=40, size=FONT_SIZE):
    """Adjoining square cells: cells is a list of (width, label, fill); returns the boxes."""
    boxes = []
    for w, label, fill in cells:
        boxes.append(d.add(Box(x, y, w, h, label=label, radius=0, fill=fill, size=size)))
        x += w
    return boxes

# States -------------------------------------------------------------------------------------------

def state(d, x, y, label, w=140, h=46, fill=COLOR_FILL):
    """One state of a state machine: a box of a fixed size, so that rows and columns line up."""
    return d.add(Box(x, y, w, h, label=label, fill=fill))

# Waveforms ----------------------------------------------------------------------------------------

def _dedup(pts):
    out = []
    for p in pts:
        if out and abs(out[-1][0] - p[0]) < 0.01 and abs(out[-1][1] - p[1]) < 0.01:
            continue
        out.append(p)
    # Merge collinear points (no zero-length segments).
    merged = [out[0]]
    for p in out[1:]:
        if len(merged) >= 2:
            a, b = merged[-2], merged[-1]
            if (abs(a[0] - b[0]) < 0.01 and abs(b[0] - p[0]) < 0.01) or \
               (abs(a[1] - b[1]) < 0.01 and abs(b[1] - p[1]) < 0.01):
                merged[-1] = p
                continue
        merged.append(p)
    return merged


class Waves:
    """Synchronous waveforms: a clock and named rows of bits or bus values, one column per step."""
    def __init__(self, d, x0=150, y0=20, cycles=10, cw=56, rh=34, label_x=135):
        self.d, self.x0, self.y, self.cycles, self.cw, self.rh = d, x0, y0, cycles, cw, rh
        self.label_x = label_x

    def _label(self, name):
        self.d.add(Text(self.label_x, self.y + self.rh/2, name, size=13, anchor="end"))

    def clock(self, name="clk"):
        self._label(name)
        lo, hi = self.y + self.rh - 8, self.y + 8
        pts = [(self.x0, lo)]
        for c in range(self.cycles):
            x = self.x0 + c*self.cw
            pts += [(x, hi), (x + self.cw/2, hi), (x + self.cw/2, lo), (x + self.cw, lo)]
        self.d.add(Bus(_dedup(pts)))
        self.y += self.rh

    def bit(self, name, values, color=None):
        """values: string of '0'/'1', one per column."""
        self._label(name)
        lo, hi = self.y + self.rh - 8, self.y + 8
        pts = []
        for c, v in enumerate(values):
            yv = hi if v == "1" else lo
            x  = self.x0 + c*self.cw
            pts += [(x, yv), (x + self.cw, yv)]
        self.d.add(Bus(_dedup(pts), color=color))
        self.y += self.rh

    def bus(self, name, values, accent=None, size=12):
        """values: list of labels (None: idle), one per column; equal neighbours are merged."""
        self._label(name)
        c = 0
        while c < len(values):
            n = 1
            while c + n < len(values) and values[c + n] == values[c]:
                n += 1
            v = values[c]
            x = self.x0 + c*self.cw
            if v is None:
                self.d.add(Bus([(x, self.y + self.rh/2), (x + n*self.cw, self.y + self.rh/2)],
                    color=COLOR_SHADE))
            else:
                fill = COLOR_ACCENT if (accent and v in accent) else COLOR_FILL
                self.d.add(Box(x + 2, self.y + 6, n*self.cw - 4, self.rh - 12, label=v, size=size,
                    radius=0, fill=fill))
            c += n
        self.y += self.rh

    def marker(self, column, label, dy=14):
        """Note below the waveforms, centered on a column ("\\n" for two lines)."""
        x = self.x0 + (column + 0.5)*self.cw
        self.d.add(Text(x, self.y + dy, label, size=12, color=COLOR_STROKE))

    def guide(self, column, top):
        """Dotted vertical line at the left edge of a column, from top to the current row."""
        x = self.x0 + column*self.cw
        self.d.add(Bus([(x, top), (x, self.y)], dash="2,3", color=COLOR_CYAN))
