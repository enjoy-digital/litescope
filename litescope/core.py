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
    def __init__(self, dw, edges=False, hitcountbits=0, triggers=1, trigger_num=0):
        self.sink = stream.Endpoint(core_layout(dw, triggers))
        self.source = stream.Endpoint(core_layout(dw, triggers))

        self.value = CSRStorage(dw)
        self.mask = CSRStorage(dw)

        # API: if a bit has edge_enable, then the "value" field selects the edge type (0 = pos, 1 = neg)
        # and the "mask" field selects if the edge matters or not
        # if the edge_enable bit is not set, then the "value" field selects the value to look for as a match,
        # and the "mask" field selects if the level matters or not
        if edges:
            self.edge_enable = CSRStorage(dw)
            if hitcountbits > 0:
                self.hit_count = CSRStorage(hitcountbits)
                self.hit_reset = Signal()

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

            if hitcountbits > 0:
                hit_count = Signal(hitcountbits)
                self.specials += MultiReg(self.hit_count.storage, hit_count)
                hit_reset = Signal()
                self.specials += MultiReg(self.hit_reset, hit_reset)
                self.hit_counter = hit_counter = Signal(hitcountbits)

        self.comb += self.sink.connect(self.source, omit=set(["hit"]))
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
            if hitcountbits == 0:
                self.comb += self.source.hit[trigger_num].eq(hit_masked != 0)
            else:
                self.sync += [
                    If(hit_reset,
                       hit_counter.eq(0)
                       ).Elif( (hit_masked != 0) & (hit_counter < hit_count), # count up to hit_count then stop, freezing in trigger
                              hit_counter.eq(hit_counter + 1)
                       )
                ]
                self.comb += [
                    If(hit_counter == hit_count,
                       self.source.hit[trigger_num].eq(1)
                       ).Else(
                        self.source.hit[trigger_num].eq(0)
                    )
                ]
        else:
            self.comb += self.source.hit.eq((self.sink.data & mask) == value)


class FrontendSubSampler(Module, AutoCSR):
    def __init__(self, dw, triggers):
        self.sink = stream.Endpoint(core_layout(dw, triggers))
        self.source = stream.Endpoint(core_layout(dw, triggers))

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
    def __init__(self, dw, cd_ratio, edges=False, triggers=1, hitcountbits=0):
        self.sink = stream.Endpoint(core_layout(dw, triggers))
        self.source = stream.Endpoint(core_layout(dw*cd_ratio, triggers))

        # # #

        self.submodules.buffer = stream.Buffer(core_layout(dw, triggers))

        if triggers == 2:
            self.submodules.trigger2 = FrontendTrigger(dw, edges=edges, hitcountbits=hitcountbits, triggers=triggers, trigger_num=1)
            self.comb += [
                self.trigger2.sink.eq(self.buffer.source),  # tap the buffer and compute triggers
                ]
            self.submodules.trigger = FrontendTrigger(dw, edges, hitcountbits=hitcountbits, triggers=triggers) # leave at default trigger_num = 0
            self.comb += self.trigger.source.hit[1].eq(self.trigger2.source.hit[1])  # map 2nd trigger output back into the main flow

        else:
            self.submodules.trigger = FrontendTrigger(dw, edges, hitcountbits=hitcountbits, triggers=triggers)  # leave at default trigger_num = 0

        self.submodules.subsampler = FrontendSubSampler(dw, triggers)
        self.submodules.converter = stream.StrideConverter(
                core_layout(dw, 1 * triggers), core_layout(dw*cd_ratio, cd_ratio * triggers))
        self.submodules.fifo = ClockDomainsRenamer(
            {"write": "sys", "read": "new_sys"})(
                stream.AsyncFIFO(core_layout(dw*cd_ratio, cd_ratio * triggers), 8))
        self.submodules.pipeline = stream.Pipeline(
            self.sink,
            self.buffer,
            self.trigger,
            self.subsampler,
            self.converter,
            self.fifo,
            self.source)



class AnalyzerStorage(Module, AutoCSR):
    def __init__(self, dw, depth, cd_ratio, triggers=1):
        self.sink = stream.Endpoint(core_layout(dw, cd_ratio * triggers))

        self.start = CSR()
        self.restart = CSR()
        self.length = CSRStorage(bits_for(depth))
        self.offset = CSRStorage(bits_for(depth))

        self.idle = CSRStatus()
        self.wait = CSRStatus()
        if triggers == 2:
            self.wait2 = CSRStatus()
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
        if triggers == 1:
            fsm.act("WAIT",
                self.wait.status.eq(1),
                self.sink.connect(mem.sink, omit=set(["hit"])),
                If(self.sink.valid & (self.sink.hit[0] != 0),
                    NextState("RUN")
                ),
                mem.source.ready.eq(mem.level >= self.offset.storage)
                # in the wait state: 1) fill the FIFO until we hit the offset level
                # 2) once we've hit the offset level, if we go over it, read a value out
                # this keeps the FIFO "spinning" until the trigger is hit
            )
        else:
            fsm.act("WAIT",
                self.wait.status.eq(1),
                self.sink.connect(mem.sink, omit=set(["hit"])),
                If(self.sink.valid & (self.sink.hit[0] != 0),
                    NextState("WAIT2")
                ).Elif(self.restart.re,
                       NextState("IDLE")
                ),
                mem.source.ready.eq(mem.level >= self.offset.storage)
            )
            fsm.act("WAIT2",
                self.wait2.status.eq(1),
                self.sink.connect(mem.sink, omit=set(["hit"])),
                If(self.sink.valid & (self.sink.hit[1] != 0),
                    NextState("RUN")
                ).Elif(self.restart.re,
                       NextState("IDLE")
                ),
                mem.source.ready.eq(mem.level >= self.offset.storage)
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
    def __init__(self, groups, depth, cd="sys", cd_ratio=1, edges=False, triggers=1, hitcountbits=0):
        assert triggers <= 2  # only support 1 or 2 triggers for now
        if triggers == 2:
            assert hitcountbits > 0  # need to have a hit counter if we're also doing multiple triggers

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
            {"sys": cd, "new_sys": "sys"})(AnalyzerFrontend(self.dw, cd_ratio, edges, triggers, hitcountbits))
        self.submodules.storage = AnalyzerStorage(self.dw*cd_ratio, depth, cd_ratio, triggers)
        self.comb += [
            self.mux.source.connect(self.frontend.sink),
            self.frontend.source.connect(self.storage.sink),
        ]
        # keep triggers in reset throughout the whole pipeline
        # because there's an ASYNCFIFO in between the trigger computation and interpretation
        # stale data in the FIFO can cause faulty triggering if the triggers are allowed to spin when not strictly active
        if hitcountbits > 0:
            self.comb += self.frontend.trigger.hit_reset.eq(self.storage.idle.status)  # reset the hit count when analyzer is IDLE
            if triggers == 2:
                self.comb += self.frontend.trigger2.hit_reset.eq(self.storage.wait.status | self.storage.idle.status) # reset trigger2's hit count while trigger 1 is pending



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
