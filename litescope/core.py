from migen import *
from migen.genlib.cdc import MultiReg

from litex.build.tools import write_to_file

from litex.soc.interconnect.csr import *
from litex.soc.cores.gpio import GPIOInOut
from litex.soc.interconnect import stream


class LiteScopeIO(Module, AutoCSR):
    def __init__(self, dw):
        self.dw = dw
        self.input = Signal(dw)
        self.output = Signal(dw)

        # # #

        self.submodules.gpio = GPIOInOut(self.input, self.output)

    def get_csrs(self):
        return self.gpio.get_csrs()


def core_layout(dw, hw=1):
    return [("data", dw), ("hit", hw)]

# produces a pulse on the rising edge of sink
# when neg=1, produce a pulse on falling edge of sink
class EdgeDetect(Module):
    def __init__(self, falling=0):
        self.sink = sink = Signal()
        sink_r = Signal()
        self.source = source = Signal()

        self.sync += [
            sink_r.eq(sink)
        ]
        self.comb += [
            source.eq(~(sink_r ^ falling) & (sink ^ falling))
        ]


class FrontendTrigger(Module, AutoCSR):
    def __init__(self, dw, edges=False):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(dw)
        self.mask = CSRStorage(dw)

        # API: if a bit has edge_enable, then the "value" field selects the edge type (0 = pos, 1 = neg)
        # and the "mask" field selects if the edge matters or not
        # if the edge_enable bit is not set, then the "value" field selects the value to look for as a match,
        # and the "mask" field selects if the level matters or not
        if edges:
            self.edge_enable = CSRStorage(dw)

        # # #

        value = Signal(dw)
        mask = Signal(dw)

        self.specials += [
            MultiReg(self.value.storage, value),
            MultiReg(self.mask.storage, mask)
        ]
        if edges:
            edge_enable = Signal(dw)
            self.specials += [
                MultiReg(self.edge_enable.storage, edge_enable),
            ]
            edge_hit = Signal(dw)
            for i in range(0, dw):
                ed_bit = EdgeDetect(value[i])
                self.submodules += ed_bit
                self.comb += [
                    ed_bit.sink.eq(self.sink.data[i]),
                    edge_hit[i].eq(ed_bit.source),
                ]

        self.comb += self.sink.connect(self.source)
        if edges:
            hit_masked = Signal(dw)
            for i in range(0, dw):
                self.comb += [
                   If(edge_enable[i],
                      hit_masked[i].eq(edge_hit[i] & mask[i])
                   ).Else(
                      hit_masked[i].eq((self.sink.data[i] == value[i]) & mask[i])
                   ),
                ]
            self.comb += self.source.hit.eq(hit_masked != 0)
        else:
            self.comb += self.source.hit.eq((self.sink.data & mask) == value)


class FrontendSubSampler(Module, AutoCSR):
    def __init__(self, dw):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(16)

        # # #

        value = Signal(16)
        self.specials += MultiReg(self.value.storage, value)

        counter = Signal(16)
        done = Signal()

        self.sync += \
            If(self.source.ready,
                If(done,
                    counter.eq(0)
                ).Elif(self.sink.valid,
                    counter.eq(counter + 1)
                )
            )

        self.comb += [
            done.eq(counter == value),
            self.sink.connect(self.source, omit=set(["valid"])),
            self.source.valid.eq(self.sink.valid & done)
        ]


class AnalyzerMux(Module, AutoCSR):
    def __init__(self, dw, n):
        self.sinks = [stream.Endpoint(core_layout(dw)) for i in range(n)]
        self.source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(bits_for(n))

        # # #

        cases = {}
        for i in range(n):
            cases[i] = self.sinks[i].connect(self.source)
        self.comb += Case(self.value.storage, cases)


class AnalyzerFrontend(Module, AutoCSR):
    def __init__(self, dw, cd_ratio, edges=False):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw*cd_ratio))

        # # #

        self.submodules.buffer = stream.Buffer(core_layout(dw))
        self.submodules.trigger = FrontendTrigger(dw, edges)
        self.submodules.subsampler = FrontendSubSampler(dw)
        self.submodules.converter = stream.StrideConverter(
                core_layout(dw, 1), core_layout(dw*cd_ratio, cd_ratio))
        self.submodules.fifo = ClockDomainsRenamer(
            {"write": "sys", "read": "new_sys"})(
                stream.AsyncFIFO(core_layout(dw*cd_ratio, cd_ratio), 8))
        self.submodules.pipeline = stream.Pipeline(
            self.sink,
            self.buffer,
            self.trigger,
            self.subsampler,
            self.converter,
            self.fifo,
            self.source)


