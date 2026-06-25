#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from itertools import count
import datetime
import os
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
    match = re.fullmatch(r"(\d+)(\w{0,1})s", timescale)
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
                val = v.values[self.cnt + 1]
                if val != v.current_value:
                    v.current_value = val
                    c += f"b{dec2bin(val, v.width)} {v.code}\n"
                    if self._has_enum(v):
                        c += f"b{self._enum_text_bits(v, val)} {v.text_code}\n"
            except:
                pass
        if c != "":
            r += f"#{self.cnt + 1}\n{c}"
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
        r = "$scope module top $end\n"
        for v in self.variables:
            r += "$var wire "
            r += str(v.width)
            r += " "
            r += v.code
            r += " "
            r += v.name
            r += " $end\n"
            if self._has_enum(v):
                r += "$var wire "
                r += str(self._enum_text_width(v))
                r += " "
                r += v.text_code
                r += " "
                r += self._enum_text_name(v)
                r += " $end\n"
        r += "$upscope "
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
            if self._has_enum(v):
                r += "b"
                r += dec2bin(v.current_value, self._enum_text_width(v))
                r += " "
                r += v.text_code
                r += "\n"
        r += "$end\n"
        return r

    def generate_valuechange(self):
        r = ""
        for i in range(len(self)):
            r += self.change()
            self.cnt += 1
        return r

    def _gtkw_variable_name(self, variable):
        if variable.width == 1:
            return "top.{}".format(variable.name)
        return "top.{}[{}:0]".format(variable.name, variable.width - 1)

    def _gtkw_text_variable_name(self, variable):
        return "top.{}[{}:0]".format(self._enum_text_name(variable), self._enum_text_width(variable) - 1)

    def _has_enum(self, variable):
        return len(getattr(variable, "enum", {})) != 0

    def _enum_text_name(self, variable):
        return "{}_text".format(variable.name)

    def _enum_text_width(self, variable):
        labels = [str(label) for label in variable.enum.values()]
        labels.append(str(2**variable.width - 1))
        return max(1, max(len(label) for label in labels))*8

    def _enum_text_bits(self, variable, value):
        width = self._enum_text_width(variable)//8
        label = str(variable.enum.get(value, value))
        data  = label.encode("ascii", errors="replace")
        data  = data[:width].ljust(width, b" ")
        return "".join("{:08b}".format(c) for c in data)

    def generate_gtkw(self, filename, filters=None):
        filters = {} if filters is None else filters
        r = ""
        r += "[*] Auto-Generated by LiteScope\n"
        r += "[dumpfile] \"{}\"\n".format(filename)
        for v in self.variables:
            filter_filename = filters.get(v.name, None)
            r += "@{}\n".format(2022 if filter_filename is not None else 22)
            if filter_filename is not None:
                r += "^1 {}\n".format(filter_filename)
            r += "{}\n".format(self._gtkw_variable_name(v))
            if self._has_enum(v):
                r += "@28\n"
                r += "{}\n".format(self._gtkw_text_variable_name(v))
        return r

    def __repr__(self):
        r = ""
        return r

    def finalize(self):
        codegen = vcd_codes()
        for v in self.variables:
            v.code = next(codegen)
            if self._has_enum(v):
                v.text_code = next(codegen)

    def write_gtkw(self, filename, gtkw_filename=None, filters=None):
        if gtkw_filename is None:
            gtkw_filename = os.path.splitext(filename)[0] + ".gtkw"
        with open(gtkw_filename, "w") as f:
            f.write(self.generate_gtkw(filename, filters=filters))

    def write(self, filename, gtkw_filename=None, gtkw_filters=None):
        self.finalize()
        f = open(filename, "w")
        f.write(self.generate_date())
        f.write(self.generate_timescale())
        f.write(self.generate_vars())
        f.write(self.generate_dumpvars())
        f.write(self.generate_valuechange())
        f.close()
        if (gtkw_filename is not None) or (gtkw_filters is not None):
            self.write_gtkw(filename, gtkw_filename=gtkw_filename, filters=gtkw_filters)

    def read(self, filename):
        raise NotImplementedError("VCD files can not (yet) be read, please contribute!")
