#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math
import zipfile
import tempfile
import re
from collections import OrderedDict

from litescope.software.dump.common import Dump, DumpVariable


class SigrokDump(Dump):
    def __init__(self, dump=None, samplerate=None):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables
        self.samplerate = 100e6 if samplerate is None else samplerate

    def write_version(self, path):
        f = open(os.path.join(path, "version"), "w")
        f.write("1")
        f.close()

    @staticmethod
    def samplerate_string(samplerate):
        # Largest unit that gives a whole number (as sigrok writes it): no rounding to MHz.
        samplerate = int(round(samplerate))
        for unit, scale in [("GHz", 10**9), ("MHz", 10**6), ("kHz", 10**3)]:
            if (samplerate >= scale) and (samplerate % scale == 0):
                return "{} {}".format(samplerate//scale, unit)
        return "{} Hz".format(samplerate)

    def write_metadata(self, path):
        probe_bits = math.ceil(sum(variable.width for variable in self.variables)/8)*8
        f = open(os.path.join(path, "metadata"), "w")
        r = """
[global]
sigrok version=0.3.0
[device 1]
capturefile=logic-1-1
total probes={}
samplerate={}
unitsize={}
""".format(
        probe_bits,
        self.samplerate_string(2*self.samplerate), # Each sample is written twice.
        probe_bits//8
    )
        i = 1
        for variable in self.variables:
            if variable.width > 1:
                for j in range(variable.width):
                    r += "probe{}={}[{}]\n".format(i, variable.name, j)
                    i += 1
            else:
                r += "probe{}={}\n".format(i, variable.name)
                i += 1
        f.write(r)
        f.close()

    def write_data(self, path):
        data_bits = math.ceil(sum(variable.width for variable in self.variables)/8)*8
        data_len = 0
        for variable in self.variables:
            data_len = max(data_len, len(variable))
        datas = []
        for i in range(data_len):
            data = 0
            for j, variable in enumerate(reversed(self.variables)):
                data = data << variable.width
                try:
                    data |= variable.values[i]
                except:
                    pass
            datas.append(data)
        f = open(os.path.join(path, "logic-1-1"), "wb")
        for data in datas:
            f.write(data.to_bytes(data_bits//8, "little"))
        f.close()

    def zip(self, path, filename):
        f = zipfile.ZipFile(filename, "w")
        for name in ["version", "metadata", "logic-1-1"]:
            f.write(os.path.join(path, name), arcname=name)
        f.close()

    def write(self, filename):
        # Build the session in a temporary directory (not a directory named after the file, that
        # would be removed if it exists).
        with tempfile.TemporaryDirectory() as path:
            self.write_version(path)
            self.write_metadata(path)
            self.write_data(path)
            self.zip(path, filename)

    def unzip(self, filename, path):
        with zipfile.ZipFile(filename) as z:
            z.extractall(path)

    def read_metadata(self, path):
        probes = OrderedDict()
        f = open(os.path.join(path, "metadata"), "r")
        for l in f:
            m = re.search(r"probe([0-9]+)\s*=\s*(.+)", l, re.I)
            if m is not None:
                index = int(m.group(1))
                name = m.group(2).strip()
                probes[name] = index
            m = re.search(r"samplerate\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*([kMG]?)Hz", l, re.I)
            if m is not None:
                scale = {"": 1, "k": 1e3, "m": 1e6, "g": 1e9}[m.group(2).lower()]
                self.samplerate = float(m.group(1))*scale
        f.close()
        return probes

    def read_data(self, name, nprobes):
        datas = []
        f = open(os.path.join(name, "logic-1-1"), "rb")
        while True:
            data = f.read(math.ceil(nprobes/8))
            if data == bytes('', "utf-8"):
                break
            data = int.from_bytes(data, "little")
            datas.append(data)
        f.close()
        return datas

    def read(self, filename):
        self.variables = []
        with tempfile.TemporaryDirectory() as path:
            self.unzip(filename, path)
            probes = self.read_metadata(path)
            datas  = self.read_data(path, len(probes.keys()))

        for k, v in probes.items():
            probe_data = []
            for data in datas:
                probe_data.append((data >> (v-1)) & 0x1)
            self.add(DumpVariable(k, 1, probe_data))
