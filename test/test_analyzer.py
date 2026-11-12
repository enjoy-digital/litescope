#
# This file is part of LiteScope.
#
# Copyright (c) 2017-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re
import unittest
import tempfile

from migen import *

from litex.soc.interconnect import csr_bus

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
            # Configure Trigger (on a counter value comfortably after arming completes; the
            # term memory no longer accepts being armed with pending terms silently flushed,
            # so the trigger must actually be enabled and reachable).
            yield from dut.analyzer.trigger.mem_value.write(0x0400)
            yield from dut.analyzer.trigger.mem_mask.write(0xffff)
            yield from dut.analyzer.trigger.mem_write.write(1)

            # Configure Subsampler
            yield from dut.analyzer.subsampler.value.write(2)

            # Configure Storage
            yield from dut.analyzer.storage.length.write(256)
            yield from dut.analyzer.storage.offset.write(8)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
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
        run_simulation(dut, generators, clocks, vcd_name=None)
        # Trigger value 0x400 (comfortably after the storage FLUSH window at depth=512) with
        # offset=8 and subsampling=3: the capture holds the 8 pre-trigger samples followed by
        # the trigger sample (first sample kept from the match on, at index 8) and the
        # post-trigger samples. The subsampling phase follows the end of the FLUSH (the trigger
        # and the subsampler only see samples from then on), not the counter.
        self.assertEqual(dut.data, [dut.data[0] + 3*i for i in range(len(dut.data))])
        self.assertTrue(0x400 <= dut.data[8] < 0x400 + 3)

    def test_analyzer_trigger_position(self):
        # The trigger sample (the sample matching the last term) is at index Offset.
        def run(offset, length=32, value=200):
            def generator(dut):
                yield from dut.analyzer.trigger.mem_value.write(value)
                yield from dut.analyzer.trigger.mem_mask.write(0xff)
                yield from dut.analyzer.trigger.mem_write.write(1)
                yield from dut.analyzer.subsampler.value.write(0)
                yield from dut.analyzer.storage.length.write(length)
                yield from dut.analyzer.storage.offset.write(offset)
                yield from dut.analyzer.storage.enable.write(1)
                yield from dut.analyzer.trigger.enable.write(1)
                for i in range(16):
                    yield
                while not (yield from dut.analyzer.storage.done.read()):
                    yield
                dut.data = (yield from read_capture_words(dut.analyzer, length))

            class DUT(Module):
                def __init__(self):
                    counter = Signal(8)
                    self.sync += counter.eq(counter + 1)
                    self.submodules.analyzer = LiteScopeAnalyzer(counter, 64, csr_csv=None)

            dut = DUT()
            run_simulation(dut, {"sys" : [generator(dut)]}, {"sys": 10, "scope": 10})
            return dut.data

        for offset, length in [(0, 32), (1, 32), (2, 32), (3, 32), (8, 32), (31, 32), (63, 64)]:
            data = run(offset, length)
            self.assertEqual(data, [(200 - offset + i) & 0xff for i in range(length)],
                msg=f"offset={offset}")

    def test_analyzer_trigger_match_during_flush(self):
        # The trigger is armed right after the storage, before its FLUSH ends: a match during
        # FLUSH must not fire the trigger. The capture is taken around the next match instead
        # (the 8-bit counter wraps), with the matching sample at index Offset.
        def run(value, offset=8, length=32):
            def generator(dut):
                yield from dut.analyzer.trigger.mem_value.write(value)
                yield from dut.analyzer.trigger.mem_mask.write(0xff)
                yield from dut.analyzer.trigger.mem_write.write(1)
                yield from dut.analyzer.subsampler.value.write(0)
                yield from dut.analyzer.storage.length.write(length)
                yield from dut.analyzer.storage.offset.write(offset)
                yield from dut.analyzer.storage.enable.write(1)
                yield from dut.analyzer.trigger.enable.write(1)
                for i in range(16):
                    yield
                while not (yield from dut.analyzer.storage.done.read()):
                    yield
                dut.data = (yield from read_capture_words(dut.analyzer, length))

            class DUT(Module):
                def __init__(self):
                    counter = Signal(8)
                    self.sync += counter.eq(counter + 1)
                    self.submodules.analyzer = LiteScopeAnalyzer(counter, 64, csr_csv=None)

            dut = DUT()
            run_simulation(dut, {"sys" : [generator(dut)]}, {"sys": 10, "scope": 10})
            return dut.data

        # FLUSH lasts 64 cycles from the arming (counter about 8 to 72).
        for value in [30, 60]:
            data = run(value)
            self.assertEqual(data, [(value - 8 + i) & 0xff for i in range(32)], msg=f"value={value}")

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
        # With offset=0 the trigger match is the first captured sample: 0xb0 at index 0
        # (the second group's signal, proving the mux selection), incrementing by 3.
        self.assertEqual(dut.data[0], 0xb0)
        self.assertEqual(dut.data, [(0xb0 + 3*i) & 0xff for i in range(len(dut.data))])

    def test_analyzer_group_mux_default(self):
        # A mux value that is not a group (raw register write) selects group 0: the capture
        # completes instead of stalling.
        def generator(dut):
            yield from dut.analyzer.mux.value.write(dut.mux_value)
            yield from dut.analyzer.trigger.mem_value.write(0)
            yield from dut.analyzer.trigger.mem_mask.write(0)
            yield from dut.analyzer.trigger.mem_write.write(1)
            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(16)
            yield from dut.analyzer.storage.offset.write(0)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            for i in range(16):
                yield
            for i in range(1000):
                if (yield from dut.analyzer.storage.done.read()):
                    break
                yield
            else:
                return
            dut.data = (yield from read_capture_words(dut.analyzer, 16))

        class DUT(Module):
            def __init__(self, mux_value):
                self.mux_value = mux_value
                self.data      = None
                counter = Signal(8)
                other   = Signal(8, reset=0x80)
                self.sync += [
                    counter.eq(counter + 1),
                    other.eq(other - 1),
                ]
                self.submodules.analyzer = LiteScopeAnalyzer({
                    0: counter,
                    1: other,
                }, 32, csr_csv=None)

        for mux_value in [2, 3]:
            dut = DUT(mux_value)
            run_simulation(dut, {"sys" : [generator(dut)]}, {"sys": 10, "scope": 10})
            self.assertIsNotNone(dut.data, msg=f"mux_value={mux_value}")
            # Group 0 (incrementing counter).
            self.assertEqual(dut.data, [(dut.data[0] + i) & 0xff for i in range(16)])

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

    def test_analyzer_rle_preserves_run_lengths(self):
        # The probe stream never stalls: the encoder must not drop samples when a run ends
        # (run word then raw value) nor when a full run word is emitted.
        def run(shift, rle_length, length=32):
            def generator(dut):
                yield from dut.analyzer.trigger.mem_value.write(0)
                yield from dut.analyzer.trigger.mem_mask.write(0)
                yield from dut.analyzer.trigger.mem_write.write(1)
                yield from dut.analyzer.rle.enable.write(1)
                yield from dut.analyzer.subsampler.value.write(0)
                yield from dut.analyzer.storage.length.write(length)
                yield from dut.analyzer.storage.offset.write(0)
                yield from dut.analyzer.storage.enable.write(1)
                yield from dut.analyzer.trigger.enable.write(1)
                while (yield from dut.analyzer.storage.done.read()):
                    yield
                while not (yield from dut.analyzer.storage.done.read()):
                    yield
                dut.data = (yield from read_capture_words(dut.analyzer, length))

            class DUT(Module):
                def __init__(self):
                    counter = Signal(12)
                    value   = Signal(4)
                    self.sync += counter.eq(counter + 1)
                    self.comb += value.eq(counter[shift:shift+4])
                    self.submodules.analyzer = LiteScopeAnalyzer(value, 64,
                        with_rle   = True,
                        rle_length = rle_length,
                        csr_csv    = None)

            dut = DUT()
            run_simulation(dut, {"sys" : [generator(dut)]}, {"sys": 10, "scope": 10})
            encoded = DumpData(dut.analyzer.storage_width)
            encoded.extend(dut.data)
            decoded = list(encoded.decode_rle(data_width=dut.analyzer.data_width))
            runs = []
            for sample in decoded:
                if runs and runs[-1][0] == sample:
                    runs[-1][1] += 1
                else:
                    runs.append([sample, 1])
            return runs

        # Runs of 4 (rle_length 8) and runs of 8 split in full run words (rle_length 4): the
        # first/last runs are cut by the capture window, the others keep their length.
        for shift, rle_length in [(2, 8), (3, 4)]:
            runs = run(shift, rle_length)
            self.assertGreater(len(runs), 3)
            self.assertEqual([n for v, n in runs[1:-1]], [2**shift]*(len(runs) - 2),
                msg=f"runs of {2**shift} with rle_length {rle_length}: {runs}")

    def test_analyzer_rle_subsampling_and_single_samples(self):
        # RLE with subsampling must complete (the RLE must not wait on a subsampler that only
        # advances when the RLE accepts) and a single-sample value right after a run must be kept.
        def run(pattern, subsampling, rle_length=8, length=64, timeout=20000):
            def generator(dut):
                dut.done = False
                yield from dut.analyzer.trigger.mem_value.write(0)
                yield from dut.analyzer.trigger.mem_mask.write(0)
                yield from dut.analyzer.trigger.mem_write.write(1)
                yield from dut.analyzer.rle.enable.write(1)
                yield from dut.analyzer.subsampler.value.write(subsampling - 1)
                yield from dut.analyzer.storage.length.write(length)
                yield from dut.analyzer.storage.offset.write(0)
                yield from dut.analyzer.storage.enable.write(1)
                yield from dut.analyzer.trigger.enable.write(1)
                for i in range(16):
                    yield
                for i in range(timeout):
                    if (yield from dut.analyzer.storage.done.read()):
                        dut.done = True
                        break
                    yield
                if dut.done:
                    dut.data = (yield from read_capture_words(dut.analyzer, length))

            class DUT(Module):
                def __init__(self):
                    index = Signal(max=len(pattern))
                    probe = Signal(4)
                    self.sync += If(index == len(pattern) - 1,
                        index.eq(0)
                    ).Else(
                        index.eq(index + 1)
                    )
                    self.comb += Case(index, {i: probe.eq(v) for i, v in enumerate(pattern)})
                    self.submodules.analyzer = LiteScopeAnalyzer(probe, length,
                        with_rle   = True,
                        rle_length = rle_length,
                        csr_csv    = None)

            dut = DUT()
            run_simulation(dut, {"sys" : [generator(dut)]}, {"sys": 10, "scope": 10})
            self.assertTrue(dut.done, msg=f"capture not done (subsampling {subsampling})")
            encoded = DumpData(dut.analyzer.storage_width)
            encoded.extend(dut.data)
            decoded = list(encoded.decode_rle(data_width=dut.analyzer.data_width))
            runs = []
            for sample in decoded:
                if runs and runs[-1][0] == sample:
                    runs[-1][1] += 1
                else:
                    runs.append([sample, 1])
            return runs

        # Runs of 12 cycles subsampled by 3: runs of 4 samples (first/last cut by the window).
        runs = run([0]*12 + [1]*12 + [2]*12 + [3]*12, subsampling=3)
        self.assertGreater(len(runs), 3)
        self.assertEqual([n for v, n in runs[1:-1]], [4]*(len(runs) - 2), msg=f"{runs}")
        self.assertTrue(all(b == (a + 1) % 4 for (a, _), (b, _) in zip(runs, runs[1:])), msg=f"{runs}")

        # A run then single-sample values: every value is kept, in order.
        runs = run([0, 0, 0, 0, 1, 2, 3], subsampling=1)
        self.assertGreater(len(runs), 8)
        self.assertTrue(all(b == (a + 1) % 4 for (a, _), (b, _) in zip(runs, runs[1:])), msg=f"{runs}")
        self.assertEqual([n for v, n in runs[1:-1]], [{0: 4}.get(v, 1) for v, n in runs[1:-1]],
            msg=f"{runs}")

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

    def test_analyzer_done_drops_on_arming(self):
        # Done reads 0 from the arming on (also with a slower scope clock and Enable cleared
        # for a single write, as run() does), so that a wait for Done does not return before
        # the capture has started.
        def generator(dut):
            dut.done_reads = []
            dut.captures   = []
            for capture in range(2):
                yield from dut.analyzer.trigger.mem_value.write(0)
                yield from dut.analyzer.trigger.mem_mask.write(0)
                yield from dut.analyzer.trigger.mem_write.write(1)
                yield from dut.analyzer.subsampler.value.write(0)
                yield from dut.analyzer.storage.length.write(8)
                yield from dut.analyzer.storage.offset.write(0)
                yield from dut.analyzer.storage.enable.write(0)
                yield from dut.analyzer.storage.enable.write(1)
                yield from dut.analyzer.trigger.enable.write(1)
                reads = []
                for i in range(1000):
                    done = (yield from dut.analyzer.storage.done.read())
                    reads.append(done)
                    if done:
                        break
                dut.done_reads.append(reads)
                data = []
                for i in range(8):
                    for j in range(16): # Let the read path (CDC) refill with a slow scope clock.
                        yield
                    data.append((yield from dut.analyzer.storage.mem_data.read()))
                dut.captures.append(data)
                yield from dut.analyzer.trigger.enable.write(0)
                for i in range(64):
                    yield

        class DUT(Module):
            def __init__(self):
                counter = Signal(8)
                self.sync.scope += counter.eq(counter + 1)
                self.submodules.analyzer = LiteScopeAnalyzer(counter, 16, csr_csv=None)

        for scope_period in [10, 40]:
            dut = DUT()
            run_simulation(dut, {"sys": [generator(dut)]}, {"sys": 10, "scope": scope_period})
            for reads, data in zip(dut.done_reads, dut.captures):
                msg = f"scope_period={scope_period}"
                self.assertEqual(reads[0], 0, msg=msg)
                self.assertEqual(reads[-1], 1, msg=msg)
                self.assertEqual(data, [(data[0] + i) & 0xff for i in range(8)], msg=msg)

    def test_format_groups_splits_records_and_deduplicates(self):
        signal = Signal(1)
        record = Record([("field0", 3), ("field1", 5)])

        analyzer = LiteScopeAnalyzer([signal, signal, record], 16, csr_csv=None)

        self.assertEqual(analyzer.groups[0], [signal, record.field0, record.field1])
        self.assertEqual(analyzer.data_width, 9)

    def test_format_groups_accepts_expressions(self):
        # Slices, Cat and other Migen expressions are not hashable: they are driven into named
        # Signals so duplicate removal and the CSV export still work.
        counter = Signal(32)
        flag    = Signal()
        analyzer = LiteScopeAnalyzer([counter[:16], counter[31], Cat(flag, counter[16:20]), flag, flag],
            depth=16, csr_csv=None)

        signals = analyzer.groups[0]
        self.assertTrue(all(isinstance(s, Signal) for s in signals))
        self.assertEqual([len(s) for s in signals], [16, 1, 5, 1])
        self.assertIs(signals[3], flag)
        self.assertEqual(analyzer.data_width, 23)

        from migen.fhdl.verilog import convert
        ns = convert(analyzer, ios=set()).ns
        with tempfile.NamedTemporaryFile() as f:
            analyzer.export_csv(ns, f.name)
            with open(f.name) as csv_file:
                lines = [l for l in csv_file.read().splitlines() if l.startswith("signal,")]
        self.assertEqual([l.split(",")[3] for l in lines], ["16", "1", "5", "1"])
        self.assertTrue(lines[0].split(",")[2].endswith("counter_15_0"))
        self.assertTrue(lines[1].split(",")[2].endswith("counter_31"))

    def test_analyzer_captures_slice(self):
        def generator(dut):
            yield from dut.analyzer.trigger.mem_value.write(0x40)
            yield from dut.analyzer.trigger.mem_mask.write(0xff)
            yield from dut.analyzer.trigger.mem_write.write(1)
            yield from dut.analyzer.subsampler.value.write(0)
            yield from dut.analyzer.storage.length.write(16)
            yield from dut.analyzer.storage.offset.write(4)
            yield from dut.analyzer.storage.enable.write(1)
            yield from dut.analyzer.trigger.enable.write(1)
            yield
            seen_busy = False
            for i in range(1024):
                done = (yield from dut.analyzer.storage.done.read())
                if not done:
                    seen_busy = True
                elif seen_busy:
                    break
                yield
            else:
                raise TimeoutError("Capture did not complete")
            dut.data = (yield from read_capture_words(dut.analyzer, 16))

        class DUT(Module):
            def __init__(self):
                counter = Signal(32, reset=0x1200)
                self.sync += counter.eq(counter + 1)
                self.submodules.analyzer = LiteScopeAnalyzer(counter[:8], 32, csr_csv=None)

        dut = DUT()
        run_simulation(dut, {"sys": [generator(dut)]}, {"sys": 10, "scope": 10})
        self.assertEqual(dut.analyzer.data_width, 8)
        # Contiguous low byte of the counter around the trigger value.
        self.assertEqual(dut.data, [(dut.data[0] + i) & 0xff for i in range(16)])
        self.assertIn(0x40, dut.data[:8])

    def test_export_csv(self):
        signal_a = Signal(3)
        signal_b = Signal(5)
        analyzer = LiteScopeAnalyzer({
            0: signal_a,
            1: signal_b,
        }, depth=32, samplerate=125e6, subsampler_width=20, csr_csv=None)

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
            "config,None,subsampler_width,20",
            "config,None,with_rle,0",
            "config,None,rle_length,256",
            "signal,0,signal_a,3",
            "signal,1,signal_b,5",
        ])

    def test_export_csv_with_fsm_enum(self):
        fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE", NextState("RUN"))
        fsm.act("RUN",  NextState("DONE"))
        fsm.act("DONE", NextState("IDLE"))

        analyzer = LiteScopeAnalyzer(fsm, depth=32, csr_csv=None)
        state    = analyzer.groups[0][0]

        class VNS:
            def get_name(self, signal):
                return {
                    state: "fsm_state",
                }[signal]

        with tempfile.NamedTemporaryFile() as f:
            analyzer.export_csv(VNS(), f.name)
            with open(f.name) as csv_file:
                lines = csv_file.read().splitlines()

        self.assertIn("signal,0,fsm_state,2", lines)
        self.assertIn("enum,0,fsm_state,0,IDLE", lines)
        self.assertIn("enum,0,fsm_state,1,RUN",  lines)
        self.assertIn("enum,0,fsm_state,2,DONE", lines)


