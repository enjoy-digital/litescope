#
# This file is part of LiteScope.
#
# Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litescope.software.dump.common import Dump, dec2bin


class CSVDump(Dump):
    def __init__(self, dump=None):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables

    def generate_vars(self):
        r = ""
        for variable in self.variables:
            r += variable.name
            r += ","
        r += "\n"
        for variable in self.variables:
            r += str(variable.width)
            r += ","
        r += "\n"
        return r

    def generate_dumpvars(self):
        r  = ""
        for i in range(len(self)):
            for variable in self.variables:
                try:
                    variable.current_value = variable.values[i]
                except:
                    pass
                if variable.current_value == "x":
                    r += "x"
                else:
                    r += dec2bin(variable.current_value, variable.width)
                r += ", "
            r += "\n"
        return r

    def write(self, filename):
        f = open(filename, "w")
        f.write(self.generate_vars())
        f.write(self.generate_dumpvars())
        f.close()

    def read(self, filename):
        raise NotImplementedError("CSV files can not (yet) be read, please contribute!")
