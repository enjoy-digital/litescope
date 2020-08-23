#
# This file is part of LiteScope.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
import os

from litescope.software.dump import *

root_dir    = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")

class TestExamples(unittest.TestCase):
    def test_arty(self):
        os.system(f"rm -rf {root_dir}/build")
        os.system(f"cd {root_dir}/examples && python3 arty.py")
        self.assertEqual(os.path.isfile(f"{root_dir}/examples/build/arty/gateware/arty.v"), True)

