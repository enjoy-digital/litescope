LSDIR = ../../
PYTHON = python3

example_designs:
	cd ../example_designs && $(PYTHON) make.py -t simple -p de0nano -Ob run False build-bitstream
	cd ../example_designs && $(PYTHON) make.py -t simple -p kc705 -Ob run False build-bitstream
	cd ../example_designs && $(PYTHON) make.py -t core build-core
