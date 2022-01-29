#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from itertools import count
import datetime
import re
from litescope.software.dump.common import Dump, dec2bin


def vcd_codes():
    codechars = [chr(i) for i in range(33, 127)]
    for n in count():
        q, r = divmod(n, len(codechars))
        code = codechars[r]
        while q > 0:
            q, r = divmod(q, len(codechars))
            code = codechars[r] + code
        yield code

_si_prefix2exp = {
    "":    0,
    "m":  -3,
    "u":  -6,
    "n":  -9,
    "p": -12,
    "f": -15,
}

def _timescale_str2num(timescale):
    match = re.fullmatch("(\d+)(\w{0,1})s", timescale)
    num = int(match.group(1))
    si_prefix = match.group(2)
    exp = _si_prefix2exp[si_prefix]
    return num * 10**exp, si_prefix


class VCDDump(Dump):
    def __init__(self, dump=None, samplerate=1e-12, timescale="1ps", comment=""):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables
        self.timescale = timescale
        self.comment = comment
        self.cnt = -1
        # rescale the timescale from the provided one to one where it is equal to the samplerate
        # this lets us output sequential change timestamps which helps with software like PulseView
        # that slow down if a much smaller timescale than necessary is used
        timescale_seconds, si_prefix = _timescale_str2num(timescale)
        # factor of 2 scale is because of 2x samples from fake clock
        self.count_timescale = int(1 / (timescale_seconds * samplerate * 2))
        self.timescale_unit_str = si_prefix + "s"

    def change(self):
        r = ""
        c = ""
        for v in self.variables:
            try:
                if v.values[self.cnt + 1] != v.current_value:
                    c += "b"
                    c += dec2bin(v.values[self.cnt + 1], v.width)
                    c += " "
                    c += v.code
                    c += "\n"
            except:
                pass
        if c != "":
            r += "#"
            r += str(self.cnt+1)
            r += "\n"
            r += c
        return r

    def generate_date(self):
        now = datetime.datetime.now()
        r = "$date\n"
        r += "\t"
        r += now.strftime("%Y-%m-%d %H:%M")
        r += "\n"
        r += "$end\n"
        return r

    def generate_version(self):
        r = "$version\n"
        r += "\tlitescope VCD dump\n"
        r += "$end\n"
        return r

    def generate_timescale(self):
        r = "$timescale "
        r += str(self.count_timescale) + self.timescale_unit_str
        r += " $end\n"
        return r

    def generate_vars(self):
        r = "$scope dumped_signals $end\n"
        for v in self.variables:
            r += "$var wire "
            r += str(v.width)
            r += " "
            r += v.code
            r += " "
            r += v.name
            r += " $end\n"
        r += "$unscope "
        r += " $end\n"
        r += "$enddefinitions "
        r += " $end\n"
        return r

    def generate_dumpvars(self):
        r = "$dumpvars\n"
        for v in self.variables:
            v.current_value = "x"
            r += "b"
            r += dec2bin(v.current_value, v.width)
            r += " "
            r += v.code
            r += "\n"
        r += "$end\n"
        return r

    def generate_valuechange(self):
        r = ""
        for i in range(len(self)):
            r += self.change()
            self.cnt += 1
        return r

    def __repr__(self):
        r = ""
        return r

    def finalize(self):
        codegen = vcd_codes()
        for v in self.variables:
            v.code = next(codegen)

    def write(self, filename):
        self.finalize()
        f = open(filename, "w")
        f.write(self.generate_date())
        f.write(self.generate_timescale())
        f.write(self.generate_vars())
        f.write(self.generate_dumpvars())
        f.write(self.generate_valuechange())
        f.close()

    def read(self, filename):
        raise NotImplementedError("VCD files can not (yet) be read, please contribute!")
