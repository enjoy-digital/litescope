#!/usr/bin/env python3

# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# License: BSD

import re
import csv
import sys
import argparse

from litex import RemoteClient
from litescope import LiteScopeAnalyzerDriver

# Helpers ------------------------------------------------------------------------------------------

def get_signals(csvname):
    signals = []
    with open(csvname) as f:
        reader = csv.reader(f, delimiter=",", quotechar="#")
        for typ, group, name, value in reader:
            if typ == "signal":
                signals.append(name)
    return signals

class Finder:
    def __init__(self, signals):
        self.signals = signals

    def __getitem__(self, name):
        scores = {s: 0 for s in signals}
        # exact match
        if name in scores:
            print("Exact:", name)
            return name
        # substring
        pattern = re.compile(name)
        max_score = 0
        for s in signals:
            match = pattern.search(s)
            if match:
                scores[s] = match.end() - match.start()
        max_score = max(scores.values())
        best = list(filter(lambda kv: kv[1] == max_score, scores.items()))
        assert len(best) == 1, f"Found multiple candidates: {best}"
        name, score = best[0]
        return name

# Main script --------------------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="""Run LiteScope with selected triggers

    Allows to add triggers based on signal names. Supports simple substring matching
    and Python regular expressions.
    """)
    parser.add_argument("-r", "--rising-edge",   action="append",          help="Add rising edge trigger")
    parser.add_argument("-f", "--falling-edge",  action="append",          help="Add falling edge trigger")
    parser.add_argument("-v", "--value-trigger", action="append", nargs=2, help="Add conditional trigger with given value",
                        metavar=("TRIGGER", "VALUE"))
    parser.add_argument("-l", "--list",          action="store_true",      help="List signal choices")
    parser.add_argument("--offset",              default="32",             help="Capture Offset.")
    parser.add_argument("--length",              default="128",            help="Capture Length.")
    args = parser.parse_args()
    return args

def add_triggers(args, analyzer, signals):
    added = False
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
        value = int(value, 0)
        cond[finder[signal]] = value
        print(f"Condition: {name} == {value}")
    if cond:
        analyzer.add_trigger(cond=cond)
        added = True
    return added

if __name__ == "__main__":
    args = parse_args()

    signals = get_signals("analyzer.csv")
    if args.list:
        for signal in signals:
            print(signal)
        sys.exit(0)

    wb = RemoteClient()
    wb.open()

    try:
        analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
        analyzer.configure_group(0)
        if not add_triggers(args, analyzer, signals):
            print("WARNING: no trigger added!")

        analyzer.run(offset=int(args.offset, 0), length=int(args.length, 0))

        analyzer.wait_done()
        analyzer.upload()
        analyzer.save("dump.vcd")
    finally:
        wb.close()
