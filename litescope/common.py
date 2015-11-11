from migen import *
from migen.genlib.fsm import FSM, NextState
from migen.fhdl.specials import Memory

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.stream import *


@ResetInserter()
@CEInserter()
class Counter(Module):
    def __init__(self, *args, increment=1, **kwargs):
        self.value = Signal(*args, **kwargs)
        self.width = len(self.value)
        self.sync += self.value.eq(self.value+increment)


def data_layout(dw):
    return [("data", dw, DIR_M_TO_S)]


def hit_layout():
    return [("hit", 1, DIR_M_TO_S)]
