module mem_ctrl
  import base_pkg::*;
  import bus_pkg::*;
(
  input  logic     clk,
  input  logic     rst_n,
  input  bus_req_t req,
  output bus_rsp_t rsp
);
  localparam MEM_DEPTH = 256;
  word_t mem [0:MEM_DEPTH-1];

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rsp <= '0;
    end else begin
      rsp.ready <= req.valid;
      if (req.valid) begin
        if (req.we)
          mem[req.addr[9:2]] <= req.data;
        else
          rsp.data <= mem[req.addr[9:2]];
      end
    end
  end
endmodule
