from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.stream import *


def data_layout(dw):
    return [("data", dw, DIR_M_TO_S)]


def hit_layout():
    return [("hit", 1, DIR_M_TO_S)]
