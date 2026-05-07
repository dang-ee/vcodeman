package bus_pkg;
  import base_pkg::*;
  typedef struct packed {
    word_t addr;
    word_t data;
    logic  we;
    logic  valid;
  } bus_req_t;
  typedef struct packed {
    word_t data;
    logic  ready;
  } bus_rsp_t;
endpackage
