#
# This file is part of LiteScope.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 kees.jongenburger <kees.jongenburger@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

def dec2bin(d, width=0):
    if d == "x":
        return "x"*width
    elif d == 0:
        b = "0"
    else:
        b = ""
        while d != 0:
            b = "01"[d&1] + b
            d = d >> 1
    return b.zfill(width)


def get_bits(values, low, high=None):
    r = []
    if high is None:
        high = low + 1
    for val in values:
        t = (val >> low) & (2**(high - low) - 1)
        r.append(t)
    return r


class DumpData(list):
    def __init__(self, width):
        self.width = width

    def __getitem__(self, key):
        if isinstance(key, int):
            return get_bits(self, key)
        elif isinstance(key, slice):
            if key.start != None:
                start = key.start
            else:
                start = 0
            if key.stop != None:
                stop = key.stop
            else:
                stop = self.width
            if stop > self.width:
                stop = self.width
            if key.step != None:
                raise KeyError
            return get_bits(self, start, stop)
        else:
            raise KeyError


class DumpVariable:
    def __init__(self, name, width, values=[]):
        self.name = name
        self.width = width
        self.values = [int(v)%2**width for v in values]

    def __len__(self):
        return len(self.values)


class Dump:
    def __init__(self):
        self.variables = []

    def add(self, variable):
        self.variables.append(variable)

    def add_from_layout(self, layout, variable):
        offset = 0
        for name, sample_width in layout:
            values = variable[offset:offset+sample_width]
            values2x = [values[i//2] for i in range(len(values)*2)]
            self.add(DumpVariable(name, sample_width, values2x))
            offset += sample_width

    def add_from_layout_flatten(self, layout, variable):
        offset = 0
        for name, sample_width in layout:
            # The samples from the logic analyzer end up in an array of size sample size
            # and have n (number of channel) bits. The following does a bit slice on the array
            # elements (implemented above)
            values         = variable[offset:offset+sample_width]
            values_flatten = [values[i//sample_width] >> (i % sample_width ) & 1 for i in range(len(values)*sample_width)]
            self.add(DumpVariable(name, 1, values_flatten))
            offset += sample_width

    def add_scope_clk(self):
        self.add(DumpVariable("scope_clk", 1, [1, 0]*(len(self)//2)))

    def add_scope_trig(self, offset):
        self.add(DumpVariable("scope_trig", 1, [0]*offset + [1]*(len(self)-offset)))

    def __len__(self):
        l = 0
        for variable in self.variables:
            l = max(len(variable), l)
        return l
