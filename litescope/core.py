#
# This file is part of LiteScope.
#
# Copyright (c) 2016-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 bunnie <bunnie@kosagi.com>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

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
    def __init__(self, data_width, depth=16, timeout_width=32):
        self.sink   = sink   = stream.Endpoint(core_layout(data_width))
        self.source = source = stream.Endpoint(core_layout(data_width))

        self.enable = CSRStorage()
        self.done   = CSRStatus()

        self.mem_write   = CSR()
        self.mem_reset   = CSR()
        self.mem_mask    = CSRStorage(data_width)
        self.mem_value   = CSRStorage(data_width)
        self.mem_timeout = CSRStorage(timeout_width)
        self.mem_full    = CSRStatus()

        # # #

        # Control re-synchronization.
        enable   = Signal()
        self.specials += MultiReg(self.enable.storage, enable, "scope")

        # Status re-synchronization.
        done = Signal()
        self.specials += MultiReg(done, self.done.status)

        # Memory and configuration.
        entry_width = 2*data_width + timeout_width
        mem         = Memory(entry_width, depth)
        self.specials += mem

        wrport = mem.get_port(write_capable=True, clock_domain="sys")
        rdport = mem.get_port(async_read=True, clock_domain="scope")
        self.specials += wrport, rdport

        write_count = Signal(max=depth + 1)
        write_ptr   = Signal(max=depth)
        write       = Signal()
        self.comb += [
            write.eq(self.mem_write.wr_stb & (write_count != depth)),
            wrport.we.eq(write),
            wrport.adr.eq(write_ptr),
            wrport.dat_w.eq(Cat(
                self.mem_mask.storage,
                self.mem_value.storage,
                self.mem_timeout.storage)),
            self.mem_full.status.eq(write_count == depth),
        ]
        self.sync += [
            If(self.mem_reset.wr_stb,
                write_count.eq(0),
                write_ptr.eq(0)
            ).Elif(write,
                write_count.eq(write_count + 1),
                write_ptr.eq(write_ptr + 1)
            )
        ]

        trigger_count = Signal(max=depth + 1)
        self.specials += MultiReg(write_count, trigger_count, "scope")

        # Trigger sequence.
        trigger_index = Signal(max=depth)
        mask          = Signal(data_width)
        value         = Signal(data_width)
        timeout       = Signal(timeout_width)
        timeout_count = Signal(timeout_width)
        entry_valid   = Signal()
        hit           = Signal()
        last          = Signal()
        final_hit     = Signal()
        timeout_hit   = Signal()
        sample        = Signal()

        self.comb += [
            rdport.adr.eq(trigger_index),
            mask.eq(rdport.dat_r[:data_width]),
            value.eq(rdport.dat_r[data_width:2*data_width]),
            timeout.eq(rdport.dat_r[2*data_width:]),
            entry_valid.eq(trigger_index < trigger_count),
            hit.eq(entry_valid & ((sink.data & mask) == (value & mask))),
            last.eq(trigger_index == (trigger_count - 1)),
            final_hit.eq(enable & sink.valid & hit & last),
            timeout_hit.eq(entry_valid & (timeout != 0) & (timeout_count == (timeout - 1))),
            sample.eq(enable & sink.valid & source.ready),
        ]

        self.sync.scope += [
            If(~enable,
                trigger_index.eq(0),
                timeout_count.eq(0),
                done.eq(0)
            ).Elif(done,
                timeout_count.eq(0)
            ).Elif(sample & entry_valid,
                If(hit,
                    timeout_count.eq(0),
                    If(last,
                        trigger_index.eq(0),
                        done.eq(1)
                    ).Else(
                        trigger_index.eq(trigger_index + 1)
                    )
                ).Elif(timeout_hit,
                    trigger_index.eq(0),
                    timeout_count.eq(0)
                ).Elif(timeout != 0,
                    timeout_count.eq(timeout_count + 1)
                )
            )
        ]

        # Output.
        self.comb += [
            sink.connect(source),
            source.hit.eq((trigger_count == 0) | done | final_hit),
        ]

# LiteScope Analyzer SubSampler --------------------------------------------------------------------

class _SubSampler(LiteXModule):
    def __init__(self, data_width, value_width=16):
        assert value_width >= 1

        self.sink   = sink   = stream.Endpoint(core_layout(data_width))
        self.source = source = stream.Endpoint(core_layout(data_width))

        self.value = CSRStorage(value_width)

        # # #

        value = Signal(value_width)
        self.specials += MultiReg(self.value.storage, value, "scope")

        counter = Signal(value_width)
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
        self.flush = Signal()

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
            ).Elif(self.flush & (count != 0),
                emit_rle(),
                If(source.ready,
                    NextValue(count, 0)
                )
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
        self.flush = Signal()

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
            self.flush.eq((length != 0) & (mem.level >= (length - 1))),
            If(mem.level < length,
                sink.connect(mem.sink, omit={"hit"})
            ),
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
            read_source.ready.eq(self.mem_data.rd_stb | ~self.enable.storage),
            self.mem_data.status.eq(read_source.data)
        ]

# LiteScope Analyzer -------------------------------------------------------------------------------

class LiteScopeAnalyzer(LiteXModule):
    def __init__(self, groups, depth,
        samplerate             = 1e12,
        clock_domain           = "sys",
        trigger_depth          = 16,
        trigger_timeout_width  = 32,
        subsampler_width       = 16,
        register               = False,
        with_rle               = False,
        rle_length             = 256,
        csr_csv                = "analyzer.csv",
    ):
        self.groups           = groups = self.format_groups(groups)
        self.depth            = depth
        self.samplerate       = int(samplerate)
        self.trigger_timeout_width = trigger_timeout_width
        self.subsampler_width = subsampler_width

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
        self.trigger    = _Trigger(data_width, depth=trigger_depth, timeout_width=trigger_timeout_width)
        self.subsampler = _SubSampler(data_width, value_width=subsampler_width)

        # Storage.
        # --------
        if with_rle:
            self.rle = _RLE(data_width, storage_width, rle_length)
        self.storage = _Storage(storage_width, depth)
        if with_rle:
            self.comb += [
                self.rle.external_enable.eq(self.storage.post_hit),
                self.rle.flush.eq(self.storage.flush),
            ]

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
        r += format_line("config", "None", "trigger_timeout_width", str(self.trigger_timeout_width))
        r += format_line("config", "None", "subsampler_width", str(self.subsampler_width))
        r += format_line("config", "None", "with_rle", str(int(self.with_rle)))
        r += format_line("config", "None", "rle_length", str(self.rle_length))
        for i, signals in self.groups.items():
            for s in signals:
                name = vns.get_name(s)
                r += format_line("signal", str(i), name, str(len(s)))
                for value, label in sorted(getattr(s, "_enumeration", {}).items()):
                    r += format_line("enum", str(i), name, str(value), str(label))
        write_to_file(filename, r)

    def do_exit(self, vns):
        if self.csr_csv is not None:
            self.export_csv(vns, self.csr_csv)
