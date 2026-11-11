#
# This file is part of LiteScope.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import io
import sys
import tempfile
import unittest
from unittest import mock

from litescope.software import litescope_cli


class FakeBus:
    instances = []

    def __init__(self, host=None, port=None, csr_csv=None):
        self.host    = host
        self.port    = port
        self.csr_csv = csr_csv
        self.regs    = object()
        self.opened  = False
        self.closed  = False
        FakeBus.instances.append(self)

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True


class FakeAnalyzer:
    instances = []

    def __init__(self, regs, name, config_csv=None, debug=False):
        self.regs       = regs
        self.name       = name
        self.config_csv = config_csv
        self.debug      = debug
        self.calls      = []
        self.fires      = True
        FakeAnalyzer.instances.append(self)

    def configure_group(self, value):
        self.calls.append(("configure_group", value))

    def configure_subsampler(self, value):
        self.calls.append(("configure_subsampler", value))

    def configure_rle(self, value):
        self.calls.append(("configure_rle", value))

    def add_trigger(self, cond=None):
        self.calls.append(("add_trigger", cond))

    def add_rising_edge_trigger(self, name):
        self.calls.append(("add_rising_edge_trigger", name))

    def add_falling_edge_trigger(self, name):
        self.calls.append(("add_falling_edge_trigger", name))

    def run(self, offset=0, length=None):
        self.calls.append(("run", offset, length))

    def wait_done(self):
        self.calls.append(("wait_done",))

    def done(self):
        self.calls.append(("done",))
        return self.fires

    def upload(self):
        self.calls.append(("upload",))
        return [0]*16

    def save(self, filename):
        self.calls.append(("save", filename))


