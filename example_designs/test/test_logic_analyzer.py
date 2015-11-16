from litex.soc.tools.remote import RemoteClient

wb = RemoteClient()
wb.open()

# # #

logic_analyzer = LiteScopeLogicAnalyzerDriver(wb.regs, "logic_analyzer", debug=True)

cond = {} # immediate trigger
logic_analyzer.configure_term(port=0, cond=cond)
logic_analyzer.configure_sum("term")
logic_analyzer.configure_subsampler(1)
# logic_analyzer.configure_qualifier(1)
logic_analyzer.configure_rle(1)
logic_analyzer.run(offset=128, length=256)

while not logic_analyzer.done():
    pass
logic_analyzer.upload()

logic_analyzer.save("dump.vcd")
logic_analyzer.save("dump.csv")
logic_analyzer.save("dump.py")
logic_analyzer.save("dump.sr")

# # #

wb.close()
