#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2017 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math
import shutil
import zipfile
import re
from collections import OrderedDict

from litescope.software.dump.common import Dump, DumpVariable


class SigrokDump(Dump):
    def __init__(self, dump=None, samplerate=None):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables
        self.samplerate = 100e6 if samplerate is None else samplerate

    def write_version(self):
        f = open("version", "w")
        f.write("1")
        f.close()

    def write_metadata(self, name):
        probe_bits = math.ceil(sum(variable.width for variable in self.variables)/8)*8
        f = open("metadata", "w")
        r = """
[global]
sigrok version=0.3.0
[device 1]
capturefile=logic-1-1
total probes={}
samplerate={} MHz
unitsize={}
""".format(
        probe_bits,
        self.samplerate//1e6*2,
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

    def write_data(self):
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
        f = open("logic-1-1", "wb")
        for data in datas:
            f.write(data.to_bytes(data_bits//8, "little"))
        f.close()

    def zip(self, name):
        f = zipfile.ZipFile(name + ".sr", "w")
        os.chdir(name)
        f.write("version")
        f.write("metadata")
        f.write("logic-1-1")
        os.chdir("..")
        f.close()

    def write(self, filename):
        name, ext = os.path.splitext(filename)
        if os.path.exists(name):
            shutil.rmtree(name)
        os.makedirs(name)
        os.chdir(name)
        self.write_version()
        self.write_metadata(name)
        self.write_data()
        os.chdir("..")
        self.zip(name)
        shutil.rmtree(name)

    def unzip(self, filename, name):
        f = open(filename, "rb")
        z = zipfile.ZipFile(f)
        if os.path.exists(name):
            shutil.rmtree(name)
            os.makedirs(name)
        for file in z.namelist():
            z.extract(file, name)
        f.close()

    def read_metadata(self):
        probes = OrderedDict()
        f = open("metadata", "r")
        for l in f:
            m = re.search("probe([0-9]+) = (\w+)", l, re.I)
            if m is not None:
                index = int(m.group(1))
                name = m.group(2)
                probes[name] = index
            m = re.search("samplerate = ([0-9]+) kHz", l, re.I)
            if m is not None:
                self.samplerate = int(m.group(1))*1000
            m = re.search("samplerate = ([0-9]+) MHz", l, re.I)
            if m is not None:
                self.samplerate = int(m.group(1))*1000000
        f.close()
        return probes

    def read_data(self, name, nprobes):
        datas = []
        f = open("logic-1-1", "rb")
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
        name, ext = os.path.splitext(filename)
        self.unzip(filename, name)
        os.chdir(name)
        probes = self.read_metadata()
        datas = self.read_data(name, len(probes.keys()))
        os.chdir("..")
        shutil.rmtree(name)

        for k, v in probes.items():
            probe_data = []
            for data in datas:
                probe_data.append((data >> (v-1)) & 0x1)
            self.add(DumpVariable(k, 1, probe_data))
