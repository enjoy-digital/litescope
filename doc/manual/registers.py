#
# This file is part of LiteScope project.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause
#
# Register appendix of the manual: which designs tools/csr_doc.py elaborates and which register banks
# it documents (the engine is generic, part of the manual kit).

import json
import os
import sys
import tempfile

# Configurations: name -> parameters of the reference design below (shown in the appendix table).
# One design holds an IO probe and an analyzer with every register of the core: two groups (mux),
# a probe wider than 32 bits (multi-word mask and value, two sub-words per stored word) and the
# run-length encoder (rle_enable).
CONFIGS = {
    "arty_reference" : ["groups: 41 and 4 bits", "depth=1024", "with_rle=True", "LiteScopeIO(8)"],
}

# Banks documented in the appendix (prefix match on the bank name), in order, with their title and
# the Python class that defines them. The longest matching prefix owns a bank.
BANKS = [
    ("analyzer", "Analyzer", "LiteScopeAnalyzer", "litescope/core.py"),
    ("io",       "IO probe", "LiteScopeIO",       "litescope/core.py"),
]

# Descriptions of the LiteScope registers. The gateware declares its registers without descriptions
# (CSRStorage/CSRStatus/CSR without `description`), so they are given here and attached to the
# elaborated registers before the dump; a description declared in the gateware takes precedence.
# Keys: (bank, register). The IO probe registers carry the descriptions of the LiteX GPIOInOut.
DESCRIPTIONS = {
    ("analyzer", "mux_value")         : "Group to capture, `bits_for(ngroups)` bits; the trigger compares the samples of this group.",
    ("analyzer", "trigger_enable")    : "1: arm the trigger, a term is consumed on each match. The falling edge flushes the terms left in the term memory.",
    ("analyzer", "trigger_done")      : "1: term memory empty, every term matched or flushed (also 1 with no term loaded).",
    ("analyzer", "trigger_mem_write") : "Write: push the term (`trigger_mem_mask`, `trigger_mem_value`) into the term memory.",
    ("analyzer", "trigger_mem_mask")  : "Mask of the next term, `data_width` bits: 1 for each bit the term compares.",
    ("analyzer", "trigger_mem_value") : "Value of the next term, `data_width` bits, compared on the bits set in the mask.",
    ("analyzer", "trigger_mem_full")  : "1: term memory full (`trigger_depth + 1` terms, `trigger_depth` a power of two of at least 4); a write is lost.",
    ("analyzer", "subsampler_value")  : "Subsampling factor minus one: one sample is kept every `value + 1` cycles, `subsampler_width` bits.",
    ("analyzer", "rle_enable")        : "1: run-length encode the samples from the trigger on. Only with `with_rle=True`.",
    ("analyzer", "storage_enable")    : "Rising edge: flush the storage and start a capture. Keep at 1 while reading `storage_mem_data`.",
    ("analyzer", "storage_done")      : "1: storage idle, capture complete or never started.",
    ("analyzer", "storage_length")    : "Words of the capture, pre-trigger window included, `bits_for(depth)` bits; at most `depth`.",
    ("analyzer", "storage_offset")    : "Pre-trigger window in words, `bits_for(depth)` bits; below `depth`.",
    ("analyzer", "storage_mem_level") : "Words still in the storage memory, `bits_for(depth)` bits; read it once `storage_done` is 1. The last words of a capture, up to four, have then moved to the read path and are not counted.",
    ("analyzer", "storage_mem_data")  : "Read port: next 32-bit sub-word of the capture, least significant first; each read pops it.",
}

