from litex.soc.tools.remote import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

wb = RemoteClient()
wb.open()

# # #

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
analyzer.configure_trigger(cond={"counter1": 0})
analyzer.configure_subsampler(1)
analyzer.run(offset=128, length=512)
while not analyzer.done():
    pass
analyzer.upload()
analyzer.save("dump.vcd")
analyzer.save("dump.sr")

# # #

wb.close()
