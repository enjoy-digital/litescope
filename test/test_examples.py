# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import unittest
import os
import subprocess

from litescope.software.dump import *

root_dir    = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
make_script = os.path.join(root_dir, "examples", "make.py")

class TestExamples(unittest.TestCase):
    def test_simple_de0nano(self):
        os.system("rm -rf {}/build".format(root_dir))
        os.system("python3 {} -t simple -p de0nano -Ob run False build-bitstream".format(make_script))
        self.assertEqual(os.path.isfile("{}/build/litescopesoc_de0nano.v".format(root_dir)), True)

    def test_simple_kc705(self):
        os.system("rm -rf {}/build".format(root_dir))
        os.system("python3 {} -t simple -p kc705 -Ob run False build-bitstream".format(make_script))
        self.assertEqual(os.path.isfile("{}/build/litescopesoc_kc705.v".format(root_dir)), True)

    def test_core(self):
        os.system("rm -rf {}/build".format(root_dir))
        os.system("python3 {} -t core build-core".format(make_script))
        self.assertEqual(os.path.isfile("{}/build/litescope.v".format(root_dir)), True)

    def test_fast_scope_arty(self):
        os.system("rm -rf {}/build".format(root_dir))
        os.system("python3 {}/examples/fast_scope_arty.py no-compile".format(root_dir))
        self.assertEqual(os.path.isfile("{}/build/top.v".format(root_dir)), True)
