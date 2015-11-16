import time
from litex.soc.tools.remote import RemoteClient
from litescope.software.driver.inout import LiteScopeInOutDriver


def led_anim0(inout):
    for i in range(10):
        inout.write(0xA5)
        time.sleep(0.1)
        inout.write(0x5A)
        time.sleep(0.1)


def led_anim1(inout):
    for j in range(4):
        # Led <<
        led_data = 1
        for i in range(8):
            inout.write(led_data)
            time.sleep(i*i*0.0020)
            led_data = (led_data << 1)
        # Led >>
        ledData = 128
        for i in range(8):
            inout.write(led_data)
            time.sleep(i*i*0.0020)
            led_data = (led_data >> 1)

wb = RemoteClient()
wb.open()

# # #

inout = LiteScopeInOutDriver(wb.regs, "inout")

led_anim0(inout)
led_anim1(inout)
print("{:02X}".format(inout.read()))

# # #

wb.close()
