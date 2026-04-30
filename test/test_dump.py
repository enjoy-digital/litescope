#
# This file is part of LiteScope.
#
# Copyright (c) 2017 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import os
from math import cos, sin

from litescope.software.dump import *
from litescope.software.dump.common import dec2bin

#TODO:
# - find a way to check if files are generated correctly

dump = Dump()
for i in range(4):
    dump.add(DumpVariable("ramp"+str(i), 2**i, [j for j in range(256)]))
pi = 3.1415
dump.add(DumpVariable("sin", 8, [128+128*sin(j/(2*pi*16)) for j in range(1024)]))
dump.add(DumpVariable("cos", 8, [128+128*cos(j/(2*pi*16)) for j in range(1024)]))


class TestDump(unittest.TestCase):
    def test_dec2bin(self):
        self.assertEqual(dec2bin(0, 4), "0000")
        self.assertEqual(dec2bin(5, 4), "0101")
        self.assertEqual(dec2bin("x", 4), "xxxx")

    def test_dumpdata_index_and_slice(self):
        data = DumpData(8)
        data.extend([0b10101100, 0b01010011])

        self.assertEqual(data[0], [0, 1])
        self.assertEqual(data[2:6], [0b1011, 0b0100])
        self.assertEqual(data[:4], [0b1100, 0b0011])
        self.assertEqual(data[4:], [0b1010, 0b0101])
        with self.assertRaises(KeyError):
            data[0:4:2]

    def test_dumpdata_decode_rle(self):
        data = DumpData(5)
        data.extend([
            0x3,          # Raw 3.
            0x10 | 0x2,   # Repeat 3 two times.
            0x7,          # Raw 7.
            0x10 | 0x0,   # Zero-repeat marker.
            0x10 | 0x3,   # Repeat 7 three times.
        ])

        decoded = data.decode_rle()

        self.assertEqual(decoded.width, 4)
        self.assertEqual(list(decoded), [3, 3, 3, 7, 7, 7, 7])

    def test_dumpdata_decode_rle_with_padded_storage_width(self):
        data = DumpData(8)
        data.extend([
            0x23,         # Raw 3 with padding bits set.
            0x80 | 0x6,   # Repeat 3 six times.
            0x0a,         # Raw 10.
            0x80 | 0x1,   # Repeat 10 one time.
        ])

        decoded = data.decode_rle(data_width=4)

        self.assertEqual(decoded.width, 4)
        self.assertEqual(list(decoded), [3, 3, 3, 3, 3, 3, 3, 10, 10])

    def test_dumpdata_decode_rle_empty_and_leading_marker(self):
        data = DumpData(5)
        decoded = data.decode_rle()

        self.assertEqual(decoded.width, 4)
        self.assertEqual(list(decoded), [])

        data.extend([
            0x10 | 0x3,   # Repeat the default previous sample.
            0x6,          # Raw 6.
            0x10 | 0x2,   # Repeat 6 two times.
        ])

        decoded = data.decode_rle()

        self.assertEqual(decoded.width, 4)
        self.assertEqual(list(decoded), [0, 0, 0, 6, 6, 6])

    def test_dumpdata_decode_rle_consecutive_run_markers(self):
        data = DumpData(5)
        data.extend([
            0x9,          # Raw 9.
            0x10 | 0xf,   # Repeat 9 fifteen times.
            0x10 | 0x4,   # Repeat 9 four more times.
            0x2,          # Raw 2.
        ])

        decoded = data.decode_rle()

        self.assertEqual(decoded.width, 4)
        self.assertEqual(list(decoded), [9]*20 + [2])

    def test_add_from_layout(self):
        data = DumpData(8)
        data.extend([0b10110001, 0b01001110])

        dump = Dump()
        dump.add_from_layout([("low", 4), ("high", 4)], data)

        self.assertEqual([(v.name, v.width, v.values) for v in dump.variables], [
            ("low",  4, [0x1, 0x1, 0xe, 0xe]),
            ("high", 4, [0xb, 0xb, 0x4, 0x4]),
        ])

    def test_add_from_layout_flatten(self):
        data = DumpData(4)
        data.extend([0b1010, 0b0101])

        dump = Dump()
        dump.add_from_layout_flatten([("bus", 4)], data)

        self.assertEqual([(v.name, v.width, v.values) for v in dump.variables], [
            ("bus", 1, [0, 1, 0, 1, 1, 0, 1, 0]),
        ])

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
