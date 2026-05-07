module cpu
  import base_pkg::*;
  import alu_pkg::*;
  import bus_pkg::*;
(
  input  logic  clk,
  input  logic  rst_n,
  input  word_t instr,
  output word_t result
);
  alu_op_t  alu_op;
  logic     use_imm, rd_we, alu_zero;
  word_t    imm, alu_result;
  bus_req_t mem_req;
  bus_rsp_t mem_rsp;

  reg_addr_t rs1_addr, rs2_addr, rd_addr;
  assign rs1_addr = instr[19:15];
  assign rs2_addr = instr[24:20];
  assign rd_addr  = instr[11:7];

  control u_control (
    .instr  (instr),
    .alu_op (alu_op),
    .use_imm(use_imm),
    .imm    (imm),
    .rd_we  (rd_we),
    .mem_req(mem_req)
  );

  datapath u_datapath (
    .clk       (clk),
    .rst_n     (rst_n),
    .alu_op    (alu_op),
    .rs1_addr  (rs1_addr),
    .rs2_addr  (rs2_addr),
    .rd_addr   (rd_addr),
    .imm       (imm),
    .use_imm   (use_imm),
    .rd_we     (rd_we),
    .alu_result(alu_result),
    .alu_zero  (alu_zero)
  );

  mem_ctrl u_mem_ctrl (
    .clk  (clk),
    .rst_n(rst_n),
    .req  (mem_req),
    .rsp  (mem_rsp)
  );

  assign result = alu_result;
endmodule
