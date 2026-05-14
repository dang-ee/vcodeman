`include "defines.svh"
module alu
  import base_pkg::*;
  import alu_pkg::*;
(
  input  alu_op_t op,
  input  word_t   a,
  input  word_t   b,
  output word_t   result,
  output logic    zero
);
  always_comb begin
    case (op)
      ALU_ADD: result = a + b;
      ALU_SUB: result = a - b;
      ALU_AND: result = a & b;
      ALU_OR:  result = a | b;
      ALU_XOR: result = a ^ b;
      ALU_SLL: result = a << b[4:0];
      ALU_SRL: result = a >> b[4:0];
      ALU_SLT: result = {{31{1'b0}}, ($signed(a) < $signed(b))};
      default: result = '0;
    endcase
    zero = (result == '0);
  end

  `ifdef SIMULATION
  initial $display("[alu] instantiated");
  `endif
endmodule
