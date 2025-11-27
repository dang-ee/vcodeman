# Mixed options test
-F nested_level1.f
-y /lib/search
-v /lib/cells.v
+incdir+includes+headers
+define+SIM_MODE+VERBOSE=1
+libext+.v+.sv
design.v
testbench.v
