#!/usr/bin/env python3

# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import time

from litex import RemoteClient

from litescope import LiteScopeIODriver

wb = RemoteClient()
wb.open()

# # #

def led_anim0(inout):
    for i in range(10):
        io.write(0xa5)
        time.sleep(0.1)
        io.write(0x5a)
        time.sleep(0.1)

def led_anim1(inout):
    for j in range(4):
        # Led <<
        led_data = 1
        for i in range(8):
            io.write(led_data)
            time.sleep(i*i*0.0020)
            led_data = (led_data << 1)
        # Led >>
        ledData = 128
        for i in range(8):
            io.write(led_data)
            time.sleep(i*i*0.0020)
            led_data = (led_data >> 1)

io = LiteScopeIODriver(wb.regs, "io")

led_anim0(io)
led_anim1(io)
print("{:02x}".format(io.read()))

# # #

wb.close()
