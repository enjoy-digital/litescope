#!/usr/bin/env python3

from litex import RemoteClient

from litescope import LiteScopeAnalyzerDriver

wb = RemoteClient()
wb.open()

# # #

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
analyzer.configure_subsampler(1)
analyzer.configure_group(1)
analyzer.add_rising_edge_trigger("uartwishbonebridge_wishbone_stb")
analyzer.add_rising_edge_trigger("uartwishbonebridge_wishbone_ack")
analyzer.run(offset=32, length=128)
analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

# # #

wb.close()
