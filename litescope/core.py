from migen import *
from migen.genlib.misc import WaitTimer
from migen.genlib.cdc import MultiReg, PulseSynchronizer

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


def core_layout(dw):
    return [("data", dw), ("hit", 1)]


class FrontendTrigger(Module, AutoCSR):
    def __init__(self, dw):
        self.sink = sink = stream.Endpoint(core_layout(dw))
        self.source = source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(dw)
        self.mask = CSRStorage(dw)

        # # #

        value = Signal(dw)
        mask = Signal(dw)
        self.specials += [
            MultiReg(self.value.storage, value, "scope"),
            MultiReg(self.mask.storage, mask, "scope")
        ]

        self.comb += [
            sink.connect(source),
            source.hit.eq((sink.data & mask) == value)
        ]


class FrontendSubSampler(Module, AutoCSR):
    def __init__(self, dw):
        self.sink = sink = stream.Endpoint(core_layout(dw))
        self.source = source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(16)

        # # #

        value = Signal(16)
        self.specials += MultiReg(self.value.storage, value, "scope")

        counter = Signal(16)
        done = Signal()

        self.sync.scope += \
            If(source.ready,
                If(done,
                    counter.eq(0)
                ).Elif(sink.valid,
                    counter.eq(counter + 1)
                )
            )

        self.comb += [
            done.eq(counter == value),
            sink.connect(source, omit={"valid"}),
            source.valid.eq(sink.valid & done)
        ]


class AnalyzerMux(Module, AutoCSR):
    def __init__(self, dw, n):
        self.sinks = sinks = [stream.Endpoint(core_layout(dw)) for i in range(n)]
        self.source = source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(bits_for(n))

        # # #

        value = Signal(max=n)
        self.specials += MultiReg(self.value.storage, value, "scope")

        cases = {}
        for i in range(n):
            cases[i] = sinks[i].connect(source)
        self.comb += Case(value, cases)


class AnalyzerFrontend(Module, AutoCSR):
    def __init__(self, dw):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw))

        # # #

        self.submodules.trigger = FrontendTrigger(dw)
        self.submodules.subsampler = FrontendSubSampler(dw)
        self.submodules.pipeline = stream.Pipeline(
            self.sink,
            self.trigger,
            self.subsampler,
            self.source)


class AnalyzerStorage(Module, AutoCSR):
    def __init__(self, dw, depth):
        self.sink = sink = stream.Endpoint(core_layout(dw))

        self.start = CSR()
        self.length = CSRStorage(bits_for(depth))
        self.offset = CSRStorage(bits_for(depth))

        self.idle = CSRStatus()
        self.wait = CSRStatus()
        self.run  = CSRStatus()

        self.mem_valid = CSRStatus()
        self.mem_ready = CSR()
        self.mem_data = CSRStatus(dw)

        # # #


        # control re-synchronization
        start = Signal()
        length = Signal(max=depth)
        offset = Signal(max=depth)

        start_ps = PulseSynchronizer("sys", "scope")
        self.submodules += start_ps
        self.comb += start_ps.i.eq(self.start.re)
        self.specials += [
            MultiReg(self.length.storage, length, "scope"),
            MultiReg(self.offset.storage, offset, "scope")
        ]

        # status re-synchronization
        idle = Signal()
        wait = Signal()
        run = Signal()
        self.specials += [
            MultiReg(idle, self.idle.status),
            MultiReg(wait, self.wait.status),
            MultiReg(run, self.run.status)
        ]

        # memory
        mem = stream.SyncFIFO([("data", dw)], depth, buffered=True)
        mem = ClockDomainsRenamer("scope")(mem)
        cdc = stream.AsyncFIFO([("data", dw)], 4)
        cdc = ClockDomainsRenamer(
            {"write": "scope", "read": "sys"})(cdc)
        self.submodules += mem, cdc

        # flush
        mem_flush = WaitTimer(depth)
        mem_flush = ClockDomainsRenamer("scope")(mem_flush)
        self.submodules += mem_flush

        # fsm
        fsm = FSM(reset_state="IDLE")
        fsm = ClockDomainsRenamer("scope")(fsm)
        self.submodules += fsm
        fsm.act("IDLE",
            idle.eq(1),
            If(start_ps.o,
                NextState("FLUSH")
            ),
            sink.ready.eq(1),
            mem.source.connect(cdc.sink)
        )
        fsm.act("FLUSH",
            sink.ready.eq(1),
            mem_flush.wait.eq(1),
            mem.source.ready.eq(1),
            If(mem_flush.done,
                NextState("WAIT")
            )
        )
        fsm.act("WAIT",
            wait.eq(1),
            sink.connect(mem.sink, omit={"hit"}),
            If(sink.valid & sink.hit,
                NextState("RUN")
            ),
            mem.source.ready.eq(mem.level >= self.offset.storage)
        )
        fsm.act("RUN",
            run.eq(1),
            sink.connect(mem.sink, omit={"hit"}),
            If(mem.level >= self.length.storage,
                NextState("IDLE"),
            )
        )

        # memory read
        self.comb += [
            self.mem_valid.status.eq(cdc.source.valid),
            cdc.source.ready.eq(self.mem_ready.re),
            self.mem_data.status.eq(cdc.source.data)
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
    def __init__(self, groups, depth, cd="sys"):
        self.groups = _format_groups(groups)
        self.dw = max([sum([len(s) for s in g]) for g in self.groups.values()])

        self.depth = depth

        # # #

        self.clock_domains.cd_scope = ClockDomain()
        self.comb += [
            self.cd_scope.clk.eq(ClockSignal(cd)),
            self.cd_scope.rst.eq(ResetSignal(cd))
        ]

        self.submodules.mux = AnalyzerMux(self.dw, len(self.groups))
        for i, signals in self.groups.items():
            self.comb += [
                self.mux.sinks[i].valid.eq(1),
                self.mux.sinks[i].data.eq(Cat(signals))
            ]
        self.submodules.frontend = AnalyzerFrontend(self.dw)
        self.submodules.storage = AnalyzerStorage(self.dw, depth)
        self.comb += [
            self.mux.source.connect(self.frontend.sink),
            self.frontend.source.connect(self.storage.sink)
        ]

    def export_csv(self, vns, filename):
        def format_line(*args):
            return ",".join(args) + "\n"
        r = format_line("config", "None", "dw", str(self.dw))
        r += format_line("config", "None", "depth", str(self.depth))
        for i, signals in self.groups.items():
            for s in signals:
                r += format_line("signal", str(i), vns.get_name(s), str(len(s)))
        write_to_file(filename, r)
