from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.interconnect.stream import *


def data_layout(dw):
    return [("data", dw)]


def hit_layout():
    return [("hit", 1)]
