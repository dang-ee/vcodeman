`include "defines.svh"
module alu import pkg_types::*; (
  input  logic  clk,
  input  byte_t a,
  input  byte_t b,
  output byte_t result
);
  `ifdef SIMULATION
    initial $display("alu: sim mode");
  `endif
  assign result = a + b;
endmodule
