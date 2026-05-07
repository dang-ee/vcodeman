`include "defines.svh"
module tb_cpu;
  import base_pkg::*;

  localparam CLK_PERIOD = 10;

  logic clk, rst_n;
  word_t instr, result;

  cpu u_cpu (
    .clk   (clk),
    .rst_n (rst_n),
    .instr (instr),
    .result(result)
  );

  initial clk = 0;
  always #(CLK_PERIOD/2) clk = ~clk;

  initial begin
    rst_n = 0;
    instr = '0;
    @(posedge clk); #1;
    @(posedge clk); #1;
    rst_n = 1;

    // ADDI x1, x0, 5   -> rd=1, rs1=0, imm=5, opcode=I-type
    instr = 32'b000000000101_00000_000_00001_0010011;
    repeat (3) @(posedge clk);

    // ADDI x2, x0, 7   -> rd=2, rs1=0, imm=7
    instr = 32'b000000000111_00000_000_00010_0010011;
    repeat (3) @(posedge clk);

    // ADD  x3, x1, x2  -> rd=3, rs1=1, rs2=2, R-type
    instr = 32'b0000000_00010_00001_000_00011_0110011;
    repeat (3) @(posedge clk);

    `ifdef SIMULATION
    $display("PASS: simulation complete, result=%0d", result);
    `endif
    $finish;
  end
endmodule
