from litescope.common import *
from litescope.core.trigger import LiteScopeTrigger
from litescope.core.storage import LiteScopeSubSampler, LiteScopeRecorder, LiteScopeRunLengthEncoder

from litex.build.tools import write_to_file


class LiteScopeLogicAnalyzer(Module, AutoCSR):
    def __init__(self, layout, depth,
            with_input_buffer=False,
            with_rle=False, rle_length=256,
            with_subsampler=False,
            clk_domain="sys", clk_ratio=1):
        self.layout = layout
        self.data = Cat(*layout)
        self.dw = len(self.data)
        if with_rle:
            self.dw = max(self.dw, log2_int(rle_length))
            self.dw += 1
        self.depth = depth
        self.with_rle = with_rle
        self.rle_length = rle_length
        self.with_input_buffer = with_input_buffer
        self.with_subsampler = with_subsampler
        self.clk_domain = clk_domain
        self.clk_ratio = clk_ratio

        self.sink = stream.Endpoint(data_layout(self.dw))
        self.comb += [
            self.sink.valid.eq(1),
            self.sink.data.eq(self.data)
        ]

        self.submodules.trigger = trigger = LiteScopeTrigger(self.dw*self.clk_ratio)
        self.submodules.recorder = recorder = LiteScopeRecorder(self.dw*self.clk_ratio, self.depth)

    def do_finalize(self):
        sink = self.sink
        # insert Buffer on sink (optional, can be used to improve timings)
        if self.with_input_buffer:
            input_buffer = Buffer(self.sink.description)
            if self.clk_domain is not "sys":
                self.submodules += ClockDomainsRenamer(self.clk_domain)(input_buffer)
            else:
                self.submodules += input_buffer
            self.comb += sink.connect(intput_buffer.sink)
            sink = input_buffer.source

        # clock domain crossing (optional, required when capture_clk is not sys_clk)
        if self.clk_domain is not "sys":
            converter = StrideConverter(data_layout(self.dw),
                                        data_layout(self.dw*self.clk_ratio))
            self.submodules += ClockDomainsRenamer(self.clk_domain)(converter)
            fifo = AsyncFIFO(converter.source.description, 32)
            self.submodules += ClockDomainsRenamer({"write": self.clk_domain, "read": "sys"})(fifo)
            self.comb += [
                sink.connect(converter.sink),
                converter.source.connect(fifo.sink)
            ]
            sink = fifo.source

        # connect trigger
        self.comb += [
            self.trigger.sink.valid.eq(sink.valid),
            self.trigger.sink.data.eq(sink.data),
        ]

        # insert subsampler (optional)
        if self.with_subsampler:
            self.submodules.subsampler = LiteScopeSubSampler(self.dw)
            self.comb += sink.connect(self.subsampler.sink)
            sink = self.subsampler.source

        # connect recorder
        self.comb += self.trigger.source.connect(self.recorder.trigger_sink)
        if self.with_rle:
            self.submodules.rle = LiteScopeRunLengthEncoder(self.dw, self.rle_length)
            self.comb += [
                sink.connect(self.rle.sink),
                self.rle.source.connect(self.recorder.data_sink),
                self.rle.external_enable.eq(self.recorder.post_hit)
            ]
        else:
            self.submodules.delay_buffer = Buffer(sink.description)
            self.comb += [
                sink.connect(self.delay_buffer.sink),
                self.delay_buffer.source.connect(self.recorder.data_sink)
            ]

    def export(self, vns, filename):
        def format_line(*args):
            return ",".join(args) + "\n"
        r = ""
        r += format_line("config", "dw", str(self.dw))
        r += format_line("config", "depth", str(self.depth))
        r += format_line("config", "with_rle", str(int(self.with_rle)))
        r += format_line("config", "clk_ratio", str(int(self.clk_ratio)))
        if not isinstance(self.layout, tuple):
            self.layout = [self.layout]
        for e in self.layout:
            r += format_line("layout", vns.get_name(e), str(len(e)))
        write_to_file(filename, r)
