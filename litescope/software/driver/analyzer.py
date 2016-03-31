import os

from litex.gen.fhdl.structure import *
from litescope.software.dump.common import *
from litescope.software.dump import *

import csv

class LiteScopeAnalyzerDriver():
    def __init__(self, regs, name, config_csv=None, clk_freq=None, debug=False):
        self.regs = regs
        self.name = name
        self.config_csv = config_csv
        if self.config_csv is None:
            self.config_csv = name + ".csv"
        if clk_freq is None:
            self.clk_freq = None
            self.samplerate = None
        else:
            self.clk_freq = clk_freq
            self.samplerate = clk_freq
        self.debug = debug
        self.get_config()
        self.get_layout()
        self.build()
        self.data = DumpData(self.dw)

    def get_config(self):
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            t, n, v = item
            if t == "config":
                setattr(self, n, int(v))

    def get_layout(self):
        self.layout = []
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            t, n, v = item
            if t == "signal":
                self.layout.append((n, int(v)))

    def build(self):
        for key, value in self.regs.d.items():
            if self.name == key[:len(self.name)]:
                key = key.replace(self.name + "_", "")
                setattr(self, key, value)
        value = 1
        for name, length in self.layout:
            setattr(self, name + "_o", value)
            value = value*(2**length)
        value = 0
        for name, length in self.layout:
            setattr(self, name + "_m", (2**length-1) << value)
            value += length

    def configure_trigger(self, value=0, mask=0, cond=None):
        if cond is not None:
            for k, v in cond.items():
                value |= getattr(self, k + "_o")*v
                mask |= getattr(self, k + "_m")
        t = getattr(self, "frontend_trigger_value")
        m = getattr(self, "frontend_trigger_mask")
        t.write(value)
        m.write(mask)

    def configure_subsampler(self, value):
        self.frontend_subsampler_value.write(value-1)
        if self.clk_freq is not None:
            self.samplerate = self.clk_freq//n
        else:
            self.samplerate = None

    def done(self):
        return self.storage_idle.read()

    def run(self, offset, length):
        while self.storage_mem_valid.read():
            self.storage_mem_ready.write(1)
        if self.debug:
            print("running")
        self.storage_offset.write(offset)
        self.storage_length.write(length)
        self.storage_start.write(1)

    def upload(self):
        if self.debug:
            print("uploading")
        while self.storage_mem_valid.read():
            self.data.append(self.storage_mem_data.read())
            self.storage_mem_ready.write(1)
        if self.cd_ratio > 1:
            new_data = DumpData(self.dw)
            for data in self.data:
                for i in range(self.clk_ratio):
                    new_data.append(*get_bits([data], i*self.dw, (i+1)*self.dw))
            self.data = new_data
        return self.data

    def save(self, filename):
        if self.debug:
            print("saving to " + filename)
        name, ext = os.path.splitext(filename)
        if ext == ".vcd":
            dump = VCDDump()
        elif ext == ".csv":
            dump = CSVDump()
        elif ext == ".py":
            dump = PythonDump()
        elif ext == ".sr":
            if self.samplerate is None:
                raise ValueError("Unable to automatically retrieve clk_freq, clk_freq parameter required")
            dump = SigrokDump(samplerate=self.samplerate)
        else:
            raise NotImplementedError
        dump.add_from_layout(self.layout, self.data)
        dump.write(filename)
