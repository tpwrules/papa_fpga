
module hps_dummy ();

endmodule

//=======================================================
//  This code is generated by Terasic System Builder
//=======================================================

module de10_nano_nixos_led(

	//////////// ADC //////////
	output		          		ADC_CONVST,
	output		          		ADC_SCK,
	output		          		ADC_SDI,
	input 		          		ADC_SDO,

	//////////// ARDUINO //////////
	inout 		    [15:0]		ARDUINO_IO,
	inout 		          		ARDUINO_RESET_N,

	//////////// CLOCK //////////
	input 		          		FPGA_CLK1_50,
	input 		          		FPGA_CLK2_50,
	input 		          		FPGA_CLK3_50,

	//////////// HDMI //////////
	inout 		          		HDMI_I2C_SCL,
	inout 		          		HDMI_I2C_SDA,
	inout 		          		HDMI_I2S,
	inout 		          		HDMI_LRCLK,
	inout 		          		HDMI_MCLK,
	inout 		          		HDMI_SCLK,
	output		          		HDMI_TX_CLK,
	output		          		HDMI_TX_DE,
	output		    [23:0]		HDMI_TX_D,
	output		          		HDMI_TX_HS,
	input 		          		HDMI_TX_INT,
	output		          		HDMI_TX_VS,

	//////////// KEY //////////
	input 		     [1:0]		KEY,

	//////////// LED //////////
	output		     [7:0]		LED,

	//////////// SW //////////
	input 		     [3:0]		SW,

	//////////// GPIO_0, GPIO connect to GPIO Default //////////
	inout 		    [35:0]		GPIO_0,

	//////////// GPIO_1, GPIO connect to GPIO Default //////////
	inout 		    [35:0]		GPIO_1
);



//=======================================================
//  REG/WIRE declarations
//=======================================================
wire hps_fpga_reset_n;
wire                fpga_clk_50;
// connection of internal logics
assign fpga_clk_50 = FPGA_CLK1_50;

wire [7:0]  f2h_axi_s0_awid                       ;//                     f2h_axi_s0.awid
wire [31:0] f2h_axi_s0_awaddr                     ;//                               .awaddr
wire [3:0]  f2h_axi_s0_awlen                      ;//                               .awlen
wire [2:0]  f2h_axi_s0_awsize                     ;//                               .awsize
wire [1:0]  f2h_axi_s0_awburst                    ;//                               .awburst
wire [1:0]  f2h_axi_s0_awlock                     ;//                               .awlock
wire [3:0]  f2h_axi_s0_awcache                    ;//                               .awcache
wire [2:0]  f2h_axi_s0_awprot                     ;//                               .awprot
wire        f2h_axi_s0_awvalid                    ;//                               .awvalid
wire        f2h_axi_s0_awready                    ;//                               .awready
wire [4:0]  f2h_axi_s0_awuser                     ;//                               .awuser
wire [7:0]  f2h_axi_s0_wid                        ;//                               .wid
wire [31:0] f2h_axi_s0_wdata                      ;//                               .wdata
wire [3:0]  f2h_axi_s0_wstrb                      ;//                               .wstrb
wire        f2h_axi_s0_wlast                      ;//                               .wlast
wire        f2h_axi_s0_wvalid                     ;//                               .wvalid
wire        f2h_axi_s0_wready                     ;//                               .wready
wire [7:0]  f2h_axi_s0_bid                        ;//                               .bid
wire [1:0]  f2h_axi_s0_bresp                      ;//                               .bresp
wire        f2h_axi_s0_bvalid                     ;//                               .bvalid
wire        f2h_axi_s0_bready                     ;//                               .bready
wire [7:0]  f2h_axi_s0_arid                       ;//                               .arid
wire [31:0] f2h_axi_s0_araddr                     ;//                               .araddr
wire [3:0]  f2h_axi_s0_arlen                      ;//                               .arlen
wire [2:0]  f2h_axi_s0_arsize                     ;//                               .arsize
wire [1:0]  f2h_axi_s0_arburst                    ;//                               .arburst
wire [1:0]  f2h_axi_s0_arlock                     ;//                               .arlock
wire [3:0]  f2h_axi_s0_arcache                    ;//                               .arcache
wire [2:0]  f2h_axi_s0_arprot                     ;//                               .arprot
wire        f2h_axi_s0_arvalid                    ;//                               .arvalid
wire        f2h_axi_s0_arready                    ;//                               .arready
wire [4:0]  f2h_axi_s0_aruser                     ;//                               .aruser
wire [7:0]  f2h_axi_s0_rid                        ;//                               .rid
wire [31:0] f2h_axi_s0_rdata                      ;//                               .rdata
wire [1:0]  f2h_axi_s0_rresp                      ;//                               .rresp
wire        f2h_axi_s0_rlast                      ;//                               .rlast
wire        f2h_axi_s0_rvalid                     ;//                               .rvalid
wire        f2h_axi_s0_rready                     ;//                               .rready

