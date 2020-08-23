#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from itertools import count
import datetime
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


class VCDDump(Dump):
    def __init__(self, dump=None, timescale="1ps", comment=""):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables
        self.timescale = timescale
        self.comment = comment
        self.cnt = -1

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
        r += self.timescale
        r += " $end\n"
        return r

    def generate_vars(self):
        r = "$scope "
        r += self.timescale
        r += " $end\n"
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
