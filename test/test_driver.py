#
# This file is part of LiteScope.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest

from litescope import LiteScopeAnalyzerDriver


class FakeReg:
    def __init__(self, value=0, data=None, addr=0):
        self.value = value
        self.data  = [] if data is None else data
        self.addr  = addr
        self.writes       = []
        self.readfn_calls = []

    def write(self, value):
        self.value = value
        self.writes.append(value)

    def read(self):
        return self.value

    def readfn(self, addr, length, burst=None):
        self.readfn_calls.append((addr, length, burst))
        return self.data[:length]


class FakeRegs:
    def __init__(self, name, regs):
        self.d = {f"{name}_{k}": v for k, v in regs.items()}


def write_config(filename, data_width=8, depth=16, samplerate=100000000,
                 storage_width=None, with_rle=None, rle_length=None):
    with open(filename, "w") as f:
        f.write(f"config,None,data_width,{data_width}\n")
        if storage_width is not None:
            f.write(f"config,None,storage_width,{storage_width}\n")
        f.write(f"config,None,depth,{depth}\n")
        f.write(f"config,None,samplerate,{samplerate}\n")
        if with_rle is not None:
            f.write(f"config,None,with_rle,{int(with_rle)}\n")
        if rle_length is not None:
            f.write(f"config,None,rle_length,{rle_length}\n")
        f.write("signal,0,flag,1\n")
        f.write("signal,0,state,3\n")
        f.write(f"signal,1,wide,{data_width}\n")


def make_regs(name="analyzer", mem_level=0, mem_data=None, with_rle=False):
    regs = {
        "mux_value":             FakeReg(),
        "trigger_mem_full":      FakeReg(),
        "trigger_mem_mask":      FakeReg(),
        "trigger_mem_value":     FakeReg(),
        "trigger_mem_write":     FakeReg(),
        "trigger_enable":        FakeReg(),
        "subsampler_value":      FakeReg(),
        "storage_offset":        FakeReg(),
        "storage_length":        FakeReg(),
        "storage_enable":        FakeReg(),
        "storage_done":          FakeReg(1),
        "storage_mem_level":     FakeReg(mem_level),
        "storage_mem_data":      FakeReg(data=mem_data, addr=0x1234),
    }
    if with_rle:
        regs["rle_enable"] = FakeReg()
    return FakeRegs(name, regs)