# Wide trigger through the real multi-word CSR bus path ---------------------------------------------
#
# At data_width > 32 the trigger Mask/Value CSRs are compound (multiple bus words). The tests
# above poke CSRStorage.write() which sets the whole storage atomically, so the word-by-word bus
# path (what csr_builder/RemoteClient perform on hardware) was never exercised, and neither was
# a comparator wider than 32 bits. These tests drive the analyzer exclusively through a
# csr_bus.CSRBank, mirroring the host access pattern (MSB word first, ascending addresses,
# separate arm strobe).

# The trigger sample's position within the capture (offset=8, subsampling=1) is locked below:
# it must stay stable across trigger-pipeline changes (only absolute capture time may shift).


class _WideDUT(Module):
    def __init__(self, data_width=128, depth=64):
        self.counter = counter = Signal(32)
        self.sync += counter.eq(counter + 1)
        probe = Signal(data_width)
        self.comb += probe.eq(Cat(counter, ~counter, (counter + 0x12345678)[:32], (counter ^ 0x55AA55AA)[:32]))
        self.submodules.analyzer = LiteScopeAnalyzer(probe, depth, csr_csv=None)
        self.bus = csr_bus.Interface(data_width=32, address_width=14)
        self.submodules.bank = csr_bus.CSRBank(self.analyzer.get_csrs(), address=0, bus=self.bus)


