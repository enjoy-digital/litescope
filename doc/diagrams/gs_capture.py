#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# A real capture, drawn from its VCD: captures/gs_rising.vcd is the dump written by
# `litescope_cli -r simsoc_ibus_stb` on `litex_sim --with-analyzer` (Getting started chapter).
# Samples 28 to 47: ibus_stb rises at sample 30 (the trigger), then the CPU refills one line of its
# instruction cache, eight words from word address 0x6b0, one ack every other cycle.

import re
from pathlib import Path

from primer_helpers import *

VCD    = Path(__file__).resolve().parent/"captures"/"gs_rising.vcd"
FIRST  = 28 # First sample drawn.
COUNT  = 20 # Samples drawn.
MATCH  = 30 # Sample where ibus_stb is first seen high (read from the VCD, checked below).


def read_vcd(path):
    """Value of every variable at each sample: {name: [v0, v1, ...]}. A LiteScope dump writes each
    sample on two time steps (scope_clk high then low), so sample n is time step 2n."""
    ids, steps, cur, t = {}, {}, {}, None
    for line in path.read_text().splitlines():
        line = line.strip()
        m = re.match(r"\$var\s+\w+\s+\d+\s+(\S+)\s+(\S+)", line)
        if m:
            ids[m.group(1)] = m.group(2)
        elif line.startswith("#"):
            if t is not None:
                steps[t] = dict(cur)
            t = int(line[1:])
        elif t is not None and line.startswith("b"):
            v, i = line[1:].split()
            cur[ids[i]] = None if "x" in v else int(v, 2)
    steps[t] = dict(cur)
    return {n: [steps[2*s].get(n) for s in range(t//2 + 1)] for n in ids.values()}


def runs(values):
    """[(start, length, value)] of the runs of equal values."""
    out = []
    for i, v in enumerate(values):
        if out and out[-1][2] == v:
            out[-1][1] += 1
        else:
            out.append([i, 1, v])
    return out


def build():
    v = read_vcd(VCD)
    sl = lambda name: v["simsoc_" + name][FIRST:FIRST + COUNT]
    assert sl("ibus_stb")[MATCH - FIRST - 1:MATCH - FIRST + 1] == [0, 1]

    d  = Diagram(CANVAS_WIDTH, 330)
    x0 = 110
    p  = (CANVAS_WIDTH - x0 - 30)/COUNT
    xs = lambda s: x0 + (s - FIRST)*p

    # Sample numbers.
    row_name(d, x0, 40, "sample")
    for s in range(FIRST, FIRST + COUNT, 2):
        d.add(Text(xs(s) + p/2, 40, str(s), size=12, color=COLOR_STROKE))

    # Control lines.
    y = 80
    for name in ("ibus_cyc", "ibus_stb", "ibus_ack"):
        row_name(d, x0, y, name)
        wave(d, x0, y, p, sl(name), kind="data" if name == "ibus_stb" else "control")
        y += 40

    # Address and read data, one cell per run of equal values.
    for name, fmt in (("ibus_adr", "0x{:x}"), ("ibus_dat_r", "{:08x}")):
        row_name(d, x0, y, name)
        values = sl(name)
        skip   = 0
        if name == "ibus_dat_r":
            # The read data means something from the first ack on: shade the samples before it.
            skip = sl("ibus_ack").index(1)
            d.add(Box(x0, y - 13, skip*p, 26, radius=0, fill=COLOR_SHADE))
        for start, n, val in runs(values[skip:]):
            start += skip
            fill  = COLOR_ACCENT_LIGHT if name == "ibus_adr" and FIRST + start >= MATCH else COLOR_FILL
            label = fmt.format(val) if n*p >= text_width(fmt.format(val), 12) + 4 else ""
            d.add(Box(xs(FIRST + start), y - 13, n*p, 26, label=label, radius=0, fill=fill, size=12))
        y += 45

    # Trigger marker.
    tick(d, xs(MATCH), 58, y - 18)
    d.add(Text(xs(MATCH), y, "trigger: ibus_stb rises", size=13, color=COLOR_STROKE))
    cyc = sl("ibus_cyc")
    end = FIRST + next(i for i in range(MATCH - FIRST, COUNT) if cyc[i] == 0)
    acks = sum(sl("ibus_ack"))
    span(d, xs(MATCH), xs(end), y + 30, f"cache line refill: {acks} words", side="below")
    d.height = y + 60
    return d
