from litex.gen import *
from litex.gen.genlib.cdc import MultiReg

from litex.build.tools import write_to_file

from litex.soc.interconnect.csr import *
from litex.soc.cores.gpio import GPIOInOut
from litex.soc.interconnect import stream

def core_layout(dw, hw=1):
    return [("data", dw), ("hit", hw)]

class FrontendTrigger(Module, AutoCSR):
    def __init__(self, dw, cd):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(dw)
        self.mask = CSRStorage(dw)

        # # #

        value = Signal(dw)
        mask = Signal(dw)
        self.specials += [
            MultiReg(self.value.storage, value, cd),
            MultiReg(self.mask.storage, mask, cd)
        ]

        self.comb += [
            self.sink.connect(self.source),
            self.source.hit.eq((self.sink.data & mask) == value)
        ]


class FrontendSubSampler(Module, AutoCSR):
    def __init__(self, dw, cd):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw))

        self.value = CSRStorage(16)

        # # #

        sync_cd = getattr(self.sync, cd)

        value = Signal(16)
        self.specials += MultiReg(self.value.storage, value, cd)

        counter = Signal(16)
        done = Signal()

        sync_cd += \
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


class AnalyzerFrontend(Module, AutoCSR):
    def __init__(self, dw, cd, cd_ratio):
        self.sink = stream.Endpoint(core_layout(dw))
        self.source = stream.Endpoint(core_layout(dw*cd_ratio))

        # # #

        self.submodules.buffer = ClockDomainsRenamer(cd)(stream.Buffer(core_layout(dw)))
        self.submodules.trigger = FrontendTrigger(dw, cd)
        self.submodules.subsampler = FrontendSubSampler(dw, cd)
        self.submodules.converter = ClockDomainsRenamer(cd)(
                                        stream.StrideConverter(
                                            core_layout(dw, 1),
                                            core_layout(dw*cd_ratio, cd_ratio)))
        self.submodules.fifo = ClockDomainsRenamer({"write": cd, "read": "sys"})(
                                   stream.AsyncFIFO(core_layout(dw*cd_ratio, cd_ratio), 8))

        self.submodules.pipeline = stream.Pipeline(self.sink,
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
        self.length = CSRStorage(bits_for(depth))
        self.offset = CSRStorage(bits_for(depth))

        self.idle = CSRStatus()
        self.wait = CSRStatus()
        self.run  = CSRStatus()

        self.mem_valid = CSRStatus()
        self.mem_ready = CSR()
        self.mem_data = CSRStatus(dw)

        # # #

        mem = stream.SyncFIFO([("data", dw)], depth//cd_ratio, buffered=True)
        self.submodules += mem

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            self.idle.status.eq(1),
            If(self.start.re,
                NextState("WAIT")
            ),
            self.sink.ready.eq(1),
            mem.source.ready.eq(self.mem_ready.re & self.mem_ready.r)
        )
        fsm.act("WAIT",
            self.wait.status.eq(1),
            self.sink.connect(mem.sink, omit=set(["hit"])),
            If(self.sink.valid & (self.sink.hit != 0),
                NextState("RUN")
            ),
            mem.source.ready.eq(mem.level >= self.offset.storage)
        )
        fsm.act("RUN",
            self.run.status.eq(1),
            self.sink.connect(mem.sink, omit=set(["hit"])),
            If(~mem.sink.ready | (mem.level >= self.length.storage),
                NextState("IDLE"),
                mem.source.ready.eq(1)
            )
        )
        self.comb += [
            self.mem_valid.status.eq(mem.source.valid),
            self.mem_data.status.eq(mem.source.data)
        ]


class LiteScopeIO(Module, AutoCSR):
    def __init__(self, dw):
        self.dw = dw
        self.input = Signal(dw)
        self.output = Signal(dw)

        # # #

        self.submodules.gpio = GPIOInOut(self.input, self.output)

    def get_csrs(self):
        return self.gpio.get_csrs()


class LiteScopeAnalyzer(Module, AutoCSR):
    def __init__(self, signals, depth, cd="sys", cd_ratio=1):
        if not isinstance(signals, list):
            signals = [signals]

        split_signals = []
        for s in signals:
            if isinstance(s, Record):
                split_signals.extend(s.flatten())
            else:
                split_signals.append(s)
        signals = split_signals

        self.signals = signals
        self.dw = sum([len(s) for s in signals])
        self.core_dw = self.dw*cd_ratio

        self.depth = depth
        self.cd_ratio = cd_ratio

        # # #

        self.submodules.frontend = AnalyzerFrontend(self.dw, cd, cd_ratio)
        self.submodules.storage = AnalyzerStorage(self.core_dw, depth, cd_ratio)

        self.comb += [
            self.frontend.sink.valid.eq(1),
            self.frontend.sink.data.eq(Cat(self.signals)),
            self.frontend.source.connect(self.storage.sink)
        ]

    def export_csv(self, vns, filename):
        def format_line(*args):
            return ",".join(args) + "\n"
        r = format_line("config", "dw", str(self.dw))
        r += format_line("config", "depth", str(self.depth))
        r += format_line("config", "cd_ratio", str(int(self.cd_ratio)))
        for s in self.signals:
            r += format_line("signal", vns.get_name(s), str(len(s)))
        write_to_file(filename, r)
