```
                                 __   _ __      ____
                                / /  (_) /____ / __/______  ___  ___
                               / /__/ / __/ -_)\ \/ __/ _ \/ _ \/ -_)
                              /____/_/\__/\__/___/\__/\___/ .__/\__/
                                                         /_/
                               Copyright 2015-2020 / EnjoyDigital

                           A small footprint and configurable Logic Analyzer
                                    core powered by Migen & LiteX
```

[![](https://github.com/enjoy-digital/litescope/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litescope/actions) ![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)


[> Intro
--------
LiteScope provides a small footprint and configurable embedded logic analyzer that you
can use in your FPGA and aims to provide a free, portable and flexible
alternative to vendor's solutions!

LiteScope is part of LiteX libraries whose aims are to lower entry level of
complex FPGA cores by providing simple, elegant and efficient implementations
of components used in today's SoC such as Ethernet, SATA, PCIe, SDRAM Controller...

Using Migen to describe the HDL allows the core to be highly and easily configurable.

LiteScope can be used as LiteX library or can be integrated with your standard
design flow by generating the verilog rtl that you will use as a standard core.

[> Features
-----------
- IO peek and poke with LiteScopeIO.
- Logic analyser with LiteScopeAnalyzer:
  - Subsampling.
  - Data storage in Block RAM.
  - Configurable triggers.
- Bridges:
  - UART <--> Wishbone (provided by LiteX)
  - Ethernet <--> Wishbone ("Etherbone") (provided by LiteEth)
  - PCIe <--> Wishbone (provided by LitePCIe)
- Exports formats: .vcd, .sr(sigrok), .csv, .py, etc...

[> Proven
---------
LiteScope has already been used to investigate issues on several commercial or
open-source designs.

[> Possible improvements
------------------------
- add standardized interfaces (AXI, Avalon-ST)
- add protocols analyzers
- add signals injection/generation
- add storage in DRAM
- add storage in HDD with LiteSATA core
- ... See below Support and consulting :)

If you want to support these features, please contact us at florent [AT]
enjoy-digital.fr.

[> Getting started
------------------
1. Install Python 3.6+ and FPGA vendor's development tools.
2. Install LiteX and the cores by following the LiteX's wiki [installation guide](https://github.com/enjoy-digital/litex/wiki/Installation).
3. You can find examples of integration of the core with LiteX in LiteX-Boards and in the examples directory.

[> Tests
--------
Unit tests are available in ./test/.
To run all the unit tests:
```sh
$ ./setup.py test
```

Tests can also be run individually:
```sh
$ python3 -m unittest test.test_name
```

[> License
----------
LiteScope is released under the very permissive two-clause BSD license. Under
the terms of this license, you are authorized to use LiteScope for closed-source
proprietary designs.
Even though we do not require you to do so, those things are awesome, so please
do them if possible:
 - tell us that you are using LiteScope
 - cite LiteScope in publications related to research it has helped
 - send us feedback and suggestions for improvements
 - send us bug reports when something goes wrong
 - send us the modifications and improvements you have done to LiteScope.

[> Support and consulting
-------------------------
We love open-source hardware and like sharing our designs with others.

LiteScope is developed and maintained by EnjoyDigital.

If you would like to know more about LiteScope or if you are already a happy
user and would like to extend it for your needs, EnjoyDigital can provide standard
commercial support as well as consulting services.

So feel free to contact us, we'd love to work with you! (and eventually shorten
the list of the possible improvements :)

[> Contact
----------
E-mail: florent [AT] enjoy-digital.fr