def _wide_pattern(c):
    mask32 = 0xffffffff
    return (( c            & mask32)      |
            ((~c           & mask32) << 32) |
            (((c + 0x12345678) & mask32) << 64) |
            (((c ^ 0x55AA55AA) & mask32) << 96))


def _csr_addrs(dut, name):
    # Bus word addresses of a (possibly compound) CSR; ascending = MSB word first with the
    # default "big" ordering, matching litex's csr_builder host-side decomposition.
    return [i for i, c in enumerate(dut.bank.simple_csrs)
            if re.fullmatch(re.escape(name) + r"\d*", c.name)]


def _bus_csr_write(dut, name, value):
    addrs = _csr_addrs(dut, name)
    n     = len(addrs)
    for j, adr in enumerate(addrs):
        yield from dut.bus.write(adr, (value >> (32*(n - 1 - j))) & 0xffffffff)


def _bus_word_read(dut, adr):
    # csr_bus.Interface.read samples dat_r one cycle too early for the bank's registered
    # read path; add the settle cycle here.
    yield dut.bus.adr.eq(adr)
    yield dut.bus.re.eq(1)
    yield
    yield dut.bus.re.eq(0)
    yield
    return (yield dut.bus.dat_r)


def _bus_csr_read(dut, name):
    addrs = _csr_addrs(dut, name)
    value = 0
    for adr in addrs:
        value = (value << 32) | (yield from _bus_word_read(dut, adr))
    return value


