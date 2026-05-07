module regfile
  import base_pkg::*;
(
  input  logic      clk,
  input  logic      rst_n,
  input  reg_addr_t rs1_addr,
  input  reg_addr_t rs2_addr,
  output word_t     rs1_data,
  output word_t     rs2_data,
  input  reg_addr_t rd_addr,
  input  word_t     rd_data,
  input  logic      rd_we
);
  word_t regs [0:NUM_REGS-1];
  integer i;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (i = 0; i < NUM_REGS; i = i + 1)
        regs[i] <= '0;
    end else if (rd_we && rd_addr != '0) begin
      regs[rd_addr] <= rd_data;
    end
  end

  assign rs1_data = (rs1_addr == '0) ? '0 : regs[rs1_addr];
  assign rs2_data = (rs2_addr == '0) ? '0 : regs[rs2_addr];
endmodule
