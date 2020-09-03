#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 kees.jongenburger <kees.jongenburger@gmail.com>
# Copyright (c) 2018 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import re

from migen import *

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
        self.data = DumpData(self.data_width)

        self.offset = 0
        self.length = None

        # Disable trigger and storage
        self.trigger_enable.write(0)
        self.storage_enable.write(0)

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
        for signals in self.layouts.values():
            value = 1
            for name, length in signals:
                setattr(self, name + "_o", value)
                value = value*(2**length)
        for signals in self.layouts.values():
            value = 0
            for name, length in signals:
                setattr(self, name + "_m", (2**length-1) << value)
                value += length

    def configure_group(self, value):
        self.group = value
        self.mux_value.write(value)

    def add_trigger(self, value=0, mask=0, cond=None):
        if self.trigger_mem_full.read():
            raise ValueError("Trigger memory full, too much conditions")
        if cond is not None:
            for k, v in cond.items():
                # Check for binary/hexa expressions
                mb = re.match("0b([01x]+)",  v)
                mx = re.match("0x([0-fx]+)", v)
                m  = mb or mx
                if m is not None:
                    b = m.group(1)
                    v = 0
                    m = 0
                    for c in b:
                        v <<= 4 if mx is not None else 1
                        m <<= 4 if mx is not None else 1
                        if c != "x":
                            v |= int(c)
                            m |= 0xf if mx is not None else 0b1
                    value |= getattr(self, k + "_o")*v
                    mask  |= getattr(self, k + "_m") & (getattr(self, k + "_o")*m)
                # Else convert to int
                else:
                    value |= getattr(self, k + "_o")*int(v, 0)
                    mask  |= getattr(self, k + "_m")
        self.trigger_mem_mask.write(mask)
        self.trigger_mem_value.write(value)
        self.trigger_mem_write.write(1)

    def add_rising_edge_trigger(self, name):
        self.add_trigger(getattr(self, name + "_o")*0, getattr(self, name + "_m"))
        self.add_trigger(getattr(self, name + "_o")*1, getattr(self, name + "_m"))

    def add_falling_edge_trigger(self, name):
        self.add_trigger(getattr(self, name + "_o")*1, getattr(self, name + "_m"))
        self.add_trigger(getattr(self, name + "_o")*0, getattr(self, name + "_m"))

    def configure_trigger(self, value=0, mask=0, cond=None):
        self.add_trigger(value, mask, cond)

    def configure_subsampler(self, value):
        self.subsampler_value.write(value-1)

    def run(self, offset=0, length=None):
        if length is None:
            length = self.depth
        assert offset < self.depth
        assert length <= self.depth
        self.offset = offset
        self.length = length
        if self.debug:
            print("[running]...")
        self.storage_offset.write(offset)
        self.storage_length.write(length)
        self.storage_enable.write(1)
        self.trigger_enable.write(1)

    def done(self):
        return self.storage_done.read()

    def wait_done(self):
        while not self.done():
            pass

    def upload(self):
        if self.debug:
            print("[uploading]...")
        length = self.storage_length.read()
        for position in range(1, length + 1):
            if self.debug:
                sys.stdout.write("[{}>{}] {}%\r".format('=' * (20*position//length),
                                                        ' ' * (20-20*position//length),
                                                        100*position//length))
                sys.stdout.flush()
            if not self.storage_mem_valid.read():
                break
            self.data.append(self.storage_mem_data.read())
        if self.debug:
            print("")
        return self.data

    def save(self, filename, samplerate=None, flatten=False):
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
        if not flatten:
            dump.add_from_layout(self.layouts[self.group], self.data)
        else:
            dump.add_from_layout_flatten(self.layouts[self.group], self.data)
        dump.add_scope_clk()
        dump.add_scope_trig(self.offset)
        dump.write(filename)

    def get_instant_value(self, group, name):
        self.data = DumpData(self.data_width)
        self.debug = False
        self.configure_group(group)
        self.configure_trigger()
        self.configure_subsampler(1)
        self.run(0, 1)
        self.wait_done()
        self.upload()
        min_idx = log2_int(getattr(self, name + "_o"))
        max_idx = min_idx + log2_int((getattr(self, name + "_m") >> min_idx) + 1)
        return self.data[min_idx:max_idx][0]
