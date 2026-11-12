#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litescope.software.dump.common import Dump, dec2bin


class CSVDump(Dump):
    def __init__(self, dump=None):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables

    # One "," between fields, none at the end of a row (header rows: names, widths).
    def generate_vars(self):
        r  = ",".join(variable.name       for variable in self.variables) + "\n"
        r += ",".join(str(variable.width) for variable in self.variables) + "\n"
        return r

    def generate_dumpvars(self):
        r  = ""
        for i in range(len(self)):
            values = []
            for variable in self.variables:
                try:
                    variable.current_value = variable.values[i]
                except:
                    pass
                if variable.current_value == "x":
                    values.append("x")
                else:
                    values.append(dec2bin(variable.current_value, variable.width))
            r += ",".join(values) + "\n"
        return r

    def write(self, filename):
        f = open(filename, "w")
        f.write(self.generate_vars())
        f.write(self.generate_dumpvars())
        f.close()

    def read(self, filename):
        raise NotImplementedError("CSV files can not (yet) be read, please contribute!")