wire [11:0] h2f_lw_awid                           ;//            h2f_lw.awid
wire [20:0] h2f_lw_awaddr                         ;//                  .awaddr
wire [3:0]  h2f_lw_awlen                          ;//                  .awlen
wire [2:0]  h2f_lw_awsize                         ;//                  .awsize
wire [1:0]  h2f_lw_awburst                        ;//                  .awburst
wire [1:0]  h2f_lw_awlock                         ;//                  .awlock
wire [3:0]  h2f_lw_awcache                        ;//                  .awcache
wire [2:0]  h2f_lw_awprot                         ;//                  .awprot
wire        h2f_lw_awvalid                        ;//                  .awvalid
wire        h2f_lw_awready                        ;//                  .awready
wire [11:0] h2f_lw_wid                            ;//                  .wid
wire [31:0] h2f_lw_wdata                          ;//                  .wdata
wire [3:0]  h2f_lw_wstrb                          ;//                  .wstrb
wire        h2f_lw_wlast                          ;//                  .wlast
wire        h2f_lw_wvalid                         ;//                  .wvalid
wire        h2f_lw_wready                         ;//                  .wready
wire [11:0] h2f_lw_bid                            ;//                  .bid
wire [1:0]  h2f_lw_bresp                          ;//                  .bresp
wire        h2f_lw_bvalid                         ;//                  .bvalid
wire        h2f_lw_bready                         ;//                  .bready
wire [11:0] h2f_lw_arid                           ;//                  .arid
wire [20:0] h2f_lw_araddr                         ;//                  .araddr
wire [3:0]  h2f_lw_arlen                          ;//                  .arlen
wire [2:0]  h2f_lw_arsize                         ;//                  .arsize
wire [1:0]  h2f_lw_arburst                        ;//                  .arburst
wire [1:0]  h2f_lw_arlock                         ;//                  .arlock
wire [3:0]  h2f_lw_arcache                        ;//                  .arcache
wire [2:0]  h2f_lw_arprot                         ;//                  .arprot
wire        h2f_lw_arvalid                        ;//                  .arvalid
wire        h2f_lw_arready                        ;//                  .arready
wire [11:0] h2f_lw_rid                            ;//                  .rid
wire [31:0] h2f_lw_rdata                          ;//                  .rdata
wire [1:0]  h2f_lw_rresp                          ;//                  .rresp
wire        h2f_lw_rlast                          ;//                  .rlast
wire        h2f_lw_rvalid                         ;//                  .rvalid
wire        h2f_lw_rready                         ;//                  .rready

hps_dummy hps_dummy();

// not sure if mandatory
cyclonev_hps_interface_clocks_resets clocks_resets(
 .f2h_pending_rst_ack({
    1'b1 // 0:0
  })
,.f2h_warm_rst_req_n({
    1'b1 // 0:0
  })
,.f2h_dbg_rst_req_n({
    1'b1 // 0:0
  })
,.h2f_rst_n({
    hps_fpga_reset_n // 0:0
  })
,.f2h_cold_rst_req_n({
    1'b1 // 0:0
  })
);

