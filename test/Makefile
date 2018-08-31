COREDIR = ../
PYTHON = python3

CMD = PYTHONPATH=$(COREDIR) $(PYTHON)

examples:
	cd ../examples && $(PYTHON) make.py -t simple -p de0nano -Ob run False build-bitstream
	cd ../examples && $(PYTHON) make.py -t simple -p kc705 -Ob run False build-bitstream
	cd ../examples && $(PYTHON) make.py -t core build-core

all: examples
