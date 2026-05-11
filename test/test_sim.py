#
# This file is part of LiteScope.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import shutil
import socket
import sys
import tempfile
import time
import unittest

from migen import *

root_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    import pexpect
except ImportError:
    pexpect = None

from litex.build.sim.config import SimConfig
from litex.soc.integration.builder import Builder
from litex.tools.litex_sim import SimSoC
from litex.tools.remote.csr_builder import CSRBuilder

from litescope import LiteScopeAnalyzer, LiteScopeAnalyzerDriver


PROMPT = b"litex\x1b[0m> "


class LiteScopeSimSoC(SimSoC):
    def __init__(self, analyzer_csv, analyzer_rle_csv, **kwargs):
        SimSoC.__init__(self,
            integrated_rom_size      = 128*1024,
            integrated_main_ram_size = 64*1024,
            **kwargs)

        counter = Signal(32)
        self.sync += counter.eq(counter + 1)
        self.submodules.analyzer = LiteScopeAnalyzer(counter,
            depth        = 64,
            clock_domain = "sys",
            samplerate   = self.sys_clk_freq,
            csr_csv      = analyzer_csv)
        rle_value = Signal(4, reset=5)
        self.submodules.analyzer_rle = LiteScopeAnalyzer(rle_value,
            depth        = 64,
            clock_domain = "sys",
            samplerate   = self.sys_clk_freq,
            with_rle     = True,
            rle_length   = 8,
            csr_csv      = analyzer_rle_csv)
        if hasattr(self, "add_csr"):
            self.add_csr("analyzer")
            self.add_csr("analyzer_rle")
        else:
            self.csr.add("analyzer")
            self.csr.add("analyzer_rle")


def sim_main():
    import argparse

    parser = argparse.ArgumentParser(description="LiteScope litex_sim test target")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--csr-csv", required=True)
    parser.add_argument("--analyzer-csv", required=True)
    parser.add_argument("--analyzer-rle-csv", required=True)
    parser.add_argument("--uart-tcp-port", type=int, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()

    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    soc = LiteScopeSimSoC(
        analyzer_csv     = args.analyzer_csv,
        analyzer_rle_csv = args.analyzer_rle_csv,
        uart_name        = "sim")
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=args.csr_csv)

    def export_analyzer_csv(vns):
        soc.analyzer.export_csv(vns, args.analyzer_csv)
        soc.analyzer_rle.export_csv(vns, args.analyzer_rle_csv)

    builder.build(
        sim_config       = sim_config,
        interactive      = False,
        opt_level        = "O0",
        jobs             = args.jobs,
        pre_run_callback = export_analyzer_csv)


def sim_jobs():
    return max(1, min(4, os.cpu_count() or 1))


def get_free_tcp_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def connect_tcp(port, timeout=30, process=None):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        if process is not None and not process.isalive():
            raise RuntimeError(f"litex_sim exited before UART port {port} accepted connections")
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=1)
            sock.settimeout(0.1)
            return sock
        except OSError as e:
            last_error = e
            time.sleep(0.1)
    raise TimeoutError(f"could not connect to litex_sim UART on port {port}: {last_error}")


class UARTConsole:
    def __init__(self, sock):
        self.sock = sock

    def recv_until_prompt(self, timeout=60):
        deadline = time.time() + timeout
        data = b""
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if chunk:
                    data += chunk
                    if PROMPT in data:
                        return data
                else:
                    time.sleep(0.02)
            except socket.timeout:
                pass
        raise TimeoutError(f"did not receive LiteX prompt; last data: {data[-500:]!r}")

    def command(self, command, timeout=20):
        self.sock.sendall(command.encode() + b"\n")
        return self.recv_until_prompt(timeout=timeout)


class BIOSMemAccess:
    def __init__(self, console):
        self.console = console

    def read(self, addr, length=None, burst="incr"):
        length = 1 if length is None else length
        addrs = [addr]*length if burst == "fixed" else [addr + 4*i for i in range(length)]
        datas = [self._read32(addr) for addr in addrs]
        return datas[0] if length == 1 else datas

    def write(self, addr, datas):
        if isinstance(datas, int):
            datas = [datas]
        for i, data in enumerate(datas):
            self.console.command(f"mem_write 0x{addr + 4*i:08x} 0x{data:08x}")

    def _read32(self, addr):
        response = self.console.command(f"mem_read 0x{addr:08x} 4")
        match = re.search(
            rb"Memory dump:.*?0x[0-9a-fA-F]+\s+((?:[0-9a-fA-F]{2}\s+){4})",
            response,
            re.S)
        if match is None:
            raise ValueError(f"could not parse mem_read response: {response[-500:]!r}")
        data = bytes(int(v, 16) for v in match.group(1).split()[:4])
        return int.from_bytes(data, "little")


