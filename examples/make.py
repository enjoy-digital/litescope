#!/usr/bin/env python3

# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import sys
import os
import argparse
import subprocess
import struct
import importlib

from migen.fhdl import verilog
from migen.fhdl.structure import _Fragment

from litex.build.tools import write_to_file
from litex.build.xilinx.common import *

from litex.soc.integration import cpu_interface


def autotype(s):
    if s == "True":
        return True
    elif s == "False":
        return False
    try:
        return int(s, 0)
    except ValueError:
        pass
    return s


def _import(default, name):
    return importlib.import_module(default + "." + name)


def _get_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
LiteScope - based on Migen.

This program builds and/or loads LiteScope components.
One or several actions can be specified:

clean           delete previous build(s).
build-core      build verilog core.
build-bitstream build-bitstream build FPGA bitstream.
build-csr-csv   save CSR map into CSV file.

load-bitstream  load bitstream into volatile storage.

all             clean, build-csr-csv, build-bitstream, load-bitstream.
""")

    parser.add_argument("-t", "--target", default="simple", help="Core type to build")
    parser.add_argument("-s", "--sub-target", default="", help="variant of the Core type to build")
    parser.add_argument("-p", "--platform", default=None, help="platform to build for")
    parser.add_argument("-Ot", "--target-option", default=[], nargs=2, action="append", help="set target-specific option")
    parser.add_argument("-Op", "--platform-option", default=[], nargs=2, action="append", help="set platform-specific option")
    parser.add_argument("-Ob", "--build-option", default=[], nargs=2, action="append", help="set build option")
    parser.add_argument("--csr_csv", default="./test/csr.csv", help="CSV file to save the CSR map into")

    parser.add_argument("action", nargs="+", help="specify an action")

    return parser.parse_args()

if __name__ == "__main__":
    args = _get_args()

    # create top-level Core object
    target_module = _import("targets", args.target)
    if args.sub_target:
        top_class = getattr(target_module, args.sub_target)
    else:
        top_class = target_module.default_subtarget

    if hasattr(top_class, "platform"):
        platform = top_class.platform
        platform_name = top_class.platform.name
    else:
        if args.platform is None:
            if hasattr(top_class, "default_platform"):
                platform_name = top_class.default_platform
            else:
                raise ValueError("Target has no default platform, specify a platform with -p your_platform")
        else:
            platform_name = args.platform
        try:
            platform_module = _import("litex.boards.platforms", platform_name)
        except:
            platform_module = _import("migen.build.platforms", platform_name)
        platform_kwargs = dict((k, autotype(v)) for k, v in args.platform_option)
        platform = platform_module.Platform(**platform_kwargs)

    build_name = top_class.__name__.lower() + "_" + platform_name
    top_kwargs = dict((k, autotype(v)) for k, v in args.target_option)
    soc = top_class(platform, **top_kwargs)
    soc.finalize()

    # decode actions
    action_list = ["clean", "build-csr-csv", "build-core", "build-bitstream", "load-bitstream", "all"]
    actions = {k: False for k in action_list}
    for action in args.action:
        if action in actions:
            actions[action] = True
        else:
            print("Unknown action: "+action+". Valid actions are:")
            for a in action_list:
                print("  "+a)
            sys.exit(1)

    print("""
      __   _ __      ____
     / /  (_) /____ / __/______  ___  ___
    / /__/ / __/ -_)\ \/ __/ _ \/ _ \/ -_)
   /____/_/\__/\__/___/\__/\___/ .__/\__/
                              /_/

   A small footprint and configurable embedded FPGA
       logic analyzer core powered by LiteX

====== Building parameters: ======""")
if hasattr(soc, "io"):
    print("""
LiteScopeIO
-----------
Width: {}
""".format(soc.io.data_width)
)

if hasattr(soc, "analyzer"):
    print("""
LiteScopeAnalyzer
-----------------
Width: {}
Depth: {}
===============================""".format(
    soc.analyzer.data_width,
    soc.analyzer.depth
    )
)

    # dependencies
    if actions["all"]:
        actions["build-csr-csv"] = True
        actions["build-bitstream"] = True
        actions["load-bitstream"] = True

    if actions["build-bitstream"]:
        actions["build-csr-csv"] = True

    if actions["clean"]:
        subprocess.call(["rm", "-rf", "build/*"])

    if actions["build-csr-csv"]:
        csr_csv = cpu_interface.get_csr_csv(soc.csr_regions, soc.constants)
        write_to_file(args.csr_csv, csr_csv)

    if actions["build-core"]:
        soc_fragment = soc.get_fragment()
        platform.finalize(soc_fragment)
        v_output = platform.get_verilog(soc_fragment, name="litescope",
            special_overrides=xilinx_special_overrides)
        if not os.path.exists("build"):
            os.makedirs("build")
        v_output.write("build/litescope.v")

    if actions["build-bitstream"]:
        build_kwargs = dict((k, autotype(v)) for k, v in args.build_option)
        vns = platform.build(soc, build_name=build_name, **build_kwargs)
        if hasattr(soc, "do_exit") and vns is not None:
            if hasattr(soc.do_exit, '__call__'):
                soc.do_exit(vns)

    if actions["load-bitstream"]:
        prog = platform.create_programmer()
        prog.load_bitstream("build/" + build_name + platform.bitstream_ext)
