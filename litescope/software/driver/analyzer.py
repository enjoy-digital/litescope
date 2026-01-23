#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 kees.jongenburger <kees.jongenburger@gmail.com>
# Copyright (c) 2018 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import sys
import time

from migen import *

from litescope.software.dump.common import *
from litescope.software.dump import *

import csv


class LiteScopeAnalyzerDriver:
    # Logging / UI helpers -------------------------------------------------------------------------
    def _log(self, msg):
        if self.debug:
            print(f"{self.name}: {msg}")

    def _progress(self, cur, total, width=20):
        # Only show progress when debugging (keeps normal usage quiet and preserves scripts' stdout).
        if not self.debug:
            return
        if total <= 0:
            return
        if cur < 0:
            cur = 0
        if cur > total:
            cur = total
        done = (width * cur) // total
        sys.stdout.write(f"\r{self.name}: [{'='*done}{' '*(width-done)}] {(100*cur)//total}%")
        sys.stdout.flush()

    def _progress_end(self):
        if self.debug:
            sys.stdout.write("\n")
            sys.stdout.flush()

    # Driver --------------------------------------------------------------------------------------
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
                            v |= int(c, 16 if mx is not None else 2 )
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
        self.subsampling = value
        self.subsampler_value.write(value-1)

    def run(self, offset=0, length=None):
        if length is None:
            length = self.depth
        assert offset < self.depth
        assert length <= self.depth
        self.offset = offset
        self.length = length
        if self.debug:
            self._log(f"run (offset={offset}, length={length})")
        self.storage_offset.write(offset)
        self.storage_length.write(length)
        self.storage_enable.write(1)
        self.trigger_enable.write(1)

    def clear(self):
        self.data = DumpData(self.data_width)
        self.offset = 0
        self.length = None
        self.trigger_enable.write(0)
        self.storage_enable.write(0)

    def done(self):
        return self.storage_done.read()

    def wait_done(self, delay=0.2):
        if self.debug:
            self._log(f"wait_done (delay={delay}s)")
        while not self.done():
            if delay:
                time.sleep(delay)

    def upload(self):
        length = self.storage_mem_level.read()
        if self.debug:
            self._log(f"upload (words={length})")

        remaining = length
        swpw = (self.data_width + 31) // 32 # Sub-Words per word
        mwbl = 192 // swpw                  # Max Burst len (in # of words)

        cur = 0
        self._progress(0, length)

        while remaining > 0:
            rdw  = min(remaining, mwbl)
            rdsw = rdw * swpw
            datas = self.storage_mem_data.readfn(self.storage_mem_data.addr, length=rdsw, burst="fixed")

            for i, sv in enumerate(datas):
                j = i % swpw
                if j == 0:
                    v = 0
                v |= sv << (32 * j)
                if j == (swpw - 1):
                    self.data.append(v)

            remaining -= rdw
            cur += rdw
            self._progress(cur, length)

        self._progress_end()
        return self.data

    def save(self, filename, samplerate=None, flatten=False):
        if samplerate is None:
            samplerate = self.samplerate / self.subsampling
        if self.debug:
            self._log(f"write {filename}")

        name, ext = os.path.splitext(filename)
        if ext == ".vcd":
            dump = VCDDump(samplerate=samplerate)
        elif ext == ".csv":
            dump = CSVDump()
        elif ext == ".py":
            dump = PythonDump()
        elif ext == ".json":
            dump = JSONDump()
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
