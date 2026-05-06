module core (
  input  logic       clk,
  input  logic [7:0] data_in,
  output logic [7:0] data_out
);
  alu u_alu (
    .clk(clk),
    .a(data_in),
    .b(8'h00),
    .result(data_out)
  );
endmodule
