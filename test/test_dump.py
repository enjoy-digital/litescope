#
# This file is part of LiteScope.
#
# Copyright (c) 2017 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import os
from math import cos, sin

from litescope.software.dump import *

#TODO:
# - find a way to check if files are generated correctly

dump = Dump()
for i in range(4):
    dump.add(DumpVariable("ramp"+str(i), 2**i, [j for j in range(256)]))
pi = 3.1415
dump.add(DumpVariable("sin", 8, [128+128*sin(j/(2*pi*16)) for j in range(1024)]))
dump.add(DumpVariable("cos", 8, [128+128*cos(j/(2*pi*16)) for j in range(1024)]))


class TestDump(unittest.TestCase):
    def test_csv(self):
        filename = "dump.csv"
        CSVDump(dump).write(filename)
        os.remove(filename)

    def test_py(self):
        filename = "dump.py"
        PythonDump(dump).write(filename)
        os.remove(filename)

    def test_sigrok(self):
        filename = "dump.sr"
        SigrokDump(dump).write(filename)
        SigrokDump(dump).read(filename)
        SigrokDump(dump).write(filename)
        os.remove(filename)

    def test_vcd(self):
        filename = "dump.vcd"
        VCDDump(dump).write(filename)
        os.remove(filename)
