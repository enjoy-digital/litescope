COREDIR = ../
PYTHON = python3

CMD = PYTHONPATH=$(COREDIR) $(PYTHON)

dump_tb:
	$(CMD) dump_tb.py

analyzer_tb:
	$(PYTHON) analyzer_tb.py

example_designs:
	cd ../example_designs && $(PYTHON) make.py -t simple -p de0nano -Ob run False build-bitstream
	cd ../example_designs && $(PYTHON) make.py -t simple -p kc705 -Ob run False build-bitstream
	cd ../example_designs && $(PYTHON) make.py -t core build-core

all: dump_tb example_designs

clean:
	rm -f dump.*
