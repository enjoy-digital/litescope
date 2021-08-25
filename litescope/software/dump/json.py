#
# This file is part of LiteScope.
#
# Copyright (c) 2021 Arnaud Durand <arnaud.durand@unifr.ch>
# SPDX-License-Identifier: BSD-2-Clause

import json

from litescope.software.dump.common import Dump


class JSONDump(Dump):
    def __init__(self, dump=None):
        Dump.__init__(self)
        self.variables = [] if dump is None else dump.variables

    def generate_data(self):
        return {v.name: v.values for v in self.variables}

    def write(self, filename):
        with open(filename, "w") as f:
            json.dump(self.generate_data(), f)

    def read(self, filename):
        raise NotImplementedError("JSON files can not (yet) be read, please contribute!")