# Notes printed after the title of a bank family: what the register descriptions do not say.
NOTES = {
    "analyzer": [
        "The analyzer of this design has two groups: group 0 is 41 bits wide (an 8-bit counter,",
        "a flag and a 32-bit word), group 1 is 4 bits wide. `data_width` is therefore 41, so the",
        "mask and the value of a term take two 32-bit words each. With `with_rle=True`, a stored",
        "word has 42 bits, the 41 bits of a sample and the marker bit, read as two sub-words.",
        "`rle_enable` is absent from an analyzer built without `with_rle`; the other registers are",
        "always present.",
        "",
        "The widths follow the parameters of the analyzer: `data_width` for the term registers,",
        "`bits_for(depth)` for the storage counters and at most 32 bits for `storage_mem_data`.",
        "The bank takes the name of the analyzer attribute of the SoC, and the driver must be",
        "given the same name ([Analyzer architecture](#analyzer-architecture)).",
    ],
    "io": [
        "`LiteScopeIO` wraps a LiteX `GPIOInOut`: its registers have the width given to the IO",
        "probe, 8 bits in this design ([IO probe](#io-probe)).",
    ],
}

# Opening paragraph of the appendix and the sentence that ends the access paragraph.
INTRO = ["This appendix lists the registers of LiteScope: the analyzer and the IO probe. It is",
         "generated from the register definitions of the gateware, elaborated on a reference design",
         "for the Arty A7 platform without running an FPGA toolchain. Offsets are in bytes from the",
         "base of the bank; the base addresses depend on the SoC and are in the `csr.csv` of a",
         "build. A LiteX SoC names the banks after the attributes that hold the cores, `analyzer`",
         "and `io` in this design."]
USAGE = ["The driver and `litescope_cli` use these names through the `csr.csv` of the build, so they",
         "never need the offsets."]
MAIN_BANK = "Registers of the top-level `main` bank of the SoC."


def _describe(soc):
    """Attach the descriptions of DESCRIPTIONS to the registers that have none in the gateware."""
    for bank, region in soc.csr.regions.items():
        if not isinstance(region.obj, list):
            continue
        for csr in region.obj:
            desc = DESCRIPTIONS.get((bank, csr.name))
            if desc and not (getattr(csr, "description", None) or "").strip():
                csr.description = desc


def _reference_soc(output_dir):
    """Reference design: SoCMini on the Arty A7 platform with an IO probe and an analyzer."""
    from migen import Signal, Cat
    from migen.genlib.io import CRG
    from litex.soc.integration.soc_core import SoCMini
    from litex_boards.platforms import digilent_arty
    from litescope import LiteScopeAnalyzer, LiteScopeIO

    class ReferenceSoC(SoCMini):
        def __init__(self):
            platform = digilent_arty.Platform()
            self.crg = CRG(platform.request("clk100"))
            SoCMini.__init__(self, platform, clk_freq=100e6, uart_name="uartbone")
            count = Signal(8)
            flag  = Signal()
            word  = Signal(32)
            self.sync += [
                count.eq(count + 1),
                word.eq(Cat(count, count, count, count)),
            ]
            self.comb += flag.eq(count == 0)
            self.io       = LiteScopeIO(8)
            self.analyzer = LiteScopeAnalyzer({0: [count, flag, word], 1: [count[4:8]]},
                depth      = 1024,
                samplerate = 100e6,
                with_rle   = True,
                csr_csv    = os.path.join(output_dir, "analyzer.csv"))

    return ReferenceSoC()


def elaborate(name, repo_root):
    """Elaborate the reference design with a Builder that runs no toolchain; return
    (soc, csr_json, module, argv)."""
    # The LiteScope of this repository, not an installed one.
    sys.path.insert(0, repo_root)
    from litex.soc.integration.builder import Builder
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            soc     = _reference_soc(tmp)
            builder = Builder(soc, output_dir=tmp, csr_csv=os.path.join(tmp, "csr.csv"),
                csr_json=os.path.join(tmp, "csr.json"), compile_software=False,
                compile_gateware=False)
            builder.build(run=False)
            csr_json = json.load(open(os.path.join(tmp, "csr.json")))
        finally:
            os.chdir(old_cwd)
    # Memories mapped on the CSR bus have no register definitions: keep the register banks only.
    for bank, region in list(soc.csr.regions.items()):
        if not isinstance(region.obj, list):
            del soc.csr.regions[bank]
    _describe(soc)
    return soc, csr_json, "digilent_arty", CONFIGS[name]
