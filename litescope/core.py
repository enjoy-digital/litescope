#
# This file is part of LiteScope.
#
# Copyright (c) 2016-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 bunnie <bunnie@kosagi.com>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.build.tools import write_to_file

from litex.soc.interconnect.csr import *

from litex.soc.cores.gpio   import GPIOInOut
from litex.soc.interconnect import stream

# LiteScope IO -------------------------------------------------------------------------------------

class LiteScopeIO(LiteXModule):
    def __init__(self, data_width):
        self.data_width = data_width
        self.input  = Signal(data_width)
        self.output = Signal(data_width)

        # # #

        self.gpio = GPIOInOut(self.input, self.output)

    def get_csrs(self):
        return self.gpio.get_csrs()

# LiteScope Analyzer Constants/Layouts -------------------------------------------------------------

def core_layout(data_width):
    return [("data", data_width), ("hit", 1)]

# LiteScope Analyzer Trigger -----------------------------------------------------------------------

class _Trigger(LiteXModule):
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

        # Control re-synchronization.
        enable   = Signal()
        enable_d = Signal()
        self.specials += MultiReg(self.enable.storage, enable, "scope")
        self.sync.scope += enable_d.eq(enable)

        # Status re-synchronization.
        done = Signal()
        self.specials += MultiReg(done, self.done.status)

        # Memory and configuration.
        mem = stream.AsyncFIFO([("mask", data_width), ("value", data_width)], depth)
        mem = ClockDomainsRenamer({"write": "sys", "read": "scope"})(mem)
        self.submodules += mem
        self.comb += [
            mem.sink.valid.eq(self.mem_write.re),
            mem.sink.mask.eq(self.mem_mask.storage),
            mem.sink.value.eq(self.mem_value.storage),
            self.mem_full.status.eq(~mem.sink.ready)
        ]

        # Hit and memory read/flush.
        hit   = Signal()
        flush = WaitTimer(2*depth)
        flush = ClockDomainsRenamer("scope")(flush)
        self.submodules += flush
        self.comb += [
            flush.wait.eq(~(~enable & enable_d)), # flush when disabling
            hit.eq((sink.data & mem.source.mask) == (mem.source.value & mem.source.mask)),
            mem.source.ready.eq((enable & hit) | ~flush.done),
        ]

        # Output.
        self.comb += [
            sink.connect(source),
            # Done when all triggers have been consumed.
            done.eq(~mem.source.valid),
            source.hit.eq(done)
        ]

# LiteScope Analyzer SubSampler --------------------------------------------------------------------

class _SubSampler(LiteXModule):
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

# LiteScope Analyzer Run Length Encoder -----------------------------------------------------------

class _RLE(LiteXModule):
    def __init__(self, data_width, storage_width, length):
        assert length >= 2

        self.sink   = sink   = stream.Endpoint(core_layout(data_width))
        self.source = source = stream.Endpoint(core_layout(storage_width))

        self.enable = CSRStorage()
        self.external_enable = Signal(reset=1)

        # # #

        enable = Signal()
        active_enable = Signal()
        self.specials += MultiReg(self.enable.storage, enable, "scope")
        self.comb += active_enable.eq(enable & self.external_enable)

        count_width  = bits_for(length - 1)
        marker_bit   = storage_width - 1
        max_count    = length - 1
        last_data    = Signal(data_width)
        pending_data = Signal(data_width)
        pending_hit  = Signal()
        count        = Signal(count_width)
        rle_data     = Signal(storage_width)

        self.comb += [
            rle_data[:count_width].eq(count),
            rle_data[marker_bit].eq(1),
        ]

        def emit_raw(data, hit):
            return [
                source.valid.eq(1),
                source.data.eq(data),
                source.hit.eq(hit),
            ]

        def emit_rle():
            return [
                source.valid.eq(1),
                source.data.eq(rle_data),
                source.hit.eq(1),
            ]

        fsm = FSM(reset_state="BYPASS")
        fsm = ClockDomainsRenamer("scope")(fsm)
        self.submodules += fsm

        fsm.act("BYPASS",
            source.valid.eq(sink.valid),
            source.data.eq(sink.data),
            source.hit.eq(sink.hit),
            sink.ready.eq(source.ready),
            If(sink.valid & source.ready & active_enable & sink.hit,
                NextValue(last_data, sink.data),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            If(~active_enable,
                NextValue(count, 0),
                NextState("BYPASS")
            ).Elif(count == max_count,
                emit_rle(),
                If(source.ready,
                    NextValue(count, 0)
                )
            ).Elif(sink.valid,
                If(sink.data == last_data,
                    sink.ready.eq(1),
                    NextValue(count, count + 1)
                ).Else(
                    If(count != 0,
                        emit_rle(),
                        sink.ready.eq(source.ready),
                        If(source.ready,
                            NextValue(count, 0),
                            NextValue(pending_data, sink.data),
                            NextValue(pending_hit,  sink.hit),
                            NextState("EMIT_RAW")
                        )
                    ).Else(
                        emit_raw(sink.data, sink.hit),
                        sink.ready.eq(source.ready),
                        If(source.ready,
                            NextValue(last_data, sink.data)
                        )
                    )
                )
            )
        )
        fsm.act("EMIT_RAW",
            emit_raw(pending_data, pending_hit),
            If(source.ready,
                NextValue(last_data, pending_data),
                NextState("RUN")
            )
        )

# LiteScope Analyzer Mux ---------------------------------------------------------------------------

class _Mux(LiteXModule):
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

# LiteScope Analyzer Storage -----------------------------------------------------------------------

class _Storage(LiteXModule):
    def __init__(self, data_width, depth):
        self.sink = sink = stream.Endpoint(core_layout(data_width))
        self.post_hit = Signal()

        self.enable    = CSRStorage()
        self.done      = CSRStatus()

        self.length    = CSRStorage(bits_for(depth))
        self.offset    = CSRStorage(bits_for(depth))

        read_width = min(32, data_width)
        self.mem_level = CSRStatus(bits_for(depth))
        self.mem_data  = CSRStatus(read_width)

        # # #

        # Control re-synchronization.
        enable   = Signal()
        enable_d = Signal()
        self.specials += MultiReg(self.enable.storage, enable, "scope")
        self.sync.scope += enable_d.eq(enable)

        length = Signal().like(self.length.storage)
        offset = Signal().like(self.offset.storage)
        self.specials += MultiReg(self.length.storage, length, "scope")
        self.specials += MultiReg(self.offset.storage, offset, "scope")

        # Status re-synchronization.
        done  = Signal()
        level = Signal().like(self.mem_level.status)
        self.specials += MultiReg(done, self.done.status)
        self.specials += MultiReg(level, self.mem_level.status)

        # Memory.
        mem = stream.SyncFIFO([("data", data_width)], depth, buffered=True)
        mem = ClockDomainsRenamer("scope")(mem)
        cdc = stream.AsyncFIFO([("data", data_width)], 4)
        cdc = ClockDomainsRenamer({"write": "scope", "read": "sys"})(cdc)
        self.submodules += mem, cdc

        self.comb += level.eq(mem.level)

        # Flush.
        mem_flush = WaitTimer(depth)
        mem_flush = ClockDomainsRenamer("scope")(mem_flush)
        self.submodules += mem_flush

        # FSM.
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
            self.post_hit.eq(1),
            sink.connect(mem.sink, omit={"hit"}),
            If(mem.level >= length,
                NextState("IDLE"),
            )
        )

        # Memory read.
        read_source = stream.Endpoint([("data", data_width)])
        if data_width > read_width:
            pad_bits = - data_width % read_width
            w_conv = stream.Converter(data_width + pad_bits, read_width)
            self.submodules += w_conv
            self.comb += cdc.source.connect(w_conv.sink)
            self.comb += w_conv.source.connect(read_source)
        else:
            self.comb += cdc.source.connect(read_source)

        self.comb += [
            read_source.ready.eq(self.mem_data.we | ~self.enable.storage),
            self.mem_data.status.eq(read_source.data)
        ]