// not sure if mandatory
cyclonev_hps_interface_dbg_apb debug_apb(
 .DBG_APB_DISABLE({
    1'b0 // 0:0
  })
,.P_CLK_EN({
    1'b0 // 0:0
  })
);

// not sure if mandatory
cyclonev_hps_interface_tpiu_trace tpiu(
 .traceclk_ctl({
    1'b1 // 0:0
  })
);

// not sure if mandatory
cyclonev_hps_interface_boot_from_fpga boot_from_fpga(
 .boot_from_fpga_ready({
    1'b0 // 0:0
  })
,.boot_from_fpga_on_failure({
    1'b0 // 0:0
  })
,.bsel_en({
    1'b0 // 0:0
  })
,.csel_en({
    1'b0 // 0:0
  })
,.csel({
    2'b01 // 1:0
  })
,.bsel({
    3'b001 // 2:0
  })
);

// FPGA to HPS interface
cyclonev_hps_interface_fpga2hps fpga2hps(
    .port_size_config(2'd0), // 0 == 32 bits, 3 == disabled?
    .clk(FPGA_CLK1_50),
    .awid(f2h_axi_s0_awid),
    .awaddr(f2h_axi_s0_awaddr),
    .awlen(f2h_axi_s0_awlen),
    .awsize(f2h_axi_s0_awsize),
    .awburst(f2h_axi_s0_awburst),
    .awlock(f2h_axi_s0_awlock),
    .awcache(f2h_axi_s0_awcache),
    .awprot(f2h_axi_s0_awprot),
    .awvalid(f2h_axi_s0_awvalid),
    .awready(f2h_axi_s0_awready),
    .awuser(f2h_axi_s0_awuser),
    .wid(f2h_axi_s0_wid),
    .wdata(f2h_axi_s0_wdata),
    .wstrb(f2h_axi_s0_wstrb),
    .wlast(f2h_axi_s0_wlast),
    .wvalid(f2h_axi_s0_wvalid),
    .wready(f2h_axi_s0_wready),
    .bid(f2h_axi_s0_bid),
    .bresp(f2h_axi_s0_bresp),
    .bvalid(f2h_axi_s0_bvalid),
    .bready(f2h_axi_s0_bready),
    .arid(f2h_axi_s0_arid),
    .araddr(f2h_axi_s0_araddr),
    .arlen(f2h_axi_s0_arlen),
    .arsize(f2h_axi_s0_arsize),
    .arburst(f2h_axi_s0_arburst),
    .arlock(f2h_axi_s0_arlock),
    .arcache(f2h_axi_s0_arcache),
    .arprot(f2h_axi_s0_arprot),
    .arvalid(f2h_axi_s0_arvalid),
    .arready(f2h_axi_s0_arready),
    .aruser(f2h_axi_s0_aruser),
    .rid(f2h_axi_s0_rid),
    .rdata(f2h_axi_s0_rdata),
    .rresp(f2h_axi_s0_rresp),
    .rlast(f2h_axi_s0_rlast),
    .rvalid(f2h_axi_s0_rvalid),
    .rready(f2h_axi_s0_rready),
);

// lightweight HPS to FPGA interface, not mandatory
cyclonev_hps_interface_hps2fpga_light_weight hps2fpga_light_weight(
    .clk(FPGA_CLK1_50),
    .awid(h2f_lw_awid),
    .awaddr(h2f_lw_awaddr),
    .awlen(h2f_lw_awlen),
    .awsize(h2f_lw_awsize),
    .awburst(h2f_lw_awburst),
    .awlock(h2f_lw_awlock),
    .awcache(h2f_lw_awcache),
    .awprot(h2f_lw_awprot),
    .awvalid(h2f_lw_awvalid),
    .awready(h2f_lw_awready),
    .wid(h2f_lw_wid),
    .wdata(h2f_lw_wdata),
    .wstrb(h2f_lw_wstrb),
    .wlast(h2f_lw_wlast),
    .wvalid(h2f_lw_wvalid),
    .wready(h2f_lw_wready),
    .bid(h2f_lw_bid),
    .bresp(h2f_lw_bresp),
    .bvalid(h2f_lw_bvalid),
    .bready(h2f_lw_bready),
    .arid(h2f_lw_arid),
    .araddr(h2f_lw_araddr),
    .arlen(h2f_lw_arlen),
    .arsize(h2f_lw_arsize),
    .arburst(h2f_lw_arburst),
    .arlock(h2f_lw_arlock),
    .arcache(h2f_lw_arcache),
    .arprot(h2f_lw_arprot),
    .arvalid(h2f_lw_arvalid),
    .arready(h2f_lw_arready),
    .rid(h2f_lw_rid),
    .rdata(h2f_lw_rdata),
    .rresp(h2f_lw_rresp),
    .rlast(h2f_lw_rlast),
    .rvalid(h2f_lw_rvalid),
    .rready(h2f_lw_rready),
);

// not sure if mandatory
cyclonev_hps_interface_hps2fpga hps2fpga(
 .port_size_config({
    2'b11 // 1:0, 3 == disabled?
  })
);

// not sure if mandatory
cyclonev_hps_interface_fpga2sdram f2sdram(
 .cfg_cport_rfifo_map({
    18'b000000000000000000 // 17:0
  })
,.cfg_axi_mm_select({
    6'b000000 // 5:0
  })
,.cfg_wfifo_cport_map({
    16'b0000000000000000 // 15:0
  })
,.cfg_cport_type({
    12'b000000000000 // 11:0
  })
,.cfg_rfifo_cport_map({
    16'b0000000000000000 // 15:0
  })
,.cfg_port_width({
    12'b000000000000 // 11:0
  })
,.cfg_cport_wfifo_map({
    18'b000000000000000000 // 17:0
  })
);

//=======================================================
//  Structural coding
//=======================================================
wire blink;
wire [2:0] status;
amaranth_top amaranth_top(
    .clk50(fpga_clk_50),
    .rst(~hps_fpga_reset_n),
    .blink(blink),
    .status(status),
    .button(KEY[0]),
    .GPIO_0_OUT(GPIO_0[35:34]),
    .GPIO_0_IN(GPIO_0[33:0]),
    .GPIO_1_OUT(GPIO_1[35:34]),
    .GPIO_1_IN(GPIO_1[33:0]),

    .f2h_axi_s0_awid(f2h_axi_s0_awid),
    .f2h_axi_s0_awaddr(f2h_axi_s0_awaddr),
    .f2h_axi_s0_awlen(f2h_axi_s0_awlen),
    .f2h_axi_s0_awsize(f2h_axi_s0_awsize),
    .f2h_axi_s0_awburst(f2h_axi_s0_awburst),
    .f2h_axi_s0_awlock(f2h_axi_s0_awlock),
    .f2h_axi_s0_awcache(f2h_axi_s0_awcache),
    .f2h_axi_s0_awprot(f2h_axi_s0_awprot),
    .f2h_axi_s0_awvalid(f2h_axi_s0_awvalid),
    .f2h_axi_s0_awready(f2h_axi_s0_awready),
    .f2h_axi_s0_awuser(f2h_axi_s0_awuser),
    .f2h_axi_s0_wid(f2h_axi_s0_wid),
    .f2h_axi_s0_wdata(f2h_axi_s0_wdata),
    .f2h_axi_s0_wstrb(f2h_axi_s0_wstrb),
    .f2h_axi_s0_wlast(f2h_axi_s0_wlast),
    .f2h_axi_s0_wvalid(f2h_axi_s0_wvalid),
    .f2h_axi_s0_wready(f2h_axi_s0_wready),
    .f2h_axi_s0_bid(f2h_axi_s0_bid),
    .f2h_axi_s0_bresp(f2h_axi_s0_bresp),
    .f2h_axi_s0_bvalid(f2h_axi_s0_bvalid),
    .f2h_axi_s0_bready(f2h_axi_s0_bready),
    .f2h_axi_s0_arid(f2h_axi_s0_arid),
    .f2h_axi_s0_araddr(f2h_axi_s0_araddr),
    .f2h_axi_s0_arlen(f2h_axi_s0_arlen),
    .f2h_axi_s0_arsize(f2h_axi_s0_arsize),
    .f2h_axi_s0_arburst(f2h_axi_s0_arburst),
    .f2h_axi_s0_arlock(f2h_axi_s0_arlock),
    .f2h_axi_s0_arcache(f2h_axi_s0_arcache),
    .f2h_axi_s0_arprot(f2h_axi_s0_arprot),
    .f2h_axi_s0_arvalid(f2h_axi_s0_arvalid),
    .f2h_axi_s0_arready(f2h_axi_s0_arready),
    .f2h_axi_s0_aruser(f2h_axi_s0_aruser),
    .f2h_axi_s0_rid(f2h_axi_s0_rid),
    .f2h_axi_s0_rdata(f2h_axi_s0_rdata),
    .f2h_axi_s0_rresp(f2h_axi_s0_rresp),
    .f2h_axi_s0_rlast(f2h_axi_s0_rlast),
    .f2h_axi_s0_rvalid(f2h_axi_s0_rvalid),
    .f2h_axi_s0_rready(f2h_axi_s0_rready),

    .h2f_lw_awid(h2f_lw_awid),
    .h2f_lw_awaddr(h2f_lw_awaddr),
    .h2f_lw_awlen(h2f_lw_awlen),
    .h2f_lw_awsize(h2f_lw_awsize),
    .h2f_lw_awburst(h2f_lw_awburst),
    .h2f_lw_awlock(h2f_lw_awlock),
    .h2f_lw_awcache(h2f_lw_awcache),
    .h2f_lw_awprot(h2f_lw_awprot),
    .h2f_lw_awvalid(h2f_lw_awvalid),
    .h2f_lw_awready(h2f_lw_awready),
    .h2f_lw_wid(h2f_lw_wid),
    .h2f_lw_wdata(h2f_lw_wdata),
    .h2f_lw_wstrb(h2f_lw_wstrb),
    .h2f_lw_wlast(h2f_lw_wlast),
    .h2f_lw_wvalid(h2f_lw_wvalid),
    .h2f_lw_wready(h2f_lw_wready),
    .h2f_lw_bid(h2f_lw_bid),
    .h2f_lw_bresp(h2f_lw_bresp),
    .h2f_lw_bvalid(h2f_lw_bvalid),
    .h2f_lw_bready(h2f_lw_bready),
    .h2f_lw_arid(h2f_lw_arid),
    .h2f_lw_araddr(h2f_lw_araddr),
    .h2f_lw_arlen(h2f_lw_arlen),
    .h2f_lw_arsize(h2f_lw_arsize),
    .h2f_lw_arburst(h2f_lw_arburst),
    .h2f_lw_arlock(h2f_lw_arlock),
    .h2f_lw_arcache(h2f_lw_arcache),
    .h2f_lw_arprot(h2f_lw_arprot),
    .h2f_lw_arvalid(h2f_lw_arvalid),
    .h2f_lw_arready(h2f_lw_arready),
    .h2f_lw_rid(h2f_lw_rid),
    .h2f_lw_rdata(h2f_lw_rdata),
    .h2f_lw_rresp(h2f_lw_rresp),
    .h2f_lw_rlast(h2f_lw_rlast),
    .h2f_lw_rvalid(h2f_lw_rvalid),
    .h2f_lw_rready(h2f_lw_rready),
);

assign LED[0] = blink;
assign LED[3:1] = status;

endmodule
