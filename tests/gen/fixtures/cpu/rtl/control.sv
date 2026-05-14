module control
  import base_pkg::*;
  import alu_pkg::*;
  import bus_pkg::*;
(
  input  word_t    instr,
  output alu_op_t  alu_op,
  output logic     use_imm,
  output word_t    imm,
  output logic     rd_we,
  output bus_req_t mem_req
);
  logic [6:0] opcode;
  logic [2:0] funct3;
  logic [6:0] funct7;

  assign opcode = instr[6:0];
  assign funct3 = instr[14:12];
  assign funct7 = instr[31:25];

  always_comb begin
    alu_op  = ALU_ADD;
    use_imm = 1'b0;
    imm     = '0;
    rd_we   = 1'b0;
    mem_req = '0;

    case (opcode)
      7'b0110011: begin // R-type
        rd_we = 1'b1;
        case ({funct7[5], funct3})
          4'b0_000: alu_op = ALU_ADD;
          4'b1_000: alu_op = ALU_SUB;
          4'b0_111: alu_op = ALU_AND;
          4'b0_110: alu_op = ALU_OR;
          4'b0_100: alu_op = ALU_XOR;
          4'b0_001: alu_op = ALU_SLL;
          4'b0_101: alu_op = ALU_SRL;
          4'b0_010: alu_op = ALU_SLT;
          default:  alu_op = ALU_ADD;
        endcase
      end
      7'b0010011: begin // I-type ALU
        use_imm = 1'b1;
        rd_we   = 1'b1;
        imm     = {{20{instr[31]}}, instr[31:20]};
        case (funct3)
          3'b000: alu_op = ALU_ADD;
          3'b111: alu_op = ALU_AND;
          3'b110: alu_op = ALU_OR;
          3'b100: alu_op = ALU_XOR;
          3'b010: alu_op = ALU_SLT;
          default: alu_op = ALU_ADD;
        endcase
      end
      7'b0100011: begin // S-type (store)
        use_imm  = 1'b1;
        imm      = {{20{instr[31]}}, instr[31:25], instr[11:7]};
        mem_req.we    = 1'b1;
        mem_req.valid = 1'b1;
      end
      default:;
    endcase
  end
endmodule
