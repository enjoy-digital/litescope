from litescope.common import *


class LiteScopeSubSamplerUnit(Module):
    def __init__(self, dw):
        self.sink = sink = stream.Endpoint(data_layout(dw))
        self.source = source = stream.Endpoint(data_layout(dw))
        self.value = Signal(32)

        # # #

        counter = Signal(32)
        counter_reset = Signal()
        counter_ce = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )


        done = Signal()
        self.comb += [
            done.eq(counter >= self.value),
            sink.connect(source),
            source.valid.eq(sink.valid & done),
            counter_ce.eq(source.ready),
            counter_reset.eq(source.valid & source.ready & done)
        ]


class LiteScopeSubSampler(LiteScopeSubSamplerUnit, AutoCSR):
    def __init__(self, dw):
        LiteScopeSubSamplerUnit.__init__(self, dw)
        self._value = CSRStorage(32)

        # # #

        self.comb += self.value.eq(self._value.storage)


class LiteScopeRunLengthEncoderUnit(Module):
    def __init__(self, dw, length):
        self.dw = dw
        self.length = length

        self.sink = sink = stream.Endpoint(data_layout(dw))
        self.source = source = stream.Endpoint(data_layout(dw))

        self.enable = Signal()

        # # #

        self.submodules.buf = buf = Buffer(sink.description)
        self.comb += sink.connect(buf.sink)

        counter = Signal(max=length)
        counter_reset = Signal()
        counter_ce = Signal()
        counter_done = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )
        self.comb += counter_done.eq(counter == length - 1)

        change = Signal()
        self.comb += change.eq(
            sink.valid &
            (sink.data != buf.source.data)
        )

        self.submodules.fsm = fsm = FSM(reset_state="BYPASS")
        fsm.act("BYPASS",
            buf.source.connect(source),
            counter_reset.eq(1),
            If(sink.valid & ~change,
                If(self.enable,
                    NextState("COUNT")
                )
            )
        )
        fsm.act("COUNT",
            buf.source.ready.eq(1),
            counter_ce.eq(sink.valid),
            If(~self.enable,
                NextState("BYPASS")
            ).Elif(change | counter_done,
                source.valid.eq(1),
                source.data[:len(counter)].eq(counter),
                source.data[-1].eq(1),  # Set RLE bit
                buf.source.ready.eq(source.ready),
                If(source.ready,
                    NextState("BYPASS")
                )
            )
        )


class LiteScopeRunLengthEncoder(LiteScopeRunLengthEncoderUnit, AutoCSR):
    def __init__(self, dw, length=1024):
        LiteScopeRunLengthEncoderUnit.__init__(self, dw, length)
        self._enable = CSRStorage()
        self.external_enable = Signal(reset=1)

        # # #

        self.comb += self.enable.eq(self._enable.storage & self.external_enable)


class LiteScopeRecorderUnit(Module):
    def __init__(self, dw, depth):
        self.dw = dw
        self.depth = depth

        self.trigger_sink = trigger_sink = stream.Endpoint(hit_layout())
        self.data_sink = data_sink = stream.Endpoint(data_layout(dw))

        self.trigger = Signal()
        self.qualifier = Signal()
        self.length = Signal(bits_for(depth))
        self.offset = Signal(bits_for(depth))
        self.done = Signal()
        self.post_hit = Signal()

        self.source = stream.Endpoint(data_layout(dw))

        # # #

        fifo = ResetInserter()(SyncFIFO(data_layout(dw), depth, buffered=True))
        self.submodules += fifo

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        self.comb += [
            self.source.valid.eq(fifo.source.valid),
            self.source.data.eq(fifo.source.data)
        ]
        fsm.act("IDLE",
            self.done.eq(1),
            If(self.trigger,
                NextState("PRE_HIT_RECORDING"),
                fifo.reset.eq(1),
            ),
            fifo.source.ready.eq(self.source.ready)
        )
        fsm.act("PRE_HIT_RECORDING",
            fifo.sink.valid.eq(data_sink.valid),
            fifo.sink.data.eq(data_sink.data),
            data_sink.ready.eq(fifo.sink.ready),

            fifo.source.ready.eq(fifo.level >= self.offset),
            If(trigger_sink.valid & trigger_sink.hit,
                NextState("POST_HIT_RECORDING")
            )
        )
        fsm.act("POST_HIT_RECORDING",
            self.post_hit.eq(1),
            If(self.qualifier,
                fifo.sink.valid.eq(trigger_sink.valid &
                                 trigger_sink.hit &
                                 data_sink.valid)
            ).Else(
                fifo.sink.valid.eq(data_sink.valid)
            ),
            fifo.sink.data.eq(data_sink.data),
            data_sink.ready.eq(fifo.sink.ready),

            If(~fifo.sink.ready | (fifo.level >= self.length),
                NextState("IDLE")
            )
        )


class LiteScopeRecorder(LiteScopeRecorderUnit, AutoCSR):
    def __init__(self, dw, depth):
        LiteScopeRecorderUnit.__init__(self, dw, depth)

        self._trigger = CSR()
        self._qualifier = CSRStorage()
        self._length = CSRStorage(bits_for(depth))
        self._offset = CSRStorage(bits_for(depth))
        self._done = CSRStatus()

        self._source_valid = CSRStatus()
        self._source_ready = CSR()
        self._source_data = CSRStatus(dw)

        # # #

        self.comb += [
            self.trigger.eq(self._trigger.re),
            self.qualifier.eq(self._qualifier.storage),
            self.length.eq(self._length.storage),
            self.offset.eq(self._offset.storage),
            self._done.status.eq(self.done),

            self._source_valid.status.eq(self.source.valid),
            self._source_data.status.eq(self.source.data),
            self.source.ready.eq(self._source_ready.re)
        ]
