#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages


setup(
    name                 = "litescope",
    description          = "Small footprint and configurable embedded FPGA logic analyzer core",
    author               = "Florent Kermarrec",
    author_email         = "florent@enjoy-digital.fr",
    url                  = "http://enjoy-digital.fr",
    download_url         = "https://github.com/enjoy-digital/litescope",
    test_suite           = "test",
    license              = "BSD",
    python_requires      = "~=3.7",
    packages             = find_packages(exclude=("test*", "sim*", "doc*", "examples*")),
    include_package_data = True,
    keywords             = "HDL ASIC FPGA hardware design",
    classifiers          = [
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Environment :: Console",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
    entry_points={
        "console_scripts": [
            "litescope_cli=litescope.software.litescope_cli:main",
        ],
    },
)