def _bus_read_samples(dut, count, subwords):
    samples = []
    for _ in range(count):
        value = 0
        for j in range(subwords):
            sub = (yield from _bus_csr_read(dut, "storage_mem_data"))
            value |= sub << (32*j)
        samples.append(value)
    return samples


class TestAnalyzerWideTrigger(unittest.TestCase):
    # Trigger sample position within the capture for offset=8: the matching sample lands at
    # index 8 (Offset pre-trigger samples before it).
    EXPECTED_TRIGGER_INDEX = 8

    def _capture(self, dut, trigger_value, offset=8, length=32, timeout=4096):
        full_mask = 2**128 - 1
        yield from _bus_csr_write(dut, "subsampler_value", 0)
        yield from _bus_csr_write(dut, "storage_offset", offset)
        yield from _bus_csr_write(dut, "storage_length", length)
        yield from _bus_csr_write(dut, "storage_enable", 0)
        yield from _bus_csr_write(dut, "storage_enable", 1)
        yield from _bus_csr_write(dut, "trigger_enable", 0)
        yield from _bus_csr_write(dut, "trigger_mem_mask",  full_mask)
        yield from _bus_csr_write(dut, "trigger_mem_value", trigger_value)
        yield from _bus_csr_write(dut, "trigger_mem_write", 1)
        yield from _bus_csr_write(dut, "trigger_enable", 1)
        # done stays asserted (IDLE) until the enable edge crosses into the scope domain:
        # wait for the capture to start before waiting for it to complete.
        for _ in range(timeout):
            if not (yield from _bus_csr_read(dut, "storage_done")):
                break
            yield
        else:
            self.fail("capture did not start")
        for _ in range(timeout):
            if (yield from _bus_csr_read(dut, "storage_done")):
                break
            yield
        else:
            self.fail("capture did not complete")
        # After completion the storage FIFO starts migrating samples into the CDC/read
        # pipeline, so mem_level only reflects what still sits in the FIFO; the read path
        # delivers the full capture.
        level = yield from _bus_csr_read(dut, "storage_mem_level")
        self.assertGreater(level, 0)
        return (yield from _bus_read_samples(dut, length, 4))

    def test_wide_trigger_via_csr_bus(self):
        dut = _WideDUT()
        results = {}

        def generator():
            yield
            targets = []
            for run in range(2):
                # Re-arm on each iteration: terms are consumed per capture and must be
                # re-loaded (what the driver's run() does).
                target = (yield dut.counter) + 500
                targets.append(target)
                results[run] = (yield from self._capture(dut, _wide_pattern(target)))
            results["targets"] = targets

        run_simulation(dut, {"sys": [generator()]}, {"sys": 10, "scope": 10}, vcd_name=None)

        for run in range(2):
            samples = results[run]
            base    = samples[0] & 0xffffffff
            self.assertEqual(samples, [_wide_pattern(base + i) for i in range(len(samples))],
                msg=f"capture {run} is not a consecutive wide pattern")
            # The trigger sample sits at the locked position within the capture.
            self.assertEqual(samples[self.EXPECTED_TRIGGER_INDEX],
                             _wide_pattern(results["targets"][run]))


if __name__ == "__main__":
    unittest.main()