class AnalyzerStorage(Module, AutoCSR):
    def __init__(self, dw, depth, cd_ratio):
        self.sink = stream.Endpoint(core_layout(dw, cd_ratio))

        self.start = CSR()
        self.restart = CSR()
        self.length = CSRStorage(bits_for(depth))
        self.offset = CSRStorage(bits_for(depth))

        self.idle = CSRStatus()
        self.wait = CSRStatus()
        self.run  = CSRStatus()
        self.readout = CSRStatus()

        self.mem_flush = CSR()
        self.mem_valid = CSRStatus()
        self.mem_ready = CSR()
        self.mem_data = CSRStatus(dw)

        # # #

        mem = stream.SyncFIFO([("data", dw)], depth//cd_ratio, buffered=True)
        self.submodules += ResetInserter()(mem)
        self.comb += mem.reset.eq(self.mem_flush.re)

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            self.idle.status.eq(1),
            If(self.start.re,
                NextState("WAIT")
            ),
            self.sink.ready.eq(1),
            mem.source.ready.eq(self.mem_ready.re & self.mem_ready.r)
            # readout happens in the IDLE state
            # after every word is read, litex_server drops a 1 in mem_ready, which causes .re and .r to become true
            # .re is true for just one pulse, so this increments through the read pointer
        )
        fsm.act("WAIT",
            self.wait.status.eq(1),
            self.sink.connect(mem.sink, omit=set(["hit"])),
            If(self.sink.valid & (self.sink.hit != 0),
                NextState("RUN")
            ),
            mem.source.ready.eq(mem.level >= self.offset.storage)
            # in the wait state: 1) fill the FIFO until we hit the offset level
            # 2) once we've hit the offset level, if we go over it, read a value out
            # this keeps the FIFO "spinning" until the trigger is hit
        )
        fsm.act("RUN",
            self.run.status.eq(1),
            self.sink.connect(mem.sink, omit=set(["hit"])),
            If(~mem.sink.ready | (mem.level >= self.length.storage),
                NextState("READOUT"),
                mem.source.ready.eq(1)
               # i'm not sure why this happens, but the way I read it is this will cause
               # a word to be read out of the FIFO immediately, but then as we enter the
               # IDLE state no more words are read out.
            )
        )
        # added a "READOUT" state, in order to send feedback that in fact a trigger
        # was hit and data was fetched prior to idling
        fsm.act("READOUT",
                self.readout.status.eq(1),
                If(self.restart.re,
                   NextState("IDLE")
                   ),
                self.sink.ready.eq(0), # block the pipe during readout
                mem.source.ready.eq(self.mem_ready.re & self.mem_ready.r)

                )
        self.comb += [
            self.mem_valid.status.eq(mem.source.valid),
            self.mem_data.status.eq(mem.source.data)
        ]


def _format_groups(groups):
    if not isinstance(groups, dict):
        groups = {0 : groups}
    new_groups = {}
    for n, signals in groups.items():
        if not isinstance(signals, list):
            signals = [signals]

        split_signals = []
        for s in signals:
            if isinstance(s, Record):
                split_signals.extend(s.flatten())
            else:
                split_signals.append(s)
        new_groups[n] = split_signals
    return new_groups


class LiteScopeAnalyzer(Module, AutoCSR):
    def __init__(self, groups, depth, cd="sys", cd_ratio=1, edges=False):
        self.groups = _format_groups(groups)
        self.dw = max([sum([len(s) for s in g]) for g in self.groups.values()])

        self.depth = depth
        self.cd_ratio = cd_ratio

        # # #

        self.submodules.mux = AnalyzerMux(self.dw, len(self.groups))
        for i, signals in self.groups.items():
            self.comb += [
                self.mux.sinks[i].valid.eq(1),
                self.mux.sinks[i].data.eq(Cat(signals))
            ]
        self.submodules.frontend = ClockDomainsRenamer(
            {"sys": cd, "new_sys": "sys"})(AnalyzerFrontend(self.dw, cd_ratio, edges))
        self.submodules.storage = AnalyzerStorage(self.dw*cd_ratio, depth, cd_ratio)
        self.comb += [
            self.mux.source.connect(self.frontend.sink),
            self.frontend.source.connect(self.storage.sink)
        ]

    def export_csv(self, vns, filename):
        def format_line(*args):
            return ",".join(args) + "\n"
        r = format_line("config", "None", "dw", str(self.dw))
        r += format_line("config", "None", "depth", str(self.depth))
        r += format_line("config", "None", "cd_ratio", str(int(self.cd_ratio)))
        for i, signals in self.groups.items():
            for s in signals:
                r += format_line("signal", str(i), vns.get_name(s), str(len(s)))
        write_to_file(filename, r)
