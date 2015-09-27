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

    def decode_rle(self):
        datas = DumpData(self.width - 1)
        last_data = 0
        for data in self:
            rle = data >> (self.width - 1)
            data = data & (2**(self.width - 1) - 1)
            if rle:
                for i in range(data):
                    datas.append(last_data)
            else:
                datas.append(data)
                last_data = data
        return datas


class DumpVariable:
    def __init__(self, name, width, values=[]):
        self.width = width
        self.name = name
        self.values = [int(v)%2**width for v in values]

    def __len__(self):
        return len(self.values)


class Dump:
    def __init__(self):
        self.variables = []

    def add(self, variable):
        self.variables.append(variable)

    def add_from_layout(self, layout, variable):
        i = 0
        for s, n in layout:
            self.add(DumpVariable(s, n, variable[i:i+n]))
            i += n

    def __len__(self):
        l = 0
        for variable in self.variables:
            l = max(len(variable), l)
        return l
