module datapath
  import base_pkg::*;
  import alu_pkg::*;
(
  input  logic      clk,
  input  logic      rst_n,
  input  alu_op_t   alu_op,
  input  reg_addr_t rs1_addr,
  input  reg_addr_t rs2_addr,
  input  reg_addr_t rd_addr,
  input  word_t     imm,
  input  logic      use_imm,
  input  logic      rd_we,
  output word_t     alu_result,
  output logic      alu_zero
);
  word_t rs1_data, rs2_data, alu_b;

  regfile u_regfile (
    .clk     (clk),
    .rst_n   (rst_n),
    .rs1_addr(rs1_addr),
    .rs2_addr(rs2_addr),
    .rs1_data(rs1_data),
    .rs2_data(rs2_data),
    .rd_addr (rd_addr),
    .rd_data (alu_result),
    .rd_we   (rd_we)
  );

  assign alu_b = use_imm ? imm : rs2_data;

  alu u_alu (
    .op    (alu_op),
    .a     (rs1_data),
    .b     (alu_b),
    .result(alu_result),
    .zero  (alu_zero)
  );
endmodule
