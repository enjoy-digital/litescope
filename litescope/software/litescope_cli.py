#!/usr/bin/env python3

#
# This file is part of LiteScope.
#
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import csv
import sys
import time
import threading
import argparse

from litex import RemoteClient
from litescope import LiteScopeAnalyzerDriver

# Helpers ------------------------------------------------------------------------------------------

def get_signals(csvname, group):
    signals = []
    with open(csvname) as f:
        reader = csv.reader(f, delimiter=",", quotechar="#")
        for t, g, n, v in reader:
            if t == "signal" and g == str(group):
                signals.append(n)
    return signals

class Finder:
    def __init__(self, signals):
        self.signals = signals

    def __getitem__(self, name):
        scores = {s: 0 for s in self.signals}
        # Exact match
        if name in scores:
            print("Exact:", name)
            return name
        # Substring
        pattern = re.compile(name)
        max_score = 0
        for s in self.signals:
            match = pattern.search(s)
            if match:
                scores[s] = match.end() - match.start()
        max_score = max(scores.values())
        best = list(filter(lambda kv: kv[1] == max_score, scores.items()))
        assert len(best) == 1, f"Found multiple candidates: {best}"
        name, score = best[0]
        return name

def add_triggers(args, analyzer, signals):
    added  = False
    finder = Finder(signals)

    for signal in args.rising_edge or []:
        name = finder[signal]
        analyzer.add_rising_edge_trigger(name)
        print(f"Rising edge: {name}")
        added = True
    for signal in args.falling_edge or []:
        name = finder[signal]
        analyzer.add_falling_edge_trigger(finder[signal])
        print(f"Falling edge: {name}")
        added = True
    cond = {}
    for signal, value in args.value_trigger or []:
        name = finder[signal]
        cond[finder[signal]] = value
        print(f"Condition: {name} == {value}")
    if cond:
        analyzer.add_trigger(cond=cond)
        added = True
    return added

# Run Batch/GUI  -----------------------------------------------------------------------------------

def run_batch(args):
    bus = RemoteClient(host=args.host, csr_csv=args.csr_csv)
    bus.open()

    basename = os.path.splitext(os.path.basename(args.csv))[0]
    signals  = get_signals(args.csv, args.group)

    # Configure and run LiteScope analyzer.
    analyzer = LiteScopeAnalyzerDriver(bus.regs, basename, config_csv=args.csv, debug=True)
    analyzer.configure_group(args.group)
    analyzer.configure_subsampler(args.subsampling)
    if not add_triggers(args, analyzer, signals):
        print("No trigger, immediate capture.")
    analyzer.run(
        offset = int(args.offset, 0),
        length = None if args.length is None else int(args.length, 0)
    )
    analyzer.wait_done()
    analyzer.upload()
    analyzer.save(args.dump)

    # Close remove control.
    bus.close()

def run_gui(args):
    import dearpygui.dearpygui as dpg

    bus = RemoteClient(host=args.host, port=args.port, csr_csv=args.csr_csv)
    bus.open()

    triggers = get_signals(args.csv, args.group)

    def capture_callback():
        basename = os.path.splitext(os.path.basename(args.csv))[0]
        analyzer = LiteScopeAnalyzerDriver(bus.regs, basename, config_csv=args.csv, debug=True)
        analyzer.configure_group(int(dpg.get_value(item="capture_group"), 0))
        analyzer.configure_subsampler(int(dpg.get_value(item="capture_subsampling"), 0))
        trigger_cond = {}
        for trigger in triggers:
            trigger_cond[trigger] = dpg.get_value(trigger)
        analyzer.add_trigger(cond=trigger_cond)
        analyzer.run(
            offset = int(dpg.get_value(item="capture_offset"), 0),
            length = int(dpg.get_value(item="capture_length"), 0),
        )
        dpg.set_value("capture_status", "Running...")
        analyzer.wait_done()
        dpg.set_value("capture_status", "Uploading...")
        analyzer.upload()
        dpg.set_value("capture_status", "Writing...")
        analyzer.save(dpg.get_value(item="capture_dump"))
        dpg.set_value("capture_status", "Idle")

    dpg.create_context()
    dpg.create_viewport(title="LiteScope CLI GUI", max_width=400, always_on_top=True)
    dpg.setup_dearpygui()

    with dpg.window(label="Capture", autosize=True):
        dpg.add_text("Parameters")
        dpg.add_input_text(indent=8, label="Offset",      tag="capture_offset",      default_value=args.offset)
        dpg.add_input_text(indent=8, label="Length",      tag="capture_length",      default_value="128") # FIXME
        dpg.add_input_text(indent=8, label="Group",       tag="capture_group",       default_value="0")   # FIXME
        dpg.add_input_text(indent=8, label="Subsampling", tag="capture_subsampling", default_value="1")   # FIXME
        dpg.add_input_text(indent=8, label="Dump",        tag="capture_dump",        default_value=args.dump)
        dpg.add_text("Control/Status")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Run", callback=capture_callback)
            dpg.add_text(tag="capture_status", default_value="Idle")

    with dpg.window(label="Triggers", autosize=True, pos=(0, 250)):
        for trigger in triggers:
            dpg.add_input_text(indent=8, label=trigger, tag=trigger, default_value="0bx", width=100)

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

    bus.close()

# Main ---------------------------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="""LiteScope Client utility""")
    parser.add_argument("-r", "--rising-edge",   action="append",          help="Add rising edge trigger.")
    parser.add_argument("-f", "--falling-edge",  action="append",          help="Add falling edge trigger.")
    parser.add_argument("-v", "--value-trigger", action="append", nargs=2, help="Add conditional trigger with given value.",
        metavar=("TRIGGER", "VALUE"))
    parser.add_argument("-l", "--list",          action="store_true",      help="List signal choices.")
    parser.add_argument("--host",                default="localhost",      help="Host ip address")
    parser.add_argument("--port",                default="1234",           help="Host bind port.")
    parser.add_argument("--csv",                 default="analyzer.csv",   help="Analyzer CSV file.")
    parser.add_argument("--csr-csv",             default="csr.csv",        help="SoC CSV file.")
    parser.add_argument("--group",               default=0, type=int,      help="Capture Group.")
    parser.add_argument("--subsampling",         default=1, type=int,      help="Capture Subsampling.")
    parser.add_argument("--offset",              default="32",             help="Capture Offset.")
    parser.add_argument("--length",              default=None,             help="Capture Length.")
    parser.add_argument("--dump",                default="dump.vcd",       help="Capture Filename.")
    parser.add_argument("--gui",                 action="store_true",      help="Run Gui.")
    args = parser.parse_args()
    return args

def main():
    args = parse_args()

    # Check if analyzer file is present and exit if not.
    if not os.path.exists(args.csv):
        raise ValueError("{} not found. This is necessary to load the wires which have been tapped to scope."
                         "Try setting --csv to value of the csr_csv argument to LiteScopeAnalyzer in the SoC.".format(args.csv))
        sys.exit(1)

    # If in list mode, list signals and exit.
    if args.list:
        signals = get_signals(args.csv, args.group)
        for signal in signals:
            print(signal)
        sys.exit(0)

    # Create and open remote control.
    if not os.path.exists(args.csr_csv):
        raise ValueError("{} not found. This is necessary to load the 'regs' of the remote. Try setting --csr-csv here to "
                         "the path to the --csr-csv argument of the SoC build.".format(args.csr_csv))

    # Run Batch/Gui.
    if args.gui:
        run_gui(args)
    else:
        run_batch(args)


if __name__ == "__main__":
    main()
