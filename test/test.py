# SPDX-FileCopyrightText: © 2026 TQT
# SPDX-License-Identifier: Apache-2.0
#
# Tests for the PIO blink design. Program under test (see src/pio_sm.v):
#
#   addr 0:  set pins, 1 [31]
#   addr 1:  set pins, 0 [31]
#   addr 2:  jmp 0
#
# Every individual check prints [PASS] or [FAIL] in the log, and cocotb prints
# a PASS/FAIL summary table for each test at the end of `make`.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


class Checker:
    """Logs every check as [PASS]/[FAIL]; the test fails at the end if any failed."""

    def __init__(self, dut):
        self.dut = dut
        self.failures = 0

    def check(self, name, ok, detail=""):
        if ok:
            self.dut._log.info(f"[PASS] {name}")
        else:
            self.dut._log.error(f"[FAIL] {name}  ({detail})")
            self.failures += 1

    def done(self):
        assert self.failures == 0, f"{self.failures} check(s) failed, see [FAIL] lines above"


async def reset(dut, ui_in=0):
    """Start the clock and apply reset. ui_in[3:0]=0 -> state machine ticks every clock."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="us").start())
    dut.ena.value = 1
    dut.ui_in.value = ui_in
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    for _ in range(10):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1


async def capture(dut, n_cycles):
    """Sample uo_out every clock. Returns (led_trace, other_pins_ever_high)."""
    led, other = [], 0
    for _ in range(n_cycles):
        await RisingEdge(dut.clk)
        v = int(dut.uo_out.value)
        led.append(v & 1)
        other |= v >> 1
    return led, other


def find_edges(led):
    """Indexes of: first rise, first fall, second rise. None if not found."""
    r1 = f1 = r2 = None
    try:
        r1 = led.index(1)
        f1 = led.index(0, r1)
        r2 = led.index(1, f1)
    except ValueError:
        pass  # whatever wasn't found stays None
    return r1, f1, r2


@cocotb.test()
async def test_00_reset(dut):
    """After reset the LED is off and nothing else is driven."""
    c = Checker(dut)
    await reset(dut)
    # Look at the outputs only during the first couple of cycles after reset
    led, other = await capture(dut, 1)
    c.check("reset: LED is off right after reset", led[0] == 0, f"LED={led[0]}")
    c.check("reset: uo_out[4:1] are low", other == 0, f"other={other:#x}")
    c.check("reset: uio_oe == 0 (all bidir pins are inputs)", int(dut.uio_oe.value) == 0)
    c.done()


@cocotb.test()
async def test_01_instr0_set_pins_1(dut):
    """Instruction 0: SET PINS,1 [31] -> LED turns on, stays on for 1+31 ticks."""
    c = Checker(dut)
    await reset(dut)
    led, _ = await capture(dut, 200)
    r1, f1, _ = find_edges(led)
    c.check("instr 0 (set pins,1): LED turns on within 3 cycles",
            r1 is not None and r1 <= 2, f"first rise at cycle {r1}")
    c.check("instr 0 delay [31]: LED stays on for exactly 32 cycles",
            r1 is not None and f1 is not None and f1 - r1 == 32,
            f"high for {None if r1 is None or f1 is None else f1 - r1} cycles")
    c.done()


@cocotb.test()
async def test_02_instr1_set_pins_0(dut):
    """Instruction 1: SET PINS,0 [31] (+ the JMP tick) -> LED off for 33 cycles."""
    c = Checker(dut)
    await reset(dut)
    led, _ = await capture(dut, 200)
    _, f1, r2 = find_edges(led)
    c.check("instr 1 (set pins,0): LED turns off after instr 0's delay",
            f1 is not None, "LED never fell")
    c.check("instr 1 delay [31] + instr 2 (jmp): LED stays off for exactly 33 cycles",
            f1 is not None and r2 is not None and r2 - f1 == 33,
            f"low for {None if f1 is None or r2 is None else r2 - f1} cycles")
    c.done()


@cocotb.test()
async def test_03_instr2_jmp(dut):
    """Instruction 2: JMP 0 -> program loops, period is 32 + 33 = 65 cycles."""
    c = Checker(dut)
    await reset(dut)
    led, _ = await capture(dut, 300)
    r1, _, r2 = find_edges(led)
    c.check("instr 2 (jmp 0): LED turns on a second time (program wrapped)",
            r2 is not None, "no second rising edge")
    c.check("instr 2 (jmp 0): blink period is 65 cycles",
            r1 is not None and r2 is not None and r2 - r1 == 65,
            f"period {None if r1 is None or r2 is None else r2 - r1}")
    # Check a third period too, to be sure it keeps looping
    try:
        r3 = led.index(0, r2)
        r3 = led.index(1, r3)
        c.check("instr 2 (jmp 0): second period is also 65 cycles", r3 - r2 == 65,
                f"period {r3 - r2}")
    except ValueError:
        c.check("instr 2 (jmp 0): second period is also 65 cycles", False, "no third rise")
    c.done()


@cocotb.test()
async def test_04_unused_pins(dut):
    """uo_out[7:1] must stay low and bidirectional pins must stay inputs."""
    c = Checker(dut)
    await reset(dut)
    _, other = await capture(dut, 200)
    c.check("uo_out[7:1] stayed low during the blink", other == 0, f"other={other:#x}")
    c.check("uio_oe stayed 0", int(dut.uio_oe.value) == 0)
    c.check("uio_out stayed 0", int(dut.uio_out.value) == 0)
    c.done()


@cocotb.test()
async def test_05_clock_divider(dut):
    """ui_in[3:0]=1 -> one tick per 512 clocks, so LED high time is 32*512 cycles."""
    c = Checker(dut)
    await reset(dut, ui_in=1)
    led, _ = await capture(dut, 20000)
    r1, f1, _ = find_edges(led)
    expected = 32 * 512
    got = None if r1 is None or f1 is None else f1 - r1
    c.check(f"clock divider N=1: LED high for {expected} cycles", got == expected,
            f"high for {got} cycles")
    c.done()