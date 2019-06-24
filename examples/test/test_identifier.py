#!/usr/bin/env python3

# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litex import RemoteClient

wb = RemoteClient()
wb.open()

# # #

fpga_id = ""
for i in range(256):
    c = chr(wb.read(wb.bases.identifier_mem + 4*i) & 0xff)
    fpga_id += c
    if c == "\0":
        break
print(fpga_id)

# # #

wb.close()
