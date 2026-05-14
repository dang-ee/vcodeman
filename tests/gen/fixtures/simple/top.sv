module top (
  input  logic       clk,
  input  logic [7:0] data_in,
  output logic [7:0] data_out
);
  core u_core (
    .clk(clk),
    .data_in(data_in),
    .data_out(data_out)
  );
endmodule
