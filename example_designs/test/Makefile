COREDIR = ../../
PYTHON = python3
SERIAL ?= 2

CMD = PYTHONPATH=$(COREDIR) $(PYTHON) make.py --port $(SERIAL)

test_io:
	$(CMD) test_io

test_la:
	$(CMD) test_la

all: test_io test_la
