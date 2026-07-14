#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
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

    def _limit_samples(self, data, max_samples):
        if max_samples is None:
            return data
        if max_samples < 0:
            raise ValueError("max_samples must be >= 0")
        limited = DumpData(data.width)
        limited.extend(list(data)[:max_samples])
        return limited

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
        self.rle_enabled = False
        self.data = DumpData(self.data_width)

        self.offset = 0
        self.length = None

        # Configured trigger terms (mask, value); loaded into the gateware on each run() since
        # the trigger memory consumes its terms on every capture.
        self.trigger_terms = []

        # Disable trigger and storage
        self.trigger_enable.write(0)
        self.storage_enable.write(0)
        if hasattr(self, "rle_enable"):
            self.rle_enable.write(0)

    def get_config(self):
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            if len(item) < 4:
                continue
            t, g, n, v = item[:4]
            if t == "config":
                setattr(self, n, int(v))
        self.storage_width     = getattr(self, "storage_width", self.data_width)
        self.with_rle          = getattr(self, "with_rle", 0)
        self.rle_length        = getattr(self, "rle_length", 0)
        self.subsampler_width = getattr(self, "subsampler_width", 16)

    def get_layouts(self):
        self.layouts = {}
        self.enums   = {}
        csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
        for item in csv_reader:
            if len(item) < 4:
                continue
            t, g, n, v = item[:4]
            if t == "signal":
                try:
                    self.layouts[int(g)].append((n, int(v)))
                except:
                    self.layouts[int(g)] = [(n, int(v))]
            if t == "enum" and len(item) >= 5:
                self.enums.setdefault((int(g), n), {})[int(v, 0)] = item[4]

    def build(self):
        for key, value in self.regs.d.items():
            if self.name == key[:len(self.name)]:
                key = key.replace(self.name + "_", "")
                setattr(self, key, value)
        # Group-aware signal offsets/masks: triggers must resolve a signal's position in the
        # currently selected group (a signal present in several groups can sit at different
        # positions in each).
        self.signal_offsets = {}
        self.signal_masks   = {}
        for group, signals in self.layouts.items():
            value = 1
            for name, length in signals:
                self.signal_offsets[(group, name)] = value
                value = value*(2**length)
            value = 0
            for name, length in signals:
                self.signal_masks[(group, name)] = (2**length-1) << value
                value += length
        # Keep the flat <name>_o/<name>_m attributes for compatibility; warn when a signal is
        # ambiguous across groups (the flat attribute then reflects the last group only).
        ambiguous = set()
        for (group, name), offset in self.signal_offsets.items():
            mask = self.signal_masks[(group, name)]
            if hasattr(self, name + "_o") and \
               ((getattr(self, name + "_o") != offset) or (getattr(self, name + "_m") != mask)):
                ambiguous.add(name)
            setattr(self, name + "_o", offset)
            setattr(self, name + "_m", mask)
        for name in sorted(ambiguous):
            print(f"{self.name}: warning: signal '{name}' is present in several groups at "
                   "different positions; triggers resolve it in the selected group.")

    def _signal_offset(self, name):
        return self.signal_offsets.get((self.group, name), getattr(self, name + "_o"))

    def _signal_mask(self, name):
        return self.signal_masks.get((self.group, name), getattr(self, name + "_m"))

    def configure_group(self, value):
        self.group = value
        self.mux_value.write(value)

    def add_trigger(self, value=0, mask=0, cond=None):
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
                    value |= self._signal_offset(k)*v
                    mask  |= self._signal_mask(k) & (self._signal_offset(k)*m)
                # Else convert to int
                else:
                    value |= self._signal_offset(k)*int(v, 0)
                    mask  |= self._signal_mask(k)
        self.trigger_terms.append((mask, value))

    def add_rising_edge_trigger(self, name):
        self.add_trigger(self._signal_offset(name)*0, self._signal_mask(name))
        self.add_trigger(self._signal_offset(name)*1, self._signal_mask(name))

    def add_falling_edge_trigger(self, name):
        self.add_trigger(self._signal_offset(name)*1, self._signal_mask(name))
        self.add_trigger(self._signal_offset(name)*0, self._signal_mask(name))

    def _load_trigger_terms(self, timeout=1.0):
        # Disarm the trigger; the gateware flushes any leftover terms (previous capture,
        # aborted sequence) on the falling edge of enable.
        self.trigger_enable.write(0)
        # The flush window is 2*trigger_depth scope cycles; any CSR access takes far longer,
        # but poll done (trigger memory empty) so the reload below cannot race the flush.
        deadline = time.time() + timeout
        for _ in range(2):
            while not self.trigger_done.read():
                if time.time() > deadline:
                    raise TimeoutError("Trigger memory flush timeout")
        # (Re-)load the configured terms so a capture can be re-run without reconfiguring:
        # the trigger memory consumes its terms on every capture.
        for mask, value in self.trigger_terms:
            if self.trigger_mem_full.read():
                raise ValueError("Trigger memory full, too much conditions")
            self.trigger_mem_mask.write(mask)
            self.trigger_mem_value.write(value)
            self.trigger_mem_write.write(1)

    def configure_trigger(self, value=0, mask=0, cond=None):
        self.add_trigger(value, mask, cond)

    def configure_subsampler(self, value):
        if value < 1:
            raise ValueError("Subsampling must be >= 1")
        max_subsampling = 2**self.subsampler_width
        if value > max_subsampling:
            raise ValueError("Subsampling must be <= {:d}".format(max_subsampling))
        self.subsampling = value
        self.subsampler_value.write(value-1)

    def configure_rle(self, enable=True):
        if not self.with_rle or not hasattr(self, "rle_enable"):
            if enable:
                raise ValueError("RLE is not available on this analyzer")
            self.rle_enabled = False
            return
        self.rle_enabled = bool(enable)
        self.rle_enable.write(int(enable))

    def run(self, offset=0, length=None):
        if length is None:
            length = self.depth
        assert offset < self.depth
        assert length <= self.depth
        self.offset = offset
        self.length = length
        if self.debug:
            self._log(f"run (offset={offset}, length={length})")
        # Disarm the trigger and reload its terms first: a previous capture leaves the trigger
        # armed with an empty (fully consumed) term memory, whose hit output is a constant
        # level that would otherwise fire the re-armed storage immediately. With the terms
        # reloaded, hit stays low until a real match.
        self._load_trigger_terms()
        self.storage_offset.write(offset)
        self.storage_length.write(length)
        # Storage arms on the rising edge of enable: clear it first so run() also re-arms
        # after a previous capture on the same driver instance.
        self.storage_enable.write(0)
        self.storage_enable.write(1)
        self.trigger_enable.write(1)

    def clear(self):
        self.data = DumpData(self.data_width)
        self.offset = 0
        self.length = None
        self.rle_enabled = False
        self.trigger_terms = []
        self.trigger_enable.write(0)
        self.storage_enable.write(0)
        if hasattr(self, "rle_enable"):
            self.rle_enable.write(0)

    def done(self):
        return self.storage_done.read()

    def wait_done(self, delay=0.2):
        if self.debug:
            self._log(f"wait_done (delay={delay}s)")
        while not self.done():
            if delay:
                time.sleep(delay)

    def upload(self, max_samples=None):
        length = self.storage_mem_level.read()
        if self.debug:
            self._log(f"upload (words={length})")

        remaining = length
        swpw = (self.storage_width + 31) // 32 # Sub-Words per word
        mwbl = 192 // swpw                     # Max Burst len (in # of words)
        storage_data = DumpData(self.storage_width)

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
                    storage_data.append(v)

            remaining -= rdw
            cur += rdw
            self._progress(cur, length)

        self._progress_end()
        if self.with_rle:
            if self.rle_enabled:
                self.data = storage_data.decode_rle(data_width=self.data_width)
            else:
                data_mask = 2**self.data_width - 1
                self.data = DumpData(self.data_width)
                self.data.extend([d & data_mask for d in storage_data])
        else:
            self.data = storage_data
        self.data = self._limit_samples(self.data, max_samples)
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
            enums = {
                name: self.enums[(self.group, name)]
                for name, width in self.layouts[self.group]
                if (self.group, name) in self.enums
            }
            dump.add_from_layout(self.layouts[self.group], self.data, enums=enums)
        else:
            dump.add_from_layout_flatten(self.layouts[self.group], self.data)
        dump.add_scope_clk()
        dump.add_scope_trig(self.offset)

        if ext == ".vcd" and not flatten:
            gtkw_filters = self.write_gtkw_filters(filename)
            if gtkw_filters:
                dump.write(filename, gtkw_filters=gtkw_filters)
            else:
                dump.write(filename)
        else:
            dump.write(filename)

    def write_gtkw_filters(self, filename):
        gtkw_filters = {}
        dirname      = os.path.dirname(filename)
        basename     = os.path.splitext(os.path.basename(filename))[0]
        for name, width in self.layouts[self.group]:
            enum = self.enums.get((self.group, name), None)
            if enum is None:
                continue
            filter_name = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{basename}_{name}.txt")
            filter_path = os.path.join(dirname, filter_name)
            with open(filter_path, "w") as f:
                for value, label in sorted(enum.items()):
                    f.write(f"{value} {label}\n")
            gtkw_filters[name] = filter_path
        return gtkw_filters

    def get_instant_value(self, group, name):
        self.data = DumpData(self.data_width)
        self.debug = False
        self.configure_group(group)
        self.trigger_terms = []
        self.configure_trigger()
        self.configure_subsampler(1)
        self.run(0, 1)
        self.wait_done()
        self.upload()
        min_idx = log2_int(self._signal_offset(name))
        max_idx = min_idx + log2_int((self._signal_mask(name) >> min_idx) + 1)
        return self.data[min_idx:max_idx][0]
