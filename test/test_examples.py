#
# This file is part of LiteScope.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import os
import subprocess
import sys
import tempfile

from litescope.software.dump import *

root_dir    = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
examples_dir = os.path.join(root_dir, "examples")
arty_py = os.path.join(examples_dir, "arty.py")

class TestExamples(unittest.TestCase):
    def test_arty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "digilent_arty")
            subprocess.check_call([
                sys.executable, arty_py,
                "--output-dir", output_dir,
            ], cwd=tmpdir)
            self.assertEqual(os.path.isfile(
                os.path.join(output_dir, "gateware", "digilent_arty.v")
            ), True)
