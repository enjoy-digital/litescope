COREDIR = ../
PYTHON = python3

CMD = PYTHONPATH=$(COREDIR) $(PYTHON)

example_designs:
	cd ../example_designs && $(PYTHON) make.py -t simple -p de0nano -Ob run False build-bitstream
	cd ../example_designs && $(PYTHON) make.py -t simple -p kc705 -Ob run False build-bitstream
	cd ../example_designs && $(PYTHON) make.py -t core build-core

all: example_designs
