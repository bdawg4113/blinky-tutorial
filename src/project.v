/*
 * Copyright (c) 2026 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_pio_blink (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, ignore
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // ---------------- Clock divider ("tick" generator) ----------------
    // ui_in[3:0] = N:
    //   N = 0      -> one tick every clock (full speed, used by the tests)
    //   N = 1..15  -> one tick every 2^(N+8) clocks
    // Each PIO instruction here lasts 32 ticks, so at 50 MHz:
    //   N = 11 -> 2^19 clocks/tick -> LED toggles ~3 times/s (nice and visible)
    //   N = 15 -> 2^23 clocks/tick -> LED toggles every ~5 s
    wire [3:0]  div_sel = ui_in[3:0];
    wire [4:0]  shift   = (div_sel == 4'd0) ? 5'd0 : ({1'b0, div_sel} + 5'd8);
    wire [23:0] mask    = (24'd1 << shift) - 24'd1;

    reg [23:0] prescaler;
    always @(posedge clk) begin
        if (!rst_n) prescaler <= 24'd0;
        else        prescaler <= prescaler + 24'd1;
    end

    wire tick = ((prescaler & mask) == mask);

    // ---------------- PIO state machine ----------------
    wire [4:0] pio_pins;

    pio_sm sm0 (
        .clk   (clk),
        .rst_n (rst_n),
        .tick  (tick),
        .pins  (pio_pins)
    );

    // ---------------- Pin mapping ----------------
    assign uo_out  = {3'b000, pio_pins};   // uo_out[0] = the blinking LED
    assign uio_out = 8'h00;
    assign uio_oe  = 8'h00;                // all bidirectional pins are inputs

    // Avoid lint warnings about unused inputs
    wire _unused = &{ena, ui_in[7:4], uio_in, 1'b0};

endmodule