// pio_sm.v - A minimal PIO-style state machine (beginner version)
//
// Instruction format (same as RP2040 PIO):
//   [15:13] opcode   000 = JMP, 111 = SET, anything else = NOP here
//   [12:8]  delay    extra ticks to wait AFTER the instruction runs
//   [7:5]   arg1     JMP: condition   SET: destination
//   [4:0]   arg2     JMP: address     SET: data
//
// JMP conditions:  000 always, 001 !X, 010 X-- , 011 !Y, 100 Y--
// SET destinations: 000 pins, 001 X, 010 Y
//
// The machine only advances when `tick` is high, so a clock divider
// outside this module controls how fast the program runs.

`default_nettype none

module pio_sm (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tick,       // 1 = execute one step this clock
    output reg  [4:0] pins        // result of "SET PINS"
);

    localparam [2:0] OP_JMP = 3'b000;
    localparam [2:0] OP_SET = 3'b111;

    // ------------------------------------------------------------------
    // Program memory: edit this to change what the state machine does.
    // Helper layout: {opcode, delay, arg1, arg2}
    // ------------------------------------------------------------------
    function [15:0] rom(input [4:0] addr);
        case (addr)
            5'd0:    rom = {OP_SET, 5'd31, 3'b000, 5'd1};  // set pins, 1 [31]
            5'd1:    rom = {OP_SET, 5'd31, 3'b000, 5'd0};  // set pins, 0 [31]
            5'd2:    rom = {OP_JMP, 5'd0,  3'b000, 5'd0};  // jmp 0
            default: rom = 16'hA042;                       // mov y,y  (a NOP)
        endcase
    endfunction

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------
    reg [4:0] pc;          // program counter
    reg [4:0] x, y;        // scratch registers
    reg [4:0] delay_cnt;   // remaining delay ticks

    // ------------------------------------------------------------------
    // Fetch + decode (purely combinational)
    // ------------------------------------------------------------------
    wire [15:0] instr  = rom(pc);
    wire [2:0]  opcode = instr[15:13];
    wire [4:0]  delay  = instr[12:8];
    wire [2:0]  arg1   = instr[7:5];
    wire [4:0]  arg2   = instr[4:0];

    reg take_jump;
    always @(*) begin
        case (arg1)
            3'b000:  take_jump = 1'b1;       // always
            3'b001:  take_jump = (x == 0);   // !X
            3'b010:  take_jump = (x != 0);   // X-- (test before decrement)
            3'b011:  take_jump = (y == 0);   // !Y
            3'b100:  take_jump = (y != 0);   // Y--
            default: take_jump = 1'b0;
        endcase
    end

    // ------------------------------------------------------------------
    // Execute (one instruction per tick, plus delay ticks)
    // ------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            pc        <= 5'd0;
            x         <= 5'd0;
            y         <= 5'd0;
            delay_cnt <= 5'd0;
            pins      <= 5'd0;
        end else if (tick) begin
            if (delay_cnt != 0) begin
                // Still burning delay cycles from the previous instruction
                delay_cnt <= delay_cnt - 1'b1;
            end else begin
                delay_cnt <= delay;                       // load this instr's delay
                pc <= (opcode == OP_JMP && take_jump) ? arg2 : pc + 1'b1;

                if (opcode == OP_JMP) begin
                    if (arg1 == 3'b010) x <= x - 1'b1;    // X-- always decrements
                    if (arg1 == 3'b100) y <= y - 1'b1;    // Y-- always decrements
                end

                if (opcode == OP_SET) begin
                    case (arg1)
                        3'b000:  pins <= arg2;
                        3'b001:  x    <= arg2;
                        3'b010:  y    <= arg2;
                        default: ;
                    endcase
                end
            end
        end
    end

endmodule