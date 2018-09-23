#!/usr/bin/env python3

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
