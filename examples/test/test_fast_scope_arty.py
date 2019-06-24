#!/usr/bin/env python3

from litex import RemoteClient

from litescope import LiteScopeAnalyzerDriver

wb = RemoteClient()
wb.open()

# # #

subsample = 1
analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
analyzer.configure_subsampler(subsample)
analyzer.configure_group(0)
analyzer.run(offset=32, length=512)
analyzer.wait_done()
analyzer.upload()

#
# Convert parallel input back to a flaten view (e.g. the 8 bits values are flattened)
# 
analyzer.save("dump.vcd",flatten=True)

# # #

wb.close()