# LiteScope Analyzer -------------------------------------------------------------------------------

class LiteScopeAnalyzer(LiteXModule):
    def __init__(self, groups, depth,
        samplerate    = 1e12,
        clock_domain  = "sys",
        trigger_depth = 16,
        register      = False,
        with_rle      = False,
        rle_length    = 256,
        csr_csv       = "analyzer.csv",
    ):
        self.groups     = groups = self.format_groups(groups)
        self.depth      = depth
        self.samplerate = int(samplerate)

        self.data_width = data_width = max([sum([len(s) for s in g]) for g in groups.values()])
        self.with_rle   = with_rle
        self.rle_length = rle_length
        self.storage_width = storage_width = data_width
        if with_rle:
            self.storage_width = storage_width = max(data_width, bits_for(rle_length - 1)) + 1

        self.csr_csv = csr_csv

        # # #

        # Create scope clock domain.
        self.cd_scope = ClockDomain()
        self.comb += self.cd_scope.clk.eq(ClockSignal(clock_domain))

        # Mux.
        # ----
        self.mux = _Mux(data_width, len(groups))
        sd = getattr(self.sync, clock_domain)
        for i, signals in groups.items():
            s = Cat(signals)
            if len(s) < data_width:
                s = Cat(s, Constant(0, data_width - len(s)))
            if register:
                s_d = Signal(len(s))
                sd += s_d.eq(s)
                s = s_d
            self.comb += [
                self.mux.sinks[i].valid.eq(1),
                self.mux.sinks[i].data.eq(s)
            ]

        # Frontend.
        # ---------
        self.trigger    = _Trigger(data_width, depth=trigger_depth)
        self.subsampler = _SubSampler(data_width)

        # Storage.
        # --------
        if with_rle:
            self.rle = _RLE(data_width, storage_width, rle_length)
        self.storage = _Storage(storage_width, depth)
        if with_rle:
            self.comb += self.rle.external_enable.eq(self.storage.post_hit)

        # Pipeline: Mux -> Trigger -> Subsampler -> Storage.
        # --------------------------------------------------
        pipeline = [
            self.mux,
            self.trigger,
            self.subsampler,
        ]
        if with_rle:
            pipeline.append(self.rle)
        pipeline.append(self.storage)
        self.pipeline = stream.Pipeline(*pipeline)

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
            split_signals = list(dict.fromkeys(split_signals)) # Remove duplicates.
            new_groups[n] = split_signals
        return new_groups

    def export_csv(self, vns, filename):
        def format_line(*args):
            return ",".join(args) + "\n"
        r = format_line("config", "None", "data_width", str(self.data_width))
        r += format_line("config", "None", "storage_width", str(self.storage_width))
        r += format_line("config", "None", "depth", str(self.depth))
        r += format_line("config", "None", "samplerate", str(self.samplerate))
        r += format_line("config", "None", "with_rle", str(int(self.with_rle)))
        r += format_line("config", "None", "rle_length", str(self.rle_length))
        for i, signals in self.groups.items():
            for s in signals:
                r += format_line("signal", str(i), vns.get_name(s), str(len(s)))
        write_to_file(filename, r)

    def do_exit(self, vns):
        if self.csr_csv is not None:
            self.export_csv(vns, self.csr_csv)
