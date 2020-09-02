#
# This file is part of LiteScope.
#
# Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 bunnie <bunnie@kosagi.com>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.misc import WaitTimer
from migen.genlib.cdc import MultiReg, PulseSynchronizer

from litex.build.tools import write_to_file

from litex.soc.interconnect.csr import *
from litex.soc.cores.gpio import GPIOInOut
from litex.soc.interconnect import stream

# LiteScope IO -------------------------------------------------------------------------------------

class LiteScopeIO(Module, AutoCSR):
    def __init__(self, data_width):
        self.data_width = data_width
        self.input  = Signal(data_width)
        self.output = Signal(data_width)

        # # #

        self.submodules.gpio = GPIOInOut(self.input, self.output)

    def get_csrs(self):
        return self.gpio.get_csrs()

# LiteScope Analyzer -------------------------------------------------------------------------------

def core_layout(data_width):
    return [("data", data_width), ("hit", 1)]


class _Trigger(Module, AutoCSR):
    def __init__(self, data_width, depth=16):
        self.sink   = sink   = stream.Endpoint(core_layout(data_width))
        self.source = source = stream.Endpoint(core_layout(data_width))

        self.enable = CSRStorage()
        self.done   = CSRStatus()

        self.mem_write = CSR()
        self.mem_mask  = CSRStorage(data_width)
        self.mem_value = CSRStorage(data_width)
        self.mem_full  = CSRStatus()

        # # #

        # Control re-synchronization
        enable   = Signal()
        enable_d = Signal()
        self.specials += MultiReg(self.enable.storage, enable, "scope")
        self.sync.scope += enable_d.eq(enable)

        # Status re-synchronization
        done = Signal()
        self.specials += MultiReg(done, self.done.status)

        # Memory and configuration
        mem = stream.AsyncFIFO([("mask", data_width), ("value", data_width)], depth)
        mem = ClockDomainsRenamer({"write": "sys", "read": "scope"})(mem)
        self.submodules += mem
        self.comb += [
            mem.sink.valid.eq(self.mem_write.re),
            mem.sink.mask.eq(self.mem_mask.storage),
            mem.sink.value.eq(self.mem_value.storage),
            self.mem_full.status.eq(~mem.sink.ready)
        ]

        # Hit and memory read/flush
        hit   = Signal()
        flush = WaitTimer(2*depth)
        flush = ClockDomainsRenamer("scope")(flush)
        self.submodules += flush
        self.comb += [
            flush.wait.eq(~(~enable & enable_d)), # flush when disabling
            hit.eq((sink.data & mem.source.mask) == (mem.source.value & mem.source.mask)),
            mem.source.ready.eq((enable & hit) | ~flush.done),
        ]

        # Output
        self.comb += [
            sink.connect(source),
            # Done when all triggers have been consumed
            done.eq(~mem.source.valid),
            source.hit.eq(done)
        ]

class _SubSampler(Module, AutoCSR):
    def __init__(self, data_width):
        self.sink   = sink   = stream.Endpoint(core_layout(data_width))
        self.source = source = stream.Endpoint(core_layout(data_width))

        self.value = CSRStorage(16)

        # # #

        value = Signal(16)
        self.specials += MultiReg(self.value.storage, value, "scope")

        counter = Signal(16)
        done    = Signal()
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


class _Mux(Module, AutoCSR):
    def __init__(self, data_width, n):
        self.sinks  = sinks  = [stream.Endpoint(core_layout(data_width)) for i in range(n)]
        self.source = source = stream.Endpoint(core_layout(data_width))

        self.value = CSRStorage(bits_for(n))

        # # #

        value = Signal(bits_for(n))
        self.specials += MultiReg(self.value.storage, value, "scope")

        cases = {}
        for i in range(n):
            cases[i] = sinks[i].connect(source)
        self.comb += Case(value, cases)


