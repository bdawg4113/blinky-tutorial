# Makefile for cocotb simulation of the PIO blink design.
# See https://docs.cocotb.org/en/latest/quickstart.html for more info.
#
#   make -B              RTL simulation (iverilog + cocotb)
#   make -B GATES=yes    gate-level simulation (needs gate_level_netlist.v,
#                        which the GitHub "gds" Action produces after hardening)
#   make clean           remove build products

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src

# ---> List every Verilog file from ../src here (same list as info.yaml):
PROJECT_SOURCES = project.v pio_sm.v

# Show the [PASS]/[FAIL] lines from test.py as the simulation runs
export COCOTB_LOG_LEVEL ?= INFO

# Write waveforms as FST (tb.v does the $dumpfile)
ifeq ($(SIM),icarus)
	PLUSARGS += -fst
endif

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD = sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate-level simulation:
SIM_BUILD = sim_build/gl
COMPILE_ARGS += -DGL_TEST
COMPILE_ARGS += -DFUNCTIONAL
COMPILE_ARGS += -DSIM

# IHP sg13g2 standard-cell models + the netlist from the hardening flow.
# (If the template's original Makefile has a different path for your PDK
# version, copy that GATES section over this one.)
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between the design and the testbench
COMPILE_ARGS += -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
COCOTB_TOPLEVEL = tb
COCOTB_TEST_MODULES = test

# Run the simulation, then print a one-line verdict from results.xml
include $(shell cocotb-config --makefiles)/Makefile.sim

.PHONY: verdict
verdict:
	@python3 -c "import xml.etree.ElementTree as ET; \
t=list(ET.parse('results.xml').iter('testcase')); \
bad=[x.get('name') for x in t if x.find('failure') is not None or x.find('error') is not None]; \
print(); print('=== VERDICT: %d/%d tests passed ===' % (len(t)-len(bad), len(t))); \
[print('  FAILED:', n) for n in bad]; \
raise SystemExit(1 if bad else 0)"

# `make -B` / `make` runs the sim; `make all verdict` also prints the verdict.