class TestAnalyzerDriver(unittest.TestCase):
    def make_driver(self, data_width=8, depth=16, mem_level=0, mem_data=None,
                    storage_width=None, with_rle=False, rle_length=256):
        self.tmpdir = tempfile.TemporaryDirectory()
        config_csv  = os.path.join(self.tmpdir.name, "analyzer.csv")
        write_config(config_csv,
            data_width    = data_width,
            depth         = depth,
            storage_width = storage_width,
            with_rle      = with_rle if with_rle else None,
            rle_length    = rle_length if with_rle else None)
        regs = make_regs(mem_level=mem_level, mem_data=mem_data, with_rle=with_rle)
        driver = LiteScopeAnalyzerDriver(regs, "analyzer", config_csv=config_csv)
        return driver, regs

    def tearDown(self):
        if hasattr(self, "tmpdir"):
            self.tmpdir.cleanup()

    def clear_writes(self, regs):
        for reg in regs.d.values():
            reg.writes.clear()

    def test_layout_offsets_masks_and_initial_disable(self):
        driver, regs = self.make_driver()

        self.assertEqual(driver.data_width, 8)
        self.assertEqual(driver.storage_width, 8)
        self.assertEqual(driver.depth, 16)
        self.assertEqual(driver.samplerate, 100000000)
        self.assertEqual(driver.with_rle, 0)
        self.assertEqual(driver.layouts, {
            0: [("flag", 1), ("state", 3)],
            1: [("wide", 8)],
        })
        self.assertEqual(driver.flag_o,  0x1)
        self.assertEqual(driver.flag_m,  0x1)
        self.assertEqual(driver.state_o, 0x2)
        self.assertEqual(driver.state_m, 0xe)
        self.assertEqual(driver.wide_o,  0x1)
        self.assertEqual(driver.wide_m,  0xff)
        self.assertEqual(regs.d["analyzer_trigger_enable"].writes, [0])
        self.assertEqual(regs.d["analyzer_storage_enable"].writes, [0])

    def test_configure_rle(self):
        driver, regs = self.make_driver(data_width=4, storage_width=5, with_rle=True)
        self.clear_writes(regs)

        driver.configure_rle(True)
        driver.configure_rle(False)

        self.assertEqual(driver.storage_width, 5)
        self.assertEqual(driver.with_rle, 1)
        self.assertFalse(driver.rle_enabled)
        self.assertEqual(regs.d["analyzer_rle_enable"].writes, [1, 0])

    def test_configure_rle_rejects_unavailable_analyzer(self):
        driver, regs = self.make_driver()
        with self.assertRaises(ValueError):
            driver.configure_rle(True)
        driver.configure_rle(False)

    def test_conditional_trigger_parsing(self):
        driver, regs = self.make_driver()
        self.clear_writes(regs)

        driver.add_trigger(cond={"flag": "1", "state": "0b1x0"})

        self.assertEqual(regs.d["analyzer_trigger_mem_value"].writes, [0x9])
        self.assertEqual(regs.d["analyzer_trigger_mem_mask"].writes,  [0xb])
        self.assertEqual(regs.d["analyzer_trigger_mem_write"].writes, [1])

        self.clear_writes(regs)
        driver.add_trigger(cond={"wide": "0xax"})

        self.assertEqual(regs.d["analyzer_trigger_mem_value"].writes, [0xa0])
        self.assertEqual(regs.d["analyzer_trigger_mem_mask"].writes,  [0xf0])
        self.assertEqual(regs.d["analyzer_trigger_mem_write"].writes, [1])

    def test_edge_trigger_helpers(self):
        driver, regs = self.make_driver()
        self.clear_writes(regs)

        driver.add_rising_edge_trigger("flag")
        self.assertEqual(regs.d["analyzer_trigger_mem_value"].writes, [0, 1])
        self.assertEqual(regs.d["analyzer_trigger_mem_mask"].writes,  [1, 1])

        self.clear_writes(regs)
        driver.add_falling_edge_trigger("flag")
        self.assertEqual(regs.d["analyzer_trigger_mem_value"].writes, [1, 0])
        self.assertEqual(regs.d["analyzer_trigger_mem_mask"].writes,  [1, 1])

    def test_add_trigger_checks_memory_full(self):
        driver, regs = self.make_driver()
        regs.d["analyzer_trigger_mem_full"].value = 1

        with self.assertRaises(ValueError):
            driver.add_trigger(value=1, mask=1)

    def test_configure_subsampler_and_run(self):
        driver, regs = self.make_driver(depth=8)
        self.clear_writes(regs)

        driver.configure_subsampler(4)
        driver.run(offset=2, length=5)

        self.assertEqual(driver.subsampling, 4)
        self.assertEqual(driver.offset, 2)
        self.assertEqual(driver.length, 5)
        self.assertEqual(regs.d["analyzer_subsampler_value"].writes, [3])
        self.assertEqual(regs.d["analyzer_storage_offset"].writes,   [2])
        self.assertEqual(regs.d["analyzer_storage_length"].writes,   [5])
        self.assertEqual(regs.d["analyzer_storage_enable"].writes,   [1])
        self.assertEqual(regs.d["analyzer_trigger_enable"].writes,   [1])

        with self.assertRaises(AssertionError):
            driver.run(offset=8)
        with self.assertRaises(AssertionError):
            driver.run(length=9)

    def test_upload_packs_32bit_subwords(self):
        mem_data = [
            0x00000001, 0x00000002,
            0x12345678, 0x9abcdef0,
            0xffffffff, 0x00000000,
        ]
        driver, regs = self.make_driver(data_width=64, mem_level=3, mem_data=mem_data)

        data = driver.upload()

        self.assertEqual(data.width, 64)
        self.assertEqual(list(data), [
            0x0000000200000001,
            0x9abcdef012345678,
            0x00000000ffffffff,
        ])
        self.assertEqual(regs.d["analyzer_storage_mem_data"].readfn_calls, [
            (0x1234, 6, "fixed"),
        ])

    def test_upload_decodes_rle(self):
        mem_data = [
            0x00000003,
            0x00000082,
            0x0000000a,
            0x00000081,
        ]
        driver, regs = self.make_driver(
            data_width    = 4,
            storage_width = 8,
            with_rle      = True,
            mem_level     = 4,
            mem_data      = mem_data)

        driver.configure_rle(True)
        data = driver.upload()

        self.assertEqual(data.width, 4)
        self.assertEqual(list(data), [3, 3, 3, 10, 10])
        self.assertEqual(regs.d["analyzer_storage_mem_data"].readfn_calls, [
            (0x1234, 4, "fixed"),
        ])

    def test_upload_strips_rle_storage_padding_when_disabled(self):
        mem_data = [
            0x00000023,
            0x0000000a,
        ]
        driver, regs = self.make_driver(
            data_width    = 4,
            storage_width = 8,
            with_rle      = True,
            mem_level     = 2,
            mem_data      = mem_data)

        data = driver.upload()

        self.assertEqual(data.width, 4)
        self.assertEqual(list(data), [3, 10])

    def test_upload_decodes_wide_rle_storage_words(self):
        mem_data = [
            0x11111111, 0x00000000,
            0x00000002, 0x00000001,
        ]
        driver, regs = self.make_driver(
            data_width    = 32,
            storage_width = 33,
            with_rle      = True,
            mem_level     = 2,
            mem_data      = mem_data)

        driver.configure_rle(True)
        data = driver.upload()

        self.assertEqual(data.width, 32)
        self.assertEqual(list(data), [0x11111111, 0x11111111, 0x11111111])
        self.assertEqual(regs.d["analyzer_storage_mem_data"].readfn_calls, [
            (0x1234, 4, "fixed"),
        ])


if __name__ == "__main__":
    unittest.main()
