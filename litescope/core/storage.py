from litescope.common import *


class LiteScopeSubSamplerUnit(Module):
    def __init__(self, dw):
        self.sink = sink = Sink(data_layout(dw))
        self.source = source = Source(data_layout(dw))
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
            done.eq(self.counter >= self.value),
            Record.connect(sink, source),
            source.stb.eq(sink.stb & done),
            self.counter_ce.eq(source.ack),
            self.counter_reset.eq(source.stb & source.ack & done)
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

        self.sink = sink = Sink(data_layout(dw))
        self.source = source = Source(data_layout(dw))

        self.enable = Signal()

        # # #

        self.submodules.buf = buf = Buffer(sink.description)
        self.comb += Record.connect(sink, buf.d)

        counter = Signals(max=length)
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
            sink.stb &
            (sink.data != buf.q.data)
        )

        self.submodules.fsm = fsm = FSM(reset_state="BYPASS")
        fsm.act("BYPASS",
            Record.connect(buf.q, source),
            counter_reset.eq(1),
            If(sink.stb & ~change,
                If(self.enable,
                    NextState("COUNT")
                )
            )
        )
        fsm.act("COUNT",
            buf.q.ack.eq(1),
            counter_ce.eq(sink.stb),
            If(~self.enable,
                NextState("BYPASS")
            ).Elif(change | counter_done,
                source.stb.eq(1),
                source.data[:len(counter)].eq(counter),
                source.data[-1].eq(1),  # Set RLE bit
                buf.q.ack.eq(source.ack),
                If(source.ack,
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

        self.trigger_sink = trigger_sink = Sink(hit_layout())
        self.data_sink = data_sink = Sink(data_layout(dw))

        self.trigger = Signal()
        self.qualifier = Signal()
        self.length = Signal(bits_for(depth))
        self.offset = Signal(bits_for(depth))
        self.done = Signal()
        self.post_hit = Signal()

        self.source = Source(data_layout(dw))

        # # #

        fifo = ResetInserter()(SyncFIFO(data_layout(dw), depth, buffered=True))
        self.submodules += fifo

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        self.comb += [
            self.source.stb.eq(fifo.source.stb),
            self.source.data.eq(fifo.source.data)
        ]
        fsm.act("IDLE",
            self.done.eq(1),
            If(self.trigger,
                NextState("PRE_HIT_RECORDING"),
                fifo.reset.eq(1),
            ),
            fifo.source.ack.eq(self.source.ack)
        )
        fsm.act("PRE_HIT_RECORDING",
            fifo.sink.stb.eq(data_sink.stb),
            fifo.sink.data.eq(data_sink.data),
            data_sink.ack.eq(fifo.sink.ack),

            fifo.source.ack.eq(fifo.level >= self.offset),
            If(trigger_sink.stb & trigger_sink.hit,
                NextState("POST_HIT_RECORDING")
            )
        )
        fsm.act("POST_HIT_RECORDING",
            self.post_hit.eq(1),
            If(self.qualifier,
                fifo.sink.stb.eq(trigger_sink.stb &
                                 trigger_sink.hit &
                                 data_sink.stb)
            ).Else(
                fifo.sink.stb.eq(data_sink.stb)
            ),
            fifo.sink.data.eq(data_sink.data),
            data_sink.ack.eq(fifo.sink.ack),

            If(~fifo.sink.ack | (fifo.level >= self.length),
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

        self._source_stb = CSRStatus()
        self._source_ack = CSR()
        self._source_data = CSRStatus(dw)

        # # #

        self.comb += [
            self.trigger.eq(self._trigger.re),
            self.qualifier.eq(self._qualifier.storage),
            self.length.eq(self._length.storage),
            self.offset.eq(self._offset.storage),
            self._done.status.eq(self.done),

            self._source_stb.status.eq(self.source.stb),
            self._source_data.status.eq(self.source.data),
            self.source.ack.eq(self._source_ack.re)
        ]
