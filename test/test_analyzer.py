#
# This file is part of LiteScope.
#
# Copyright (c) 2017-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import tempfile

from migen import *

from litescope import LiteScopeAnalyzer
from litescope.software.dump.common import DumpData


def read_capture(analyzer):
    data = []
    while (yield from analyzer.storage.mem_level.read()) > 0:
        data.append((yield from analyzer.storage.mem_data.read()))
        yield
    return data


def read_capture_words(analyzer, length):
    data = []
    for i in range(length):
        data.append((yield from analyzer.storage.mem_data.read()))
        yield
    return data


class TestAnalyzer(unittest.TestCase):
    def test_analyzer(self):
        def generator(dut):
            dut.data = []
            # Configure Trigger
            yield from dut.analyzer.trigger.mem_value.write(0x0010)
            yield from dut.analyzer.trigger.mem_mask.write(0xffff)
            yield from dut.analyzer.trigger.mem_write.write(1)

            # Configure Subsampler
            yield from dut.analyzer.subsampler.value.write(2)

            # Configure Storage
            yield from dut.analyzer.storage.length.write(256)
            yield from dut.analyzer.storage.offset.write(8)
            yield from dut.analyzer.storage.enable.write(1)
            yield
            for i in range(16):
                yield
            # Wait capture
            while not (yield from dut.analyzer.storage.done.read()):
                yield
            # Read captured datas
            dut.data = (yield from read_capture(dut.analyzer))

        class DUT(Module):
            def __init__(self):
                counter = Signal(32)
                self.sync += counter.eq(counter + 1)
                self.submodules.analyzer = LiteScopeAnalyzer(counter, 512)

        dut = DUT()
        generators = {"sys" : [generator(dut)]}
        clocks     = {"sys": 10, "scope": 10}
        run_simulation(dut, generators, clocks, vcd_name="sim.vcd")
        self.assertEqual(dut.data, [524 + 3*i for i in range(len(dut.data))])

    def test_analyzer_group_mux(self):
        def generator(dut):
            yield from dut.analyzer.mux.value.write(1)

            # Trigger on the second group and verify captured data comes from it.
            yield from dut.analyzer.trigger.mem_value.write(0xb0)
            yield from dut.analyzer.trigger.mem_mask.write(0xff)
            yield from dut.analyzer.trigger.mem_write.write(1)

            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(16)
            yield from dut.analyzer.storage.offset.write(0)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            yield
            for i in range(16):
                yield

            while not (yield from dut.analyzer.storage.done.read()):
                yield
            dut.data = (yield from read_capture(dut.analyzer))

        class DUT(Module):
            def __init__(self):
                counter = Signal(8)
                other   = Signal(8, reset=0xa0)
                self.sync += [
                    counter.eq(counter + 1),
                    other.eq(other + 3),
                ]
                self.submodules.analyzer = LiteScopeAnalyzer({
                    0: counter,
                    1: other,
                }, 64, csr_csv=None)

        dut = DUT()
        generators = {"sys" : [generator(dut)]}
        clocks     = {"sys": 10, "scope": 10}
        run_simulation(dut, generators, clocks)
        self.assertEqual(dut.data, [132 + 3*i for i in range(len(dut.data))])

    def test_analyzer_raw_msb_data_without_rle(self):
        def generator(dut):
            yield from dut.analyzer.trigger.mem_value.write(0)
            yield from dut.analyzer.trigger.mem_mask.write(0)
            yield from dut.analyzer.trigger.mem_write.write(1)

            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(8)
            yield from dut.analyzer.storage.offset.write(0)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            yield

            seen_busy = False
            for i in range(128):
                done = (yield from dut.analyzer.storage.done.read())
                if not done:
                    seen_busy = True
                elif seen_busy:
                    break
                yield
            else:
                raise TimeoutError("Raw capture did not complete")

            dut.data = (yield from read_capture_words(dut.analyzer, 8))

        class DUT(Module):
            def __init__(self):
                counter = Signal(8, reset=0x80)
                self.sync += counter.eq(counter + 1)
                self.submodules.analyzer = LiteScopeAnalyzer(counter, 16, csr_csv=None)

        dut = DUT()
        generators = {"sys" : [generator(dut)]}
        clocks     = {"sys": 10, "scope": 10}
        run_simulation(dut, generators, clocks)
        self.assertEqual(dut.analyzer.data_width, 8)
        self.assertEqual(dut.analyzer.storage_width, 8)
        self.assertFalse(hasattr(dut.analyzer, "rle"))
        self.assertTrue(all(sample & 0x80 for sample in dut.data))
        self.assertEqual(dut.data, list(range(dut.data[0], dut.data[0] + len(dut.data))))

    def test_analyzer_rle_constant_signal(self):
        def generator(dut):
            yield from dut.analyzer.trigger.mem_value.write(0)
            yield from dut.analyzer.trigger.mem_mask.write(0)
            yield from dut.analyzer.trigger.mem_write.write(1)

            yield from dut.analyzer.rle.enable.write(1)
            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(4)
            yield from dut.analyzer.storage.offset.write(0)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            yield

            seen_busy = False
            for i in range(128):
                done = (yield from dut.analyzer.storage.done.read())
                if not done:
                    seen_busy = True
                elif seen_busy:
                    break
                yield
            else:
                raise TimeoutError("RLE capture did not complete")

            dut.data = (yield from read_capture_words(dut.analyzer, 4))

        class DUT(Module):
            def __init__(self):
                value = Signal(4, reset=5)
                self.submodules.analyzer = LiteScopeAnalyzer(value, 16,
                    with_rle   = True,
                    rle_length = 4,
                    csr_csv    = None)

        dut = DUT()
        generators = {"sys" : [generator(dut)]}
        clocks     = {"sys": 10, "scope": 10}
        run_simulation(dut, generators, clocks)
        self.assertEqual(dut.analyzer.data_width, 4)
        self.assertEqual(dut.analyzer.storage_width, 5)
        self.assertEqual(dut.data, [5, 5, 0x10 | 3, 0x10 | 1])

        encoded = DumpData(dut.analyzer.storage_width)
        encoded.extend(dut.data)
        decoded = encoded.decode_rle(data_width=dut.analyzer.data_width)
        self.assertEqual(list(decoded), [5]*6)

    def test_analyzer_rle_changing_runs(self):
        def generator(dut):
            yield from dut.analyzer.trigger.mem_value.write(0)
            yield from dut.analyzer.trigger.mem_mask.write(0)
            yield from dut.analyzer.trigger.mem_write.write(1)

            yield from dut.analyzer.rle.enable.write(1)
            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(12)
            yield from dut.analyzer.storage.offset.write(0)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            yield

            seen_busy = False
            for i in range(256):
                done = (yield from dut.analyzer.storage.done.read())
                if not done:
                    seen_busy = True
                elif seen_busy:
                    break
                yield
            else:
                raise TimeoutError("RLE mixed-run capture did not complete")

            dut.data = (yield from read_capture_words(dut.analyzer, 12))

        class DUT(Module):
            def __init__(self):
                counter = Signal(8)
                value   = Signal(4)
                self.sync += counter.eq(counter + 1)
                self.comb += value.eq(counter[2:6])
                self.submodules.analyzer = LiteScopeAnalyzer(value, 64,
                    with_rle   = True,
                    rle_length = 8,
                    csr_csv    = None)

        dut = DUT()
        generators = {"sys" : [generator(dut)]}
        clocks     = {"sys": 10, "scope": 10}
        run_simulation(dut, generators, clocks)

        encoded = DumpData(dut.analyzer.storage_width)
        encoded.extend(dut.data)
        decoded = encoded.decode_rle(data_width=dut.analyzer.data_width)
        decoded_samples = list(decoded)

        self.assertTrue(any(word & 0x10 for word in encoded))
        self.assertGreater(len(decoded_samples), len(encoded))
        self.assertGreater(len(set(decoded_samples)), 3)
        self.assertTrue(all(b in (a, a + 1) for a, b in zip(decoded_samples, decoded_samples[1:])))

    def test_analyzer_rle_disabled_keeps_raw_capture(self):
        def generator(dut):
            yield from dut.analyzer.trigger.mem_value.write(0)
            yield from dut.analyzer.trigger.mem_mask.write(0)
            yield from dut.analyzer.trigger.mem_write.write(1)

            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(8)
            yield from dut.analyzer.storage.offset.write(0)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            yield

            seen_busy = False
            for i in range(128):
                done = (yield from dut.analyzer.storage.done.read())
                if not done:
                    seen_busy = True
                elif seen_busy:
                    break
                yield
            else:
                raise TimeoutError("RLE-disabled capture did not complete")

            dut.data = (yield from read_capture_words(dut.analyzer, 8))

        class DUT(Module):
            def __init__(self):
                counter = Signal(8)
                self.sync += counter.eq(counter + 1)
                self.submodules.analyzer = LiteScopeAnalyzer(counter, 16,
                    with_rle   = True,
                    rle_length = 8,
                    csr_csv    = None)

        dut = DUT()
        generators = {"sys" : [generator(dut)]}
        clocks     = {"sys": 10, "scope": 10}
        run_simulation(dut, generators, clocks)
        self.assertEqual(dut.analyzer.data_width, 8)
        self.assertEqual(dut.analyzer.storage_width, 9)
        self.assertEqual(dut.data, list(range(dut.data[0], dut.data[0] + len(dut.data))))

    def test_format_groups_splits_records_and_deduplicates(self):
        signal = Signal(1)
        record = Record([("field0", 3), ("field1", 5)])

        analyzer = LiteScopeAnalyzer([signal, signal, record], 16, csr_csv=None)

        self.assertEqual(analyzer.groups[0], [signal, record.field0, record.field1])
        self.assertEqual(analyzer.data_width, 9)

    def test_export_csv(self):
        signal_a = Signal(3)
        signal_b = Signal(5)
        analyzer = LiteScopeAnalyzer({
            0: signal_a,
            1: signal_b,
        }, depth=32, samplerate=125e6, csr_csv=None)

        class VNS:
            def get_name(self, signal):
                return {
                    signal_a: "signal_a",
                    signal_b: "signal_b",
                }[signal]

        with tempfile.NamedTemporaryFile() as f:
            analyzer.export_csv(VNS(), f.name)
            with open(f.name) as csv_file:
                lines = csv_file.read().splitlines()

        self.assertEqual(lines, [
            "config,None,data_width,5",
            "config,None,storage_width,5",
            "config,None,depth,32",
            "config,None,samplerate,125000000",
            "config,None,with_rle,0",
            "config,None,rle_length,256",
            "signal,0,signal_a,3",
            "signal,1,signal_b,5",
        ])