class TestCLI(unittest.TestCase):
    def write_csv(self, filename):
        with open(filename, "w") as f:
            f.write("config,None,data_width,8\n")
            f.write("signal,0,flag,1\n")
            f.write("signal,0,state,3\n")
            f.write("signal,1,other,4\n")

    def test_finder(self):
        finder = litescope_cli.Finder(["main_count", "main_count_en", "ibus_stb"], verbose=False)
        self.assertEqual(finder["main_count"], "main_count") # Exact.
        self.assertEqual(finder["stb"], "ibus_stb")          # Substring.
        with self.assertRaisesRegex(ValueError, "No signal matching"):
            finder["cpu_ibus"]
        # A single probe is not returned for a name that does not match it.
        with self.assertRaisesRegex(ValueError, "No signal matching"):
            litescope_cli.Finder(["ibus_stb"], verbose=False)["dbus"]

    def test_parse_args_accepts_rle(self):
        argv = [
            "litescope_cli",
            "--rle",
            "--subsampling", "4",
            "--offset", "0x10",
            "--length", "0x20",
        ]
        with mock.patch.object(sys, "argv", argv):
            args = litescope_cli.parse_args()

        self.assertTrue(args.rle)
        self.assertEqual(args.subsampling, 4)
        self.assertEqual(args.offset, "0x10")
        self.assertEqual(args.length, "0x20")

    def test_help_describes_capture_controls(self):
        argv = [
            "litescope_cli",
            "--help",
        ]
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with mock.patch("sys.stdout", stdout):
                with self.assertRaises(SystemExit) as cm:
                    litescope_cli.parse_args()

        self.assertEqual(cm.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("--group selects the analyzer capture group", help_text)
        self.assertIn("--subsampling keeps one sample every N scope clock cycles", help_text)
        self.assertIn("--offset selects how many pre-trigger samples", help_text)
        self.assertIn("LiteScopeAnalyzer depth", help_text)

    def test_get_signals_filters_group(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csvname = os.path.join(tmpdir, "analyzer.csv")
            self.write_csv(csvname)

            self.assertEqual(litescope_cli.get_signals(csvname, 0), ["flag", "state"])
            self.assertEqual(litescope_cli.get_signals(csvname, 1), ["other"])

    def test_add_triggers_wires_conditions_and_edges(self):
        analyzer = FakeAnalyzer(object(), "analyzer")
        args = type("Args", (), {
            "rising_edge"   : ["flag"],
            "falling_edge"  : ["state"],
            "value_trigger" : [("flag", "1"), ("state", "0b1x0")],
        })()

        added = litescope_cli.add_triggers(args, analyzer, ["flag", "state"])

        self.assertTrue(added)
        self.assertEqual(analyzer.calls, [
            ("add_rising_edge_trigger", "flag"),
            ("add_falling_edge_trigger", "state"),
            ("add_trigger", {"flag": "1", "state": "0b1x0"}),
        ])

    def test_run_batch_configures_rle(self):
        FakeBus.instances = []
        FakeAnalyzer.instances = []
        with tempfile.TemporaryDirectory() as tmpdir:
            csvname = os.path.join(tmpdir, "analyzer.csv")
            csr_csv = os.path.join(tmpdir, "csr.csv")
            self.write_csv(csvname)
            open(csr_csv, "w").close()
            args = type("Args", (), {
                "host"          : "127.0.0.1",
                "port"          : "2345",
                "csr_csv"       : csr_csv,
                "csv"           : csvname,
                "group"         : 0,
                "subsampling"   : 4,
                "rle"           : True,
                "rising_edge"   : None,
                "falling_edge"  : None,
                "value_trigger" : None,
                "offset"        : "0x10",
                "length"        : "0x20",
                "dump"          : os.path.join(tmpdir, "dump.vcd"),
            })()

            with mock.patch.object(litescope_cli, "RemoteClient", FakeBus):
                with mock.patch.object(litescope_cli, "LiteScopeAnalyzerDriver", FakeAnalyzer):
                    litescope_cli.run_batch(args)

        self.assertEqual(len(FakeBus.instances), 1)
        self.assertEqual(FakeBus.instances[0].host, "127.0.0.1")
        self.assertEqual(FakeBus.instances[0].port, "2345")
        self.assertEqual(FakeBus.instances[0].csr_csv, csr_csv)
        self.assertTrue(FakeBus.instances[0].opened)
        self.assertTrue(FakeBus.instances[0].closed)
        self.assertEqual(len(FakeAnalyzer.instances), 1)
        analyzer = FakeAnalyzer.instances[0]
        self.assertEqual(analyzer.name, "analyzer")
        self.assertEqual(analyzer.config_csv, csvname)
        self.assertEqual(analyzer.calls, [
            ("configure_group", 0),
            ("configure_subsampler", 4),
            ("configure_rle", True),
            ("run", 0x10, 0x20),
            ("wait_done",),
            ("upload",),
            ("save", args.dump),
        ])

    def _run_main(self, tmpdir, *extra, fires=True):
        csvname = os.path.join(tmpdir, "analyzer.csv")
        csr_csv = os.path.join(tmpdir, "csr.csv")
        self.write_csv(csvname)
        open(csr_csv, "w").close()
        argv = ["litescope_cli", "--csv", csvname, "--csr-csv", csr_csv,
            "--dump", os.path.join(tmpdir, "dump.vcd")] + list(extra)
        stdout = io.StringIO()
        class Analyzer(FakeAnalyzer):
            def __init__(self, *args, **kwargs):
                FakeAnalyzer.__init__(self, *args, **kwargs)
                self.fires = fires
        with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", stdout), \
             mock.patch.object(litescope_cli, "RemoteClient", FakeBus), \
             mock.patch.object(litescope_cli, "LiteScopeAnalyzerDriver", Analyzer):
            with self.assertRaises(SystemExit) as cm:
                litescope_cli.main()
        return cm.exception.code, stdout.getvalue()

    def test_json_list(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            code, out = self._run_main(tmpdir, "--list", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["signals"], [{"name": "flag", "width": 1}, {"name": "state", "width": 3}])

    def test_json_capture(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            code, out = self._run_main(tmpdir, "--json", "-r", "flag", "--timeout", "1")
        r = json.loads(out) # Nothing else printed in JSON mode.
        self.assertEqual(code, 0)
        self.assertTrue(r["triggered"])
        self.assertEqual(r["samples"], 16)
        self.assertFalse(FakeAnalyzer.instances[-1].debug)

    def test_timeout(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            code, out = self._run_main(tmpdir, "--json", "-r", "flag", "--timeout", "0.2", fires=False)
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(out)["triggered"])
        self.assertNotIn(("upload",), FakeAnalyzer.instances[-1].calls)
        with tempfile.TemporaryDirectory() as tmpdir:
            code, out = self._run_main(tmpdir, "-r", "flag", "--timeout", "0.2", fires=False)
        self.assertEqual(code, 2)
        self.assertIn("Trigger did not fire", out)

    def test_json_argument_error(self):
        # With --json, a command-line error is a JSON error with exit code 1 (exit code 2 is the
        # trigger timeout); without --json, argparse reports it (usage, exit code 2).
        import json
        for extra in [["--bogus"], ["--group", "x"], ["-v", "flag"]]:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(sys, "argv", ["litescope_cli", "--json"] + extra), \
                 mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    litescope_cli.parse_args()
            self.assertEqual(cm.exception.code, 1, msg=extra)
            self.assertIn("ArgumentError", json.loads(stdout.getvalue())["error"])
        with mock.patch.object(sys, "argv", ["litescope_cli", "--bogus"]), \
             mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                litescope_cli.parse_args()
        self.assertEqual(cm.exception.code, 2)

    def test_json_error(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(FakeBus, "open", side_effect=ConnectionRefusedError("refused")):
                code, out = self._run_main(tmpdir, "--json")
        self.assertEqual(code, 1)
        self.assertIn("ConnectionRefusedError", json.loads(out)["error"])


if __name__ == "__main__":
    unittest.main()
