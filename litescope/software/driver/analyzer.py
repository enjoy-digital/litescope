import os
import sys

from litex.gen.fhdl.structure import *
from litescope.software.dump.common import *
from litescope.software.dump import *

import csv


class LiteScopeAnalyzerDriver:
    def __init__(self, regs, name, config_csv=None, debug=False):
        self.regs = regs
        self.name = name
        self.config_csv = config_csv
        if self.config_csv is None:
            self.config_csv = name + ".csv"
        self.debug = debug
        self.get_config()
        self.get_layouts()
        self.build()
        self.group = 0
        self.data = DumpData(self.dw)

    def get_config(self):
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            t, g, n, v = item
            if t == "config":
                setattr(self, n, int(v))

    def get_layouts(self):
        self.layouts = {}
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            t, g, n, v = item
            if t == "signal":
                try:
                    self.layouts[int(g)].append((n, int(v)))
                except:
                    self.layouts[int(g)] = [(n, int(v))]

    def build(self):
        for key, value in self.regs.d.items():
            if self.name == key[:len(self.name)]:
                key = key.replace(self.name + "_", "")
                setattr(self, key, value)
        value = 1
        for signals in self.layouts.values():
            for name, length in signals:
                setattr(self, name + "_o", value)
                value = value*(2**length)
        value = 0
        for signals in self.layouts.values():
            for name, length in signals:
                setattr(self, name + "_m", (2**length-1) << value)
                value += length

    def configure_group(self, value):
        self.group = value
        self.mux_value.write(value)

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

    def run(self, offset, length):
        while self.storage_mem_valid.read():
            self.storage_mem_ready.write(1)
        if self.debug:
            print("[running]...")
        self.storage_offset.write(offset)
        self.storage_length.write(length)
        self.storage_start.write(1)

    def done(self):
        return self.storage_idle.read()

    def wait_done(self):
        while not self.done:
            pass

    def upload(self):
        if self.debug:
            print("[uploading]...")
        length = self.storage_length.read()//self.cd_ratio
        for position in range(1, length + 1):
            if self.debug:
                sys.stdout.write("|{}>{}| {}%\r".format('=' * (20*position//length),
                                                        ' ' * (20-20*position//length),
                                                        100*position//length))
                sys.stdout.flush()
            self.data.append(self.storage_mem_data.read())
            self.storage_mem_ready.write(1)
        if self.debug:
            print("")
        if self.cd_ratio > 1:
            new_data = DumpData(self.dw)
            for data in self.data:
                for i in range(self.cd_ratio):
                    new_data.append(*get_bits([data], i*self.dw, (i+1)*self.dw))
            self.data = new_data
        return self.data

    def save(self, filename, samplerate=None):
        if self.debug:
            print("[writing to " + filename + "]...")
        name, ext = os.path.splitext(filename)
        if ext == ".vcd":
            dump = VCDDump()
        elif ext == ".csv":
            dump = CSVDump()
        elif ext == ".py":
            dump = PythonDump()
        elif ext == ".sr":
            dump = SigrokDump(samplerate=samplerate)
        else:
            raise NotImplementedError
        dump.add_from_layout(self.layouts[self.group], self.data)
        dump.write(filename)
