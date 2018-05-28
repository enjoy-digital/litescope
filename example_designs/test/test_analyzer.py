#!/usr/bin/env python3

from litex.soc.tools.remote import RemoteClient

from litescope import LiteScopeAnalyzerDriver

wb = RemoteClient()
wb.open()

# # #

dumps = {
    0 : "dump.vcd",
    1 : "dump.sr"
}

for group, filename in dumps.items():
    analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
    analyzer.add_rising_edge_trigger("zero")
    analyzer.configure_subsampler(1)
    analyzer.configure_group(group)
    analyzer.run(offset=32, length=128)
    analyzer.wait_done()
    analyzer.upload()
    analyzer.save(filename)

# # #

wb.close()
