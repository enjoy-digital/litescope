from functools import reduce
from operator import and_

from litescope.common import *


class LiteScopeSumUnit(Module, AutoCSR):
    def __init__(self, ports):
        self.sinks = sinks = [stream.Endpoint(hit_layout()) for i in range(ports)]
        self.source = source = stream.Endpoint(hit_layout())

        self.prog_we = Signal()
        self.prog_adr = Signal(ports)
        self.prog_dat = Signal()

        mem = Memory(1, 2**ports)
        lut = mem.get_port()
        prog = mem.get_port(write_capable=True)
        self.specials += mem, lut, prog

        # # #

        # program port
        self.comb += [
            prog.we.eq(self.prog_we),
            prog.adr.eq(self.prog_adr),
            prog.dat_w.eq(self.prog_dat)
        ]

        # LUT port
        for i, sink in enumerate(sinks):
            self.comb += lut.adr[i].eq(sink.hit)

        # drive source
        self.comb += [
            source.valid.eq(reduce(and_, [sink.valid for sink in sinks])),
            source.hit.eq(lut.dat_r)
        ]
        for i, sink in enumerate(sinks):
            self.comb += sink.ready.eq(sink.valid & source.ready)


class LiteScopeSum(LiteScopeSumUnit, AutoCSR):
    def __init__(self, ports):
        LiteScopeSumUnit.__init__(self, ports)
        self._prog_we = CSR()
        self._prog_adr = CSRStorage(ports)
        self._prog_dat = CSRStorage()

        # # #

        self.comb += [
            self.prog_we.eq(self._prog_we.re & self._prog_we.r),
            self.prog_adr.eq(self._prog_adr.storage),
            self.prog_dat.eq(self._prog_dat.storage)
        ]


class LiteScopeTrigger(Module, AutoCSR):
    def __init__(self, dw):
        self.dw = dw
        self.ports = []
        self.sink = stream.Endpoint(data_layout(dw))
        self.source = stream.Endpoint(hit_layout())

    def add_port(self, port):
        setattr(self.submodules, "port"+str(len(self.ports)), port)
        self.ports.append(port)

    def do_finalize(self):
        self.submodules.sum = LiteScopeSum(len(self.ports))
        for i, port in enumerate(self.ports):
            # Note: port's ready is not used and supposed to be always 1
            self.comb += [
                port.sink.valid.eq(self.sink.valid),
                port.sink.data.eq(self.sink.data),
                self.sink.ready.eq(1),
                port.source.connect(self.sum.sinks[i])
            ]
        self.comb += self.sum.source.connect(self.source)