class _Storage(Module, AutoCSR):
    def __init__(self, data_width, depth):
        self.sink = sink = stream.Endpoint(core_layout(data_width))

        self.enable    = CSRStorage()
        self.done      = CSRStatus()

        self.length    = CSRStorage(bits_for(depth))
        self.offset    = CSRStorage(bits_for(depth))

        self.mem_valid = CSRStatus()
        self.mem_data  = CSRStatus(data_width)

        # # #

        # Control re-synchronization
        enable   = Signal()
        enable_d = Signal()
        self.specials += MultiReg(self.enable.storage, enable, "scope")
        self.sync.scope += enable_d.eq(enable)

        length = Signal().like(self.length.storage)
        offset = Signal().like(self.offset.storage)
        self.specials += MultiReg(self.length.storage, length, "scope")
        self.specials += MultiReg(self.offset.storage, offset, "scope")

        # Status re-synchronization
        done = Signal()
        self.specials += MultiReg(done, self.done.status)

        # Memory
        mem = stream.SyncFIFO([("data", data_width)], depth, buffered=True)
        mem = ClockDomainsRenamer("scope")(mem)
        cdc = stream.AsyncFIFO([("data", data_width)], 4)
        cdc = ClockDomainsRenamer(
            {"write": "scope", "read": "sys"})(cdc)
        self.submodules += mem, cdc

        # Flush
        mem_flush = WaitTimer(depth)
        mem_flush = ClockDomainsRenamer("scope")(mem_flush)
        self.submodules += mem_flush

        # FSM
        fsm = FSM(reset_state="IDLE")
        fsm = ClockDomainsRenamer("scope")(fsm)
        self.submodules += fsm
        fsm.act("IDLE",
            done.eq(1),
            If(enable & ~enable_d,
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
            sink.connect(mem.sink, omit={"hit"}),
            If(sink.valid & sink.hit,
                NextState("RUN")
            ),
            mem.source.ready.eq(mem.level >= offset)
        )
        fsm.act("RUN",
            sink.connect(mem.sink, omit={"hit"}),
            If(mem.level >= length,
                NextState("IDLE"),
            )
        )

        # Memory read
        self.comb += [
            self.mem_valid.status.eq(cdc.source.valid),
            cdc.source.ready.eq(self.mem_data.we | ~self.enable.storage),
            self.mem_data.status.eq(cdc.source.data)
        ]


class LiteScopeAnalyzer(Module, AutoCSR):
    def __init__(self, groups, depth, clock_domain="sys", trigger_depth=16, csr_csv=None):
        self.groups = groups = self.format_groups(groups)
        self.depth  = depth

        self.data_width = data_width = max([sum([len(s) for s in g]) for g in groups.values()])

        self.csr_csv = csr_csv

        # # #

        # Create scope clock domain
        self.clock_domains.cd_scope = ClockDomain()
        self.comb += self.cd_scope.clk.eq(ClockSignal(clock_domain))

        # Mux
        self.submodules.mux = _Mux(data_width, len(groups))
        for i, signals in groups.items():
            self.comb += [
                self.mux.sinks[i].valid.eq(1),
                self.mux.sinks[i].data.eq(Cat(signals))
            ]

        # Frontend
        self.submodules.trigger = _Trigger(data_width, depth=trigger_depth)
        self.submodules.subsampler = _SubSampler(data_width)

        # Storage
        self.submodules.storage = _Storage(data_width, depth)

        # Pipeline
        self.submodules.pipeline = stream.Pipeline(
            self.mux.source,
            self.trigger,
            self.subsampler,
            self.storage.sink)

    def format_groups(self, groups):
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
                elif isinstance(s, FSM):
                    s.do_finalize()
                    s.finalized = True
                    split_signals.append(s.state)
                else:
                    split_signals.append(s)
            new_groups[n] = split_signals
        return new_groups

    def export_csv(self, vns, filename):
        def format_line(*args):
            return ",".join(args) + "\n"
        r = format_line("config", "None", "data_width", str(self.data_width))
        r += format_line("config", "None", "depth", str(self.depth))
        for i, signals in self.groups.items():
            for s in signals:
                r += format_line("signal", str(i), vns.get_name(s), str(len(s)))
        write_to_file(filename, r)

    def do_exit(self, vns):
        if self.csr_csv is not None:
            self.export_csv(vns, self.csr_csv)
