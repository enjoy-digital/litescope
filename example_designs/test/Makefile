COREDIR = ../../
PYTHON = python3
SERIAL ?= 2

CMD = PYTHONPATH=$(COREDIR) $(PYTHON) make.py --port $(SERIAL)

test_regs:
	$(CMD) test_regs

test_inout:
	$(CMD) test_inout

test_logic_analyzer:
	$(CMD) test_logic_analyzer

all: test_regs test_inout test_logic_analyzer

clean:
	rm -f *.csv dump.*
