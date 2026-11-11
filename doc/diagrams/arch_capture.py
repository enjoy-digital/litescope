#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# One capture as the driver runs it: register writes, storage state machine, hit and done, two
# columns per step (not to scale). The trigger is armed after FLUSH, as over a slow bridge.

from arch_helpers import *


def build():
    d = Diagram(CANVAS_WIDTH, 240)
    # Two columns per step, so that a register write can change a level in the middle of a step.
    w = Waves(d, x0=130, y0=10, cycles=20, cw=30.5, rh=36, label_x=118)
    w.bit("trigger_enable", "10000000011111111111")
    w.bit("storage_enable", "11110111111111111111")
    w.bus("storage FSM", ["IDLE"]*5 + ["FLUSH"]*3 + ["WAIT"]*5 + ["RUN"]*4 + ["IDLE"]*3,
        accent=["RUN"])
    w.bit("hit", "11100000000001111111")
    w.bit("storage_done", "11111000000000000111")
    steps = ["disarm", "load\nterms", "arm\nstorage", "flush", "arm\ntrigger", "pre-\ntrigger",
             "match", "post-\ntrigger", "done", "upload"]
    for i, s in enumerate(steps):
        w.marker(2*i + 0.5, s, dy=22)
    return d