def wait_analyzer_done(analyzer, timeout=30, message="LiteScope capture did not complete"):
    deadline = time.time() + timeout
    while not analyzer.done():
        if time.time() > deadline:
            raise TimeoutError(message)


class TestLiteScopeSim(unittest.TestCase):
    @unittest.skipUnless(shutil.which("verilator"), "verilator is required")
    @unittest.skipUnless(pexpect is not None, "pexpect is required")
    def test_litescope_analyzer_over_virtual_uart(self):
        port = get_free_tcp_port()
        sock = None

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir   = os.path.join(tmpdir, "build")
            csr_csv      = os.path.join(output_dir, "csr.csv")
            analyzer_csv = os.path.join(tmpdir, "analyzer.csv")
            analyzer_rle_csv = os.path.join(tmpdir, "analyzer_rle.csv")
            cmd_args = [
                os.path.abspath(__file__),
                "--run-sim",
                "--output-dir", output_dir,
                "--csr-csv", csr_csv,
                "--analyzer-csv", analyzer_csv,
                "--analyzer-rle-csv", analyzer_rle_csv,
                "--uart-tcp-port", str(port),
                "--jobs", str(sim_jobs()),
            ]

            with tempfile.TemporaryFile(mode="w+", prefix="litescope_sim_") as log_file:
                p = pexpect.spawn(sys.executable,
                    cmd_args,
                    cwd      = tmpdir,
                    timeout  = None,
                    encoding = sys.getdefaultencoding(),
                    logfile  = log_file)
                try:
                    sock = connect_tcp(port, timeout=1200, process=p)

                    console = UARTConsole(sock)
                    console.recv_until_prompt(timeout=120)

                    bus = CSRBuilder(BIOSMemAccess(console), csr_csv)
                    self.assertEqual(bus.regs.ctrl_scratch.read(), 0x12345678)
                    bus.regs.ctrl_scratch.write(0x5aa55aa5)
                    self.assertEqual(bus.regs.ctrl_scratch.read(), 0x5aa55aa5)

                    analyzer = LiteScopeAnalyzerDriver(bus.regs, "analyzer", config_csv=analyzer_csv)
                    self.assertEqual(analyzer.data_width, 32)
                    self.assertEqual(analyzer.depth, 64)
                    self.assertEqual(analyzer.layouts[0], [("counter", 32)])

                    analyzer.configure_trigger()
                    analyzer.configure_subsampler(1)
                    analyzer.run(offset=0, length=16)
                    wait_analyzer_done(analyzer)

                    data = analyzer.upload()
                    samples = list(data)
                    self.assertGreaterEqual(len(samples), 8)
                    self.assertLessEqual(len(samples), 16)
                    self.assertEqual(data.width, 32)
                    self.assertEqual(samples, list(range(samples[0], samples[0] + len(samples))))

                    analyzer_rle = LiteScopeAnalyzerDriver(bus.regs, "analyzer_rle", config_csv=analyzer_rle_csv)
                    self.assertEqual(analyzer_rle.data_width, 4)
                    self.assertEqual(analyzer_rle.storage_width, 5)
                    self.assertEqual(analyzer_rle.depth, 64)
                    self.assertEqual(analyzer_rle.with_rle, 1)
                    self.assertEqual(analyzer_rle.layouts[0], [("rle_value", 4)])

                    analyzer_rle.configure_trigger()
                    analyzer_rle.configure_subsampler(1)
                    analyzer_rle.configure_rle(True)
                    analyzer_rle.run(offset=0, length=32)
                    wait_analyzer_done(analyzer_rle, message="LiteScope RLE capture did not complete")

                    encoded_words = analyzer_rle.storage_mem_level.read()
                    rle_data = analyzer_rle.upload(max_samples=10)
                    rle_samples = list(rle_data)
                    self.assertGreater(encoded_words, 0)
                    self.assertEqual(len(rle_samples), 10)
                    self.assertEqual(rle_data.width, 4)
                    self.assertTrue(all(sample == 5 for sample in rle_samples))
                except Exception:
                    log_file.seek(0)
                    print(log_file.read())
                    raise
                finally:
                    if sock is not None:
                        sock.close()
                    p.terminate(force=True)


if __name__ == "__main__":
    if "--run-sim" in sys.argv:
        sys.argv.remove("--run-sim")
        sim_main()
    else:
        unittest.main()
