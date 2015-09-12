from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fsm import FSM, NextState
from migen.flow.actor import *
from migen.genlib.misc import Counter
from migen.actorlib.fifo import AsyncFIFO, SyncFIFO
from migen.flow.plumbing import Buffer
from migen.fhdl.specials import Memory


@ResetInserter()
@CEInserter()
class Counter(Module):
    def __init__(self, *args, increment=1, **kwargs):
        self.value = Signal(*args, **kwargs)
        self.width = flen(self.value)
        self.sync += self.value.eq(self.value+increment)


def data_layout(dw):
    return [("data", dw, DIR_M_TO_S)]


def hit_layout():
    return [("hit", 1, DIR_M_TO_S)]
