`timescale 1 ns / 1 ps

// ====================================================================================
// Simple DAQ
// ====================================================================================
//
//  daq_control:
//      [31:16]     daq_threshold_reg - signed
//      [15:3]      daq_pretrigger_reg - unsigned
//      [0]         daq_enable
//	    [1]	        force_trigger  
//	    [2]	        channel_select -0 CH1, -1 CH2 
//
//  daq_status:
//      [31:1]      --- unused ---
//      [0]         daq_done_reg
//
//
//
//
//
// BRAM PORTA for writing
// ====================================================================================
// ====================================================================================

module axis_daq #
(
  parameter integer AXIS_TDATA_WIDTH = 32,
  parameter integer BRAM_DATA_WIDTH  = 16,
  parameter integer BRAM_ADDR_WIDTH  = 16
)
(
  // System signals
  input  wire                           aclk,
  input  wire                           aresetn,

  // DAQ status/control (AXI Slave)
  input  wire [31:0]                    daq_control,
  output wire [31:0]                    daq_status,

  // Data from ADC (AXI Stream Slave)
  output wire                           s_axis_tready,
  input  wire [AXIS_TDATA_WIDTH-1:0]    s_axis_tdata,
  input  wire                           s_axis_tvalid,

  // BRAM PORT A (captured data); write only
  output wire                           bram_porta_clk,
  output wire [BRAM_ADDR_WIDTH-1:0]     bram_porta_addr,
  output wire [BRAM_DATA_WIDTH-1:0]     bram_porta_wrdata,
  output wire                           bram_porta_we
);

// ====================================================================================
// ====================================================================================

  reg [3:0] st_reg, st_reg_next;            // main FSM

  localparam st_idle             = 4'b0000;
  localparam st_pretrigger       = 4'b0001;
  localparam st_wait_for_trigger = 4'b0010;
  localparam st_triggered        = 4'b0011;
  localparam st_done             = 4'b0100;

// ------------------------------------------------------------------------------------

  reg daq_done_reg;                             // DAQ status

  reg [BRAM_ADDR_WIDTH-1:0] bram_addr_reg;      // BRAM interface
  reg [BRAM_DATA_WIDTH-1:0] bram_data_reg;
  reg bram_wr_reg;

  reg signed [15:0] daq_threshold_reg;
  reg [BRAM_ADDR_WIDTH-2:0] daq_pretrigger_reg;
  reg [BRAM_ADDR_WIDTH-1:0] cnt_samples;


  reg daq_triggered_reg;
  reg daq_full_reg;
  reg rst_cnt_samples;
  reg en_cnt_samples;
  reg pretriger_done_reg;

//wire signed [15:0] s_axis_tdata_i;
  wire signed [15:0] s_axis_tdata_CH1_i;
  wire signed [15:0] s_axis_tdata_CH2_i;

  wire daq_enable;
  wire force_trigger;
  wire channel_select;

  



// ====================================================================================

  localparam C_CNT_SAMPLES_FULL = 16'hFFFF;
  localparam C_delimiter = 16'h7FFF;


// ====================================================================================
// ====================================================================================

  // module outputs
  assign daq_status         = { 31'd0 , daq_done_reg };
  assign s_axis_tready      = 1'b1;
  assign bram_porta_clk     = aclk;
  assign bram_porta_addr    = bram_addr_reg;
  assign bram_porta_wrdata  = bram_data_reg;
//assign bram_porta_wrdata  = { bram_data_reg[7:0] , bram_data_reg[15:8] };            // byte swap (big endien)
  
  
  assign bram_porta_we      = bram_wr_reg;

  // internal assignments
  assign daq_enable         = daq_control[0];
  assign force_trigger      = daq_control[1];
  assign channel_select     = daq_control[2];

  assign s_axis_tdata_CH1_i     = s_axis_tdata[15:0]; //CH1
  assign s_axis_tdata_CH2_i     = s_axis_tdata[31:16]; //CH2
  

// ====================================================================================

  // ----------------------------------------------------------------------------------
  // main FSM
  // ----------------------------------------------------------------------------------

  // state register
  always @(posedge aclk)
  begin
    if (~aresetn)               // synchronous reset
      st_reg <= st_idle;
    else
      st_reg <= st_reg_next;
  end

  // ----------------------------------------------------------------------------------

  // next state logic
  always @*
  begin
    // default assignments (latch prevention)
    st_reg_next <= st_reg;

    case(st_reg)
      // ARM must activate DAQ by writing '1' to daq_control[0]
      st_idle:              if(daq_enable == 1'b1)
                                st_reg_next <= st_pretrigger;

      // wait until pretrigger data are buffered
      st_pretrigger:        if(pretriger_done_reg == 1'b1)
                                st_reg_next <= st_wait_for_trigger;

      // wait for trigger event
      st_wait_for_trigger:  if(daq_triggered_reg == 1'b1)
                                st_reg_next <= st_triggered;

      // fill the whole buffer
      st_triggered:         if(daq_full_reg == 1'b1)
                                st_reg_next <= st_done;

      // wait until ARM reads data from BRAM (confirmed by writing '0' to daq_control[0])
      st_done:              if(daq_enable == 1'b0)
                                st_reg_next <= st_idle;
    endcase;
  end

  // ----------------------------------------------------------------------------------

  // output decoder (registered)
  always @(posedge aclk)
  begin
    if (~aresetn) begin
      rst_cnt_samples         <=  1'b0;
      en_cnt_samples          <=  1'b0;
      daq_done_reg            <=  1'b0;
      daq_threshold_reg       <= 16'b0;
      daq_pretrigger_reg      <= 13'b0;
    end

    else begin

      // default assignments
      rst_cnt_samples         <=  1'b0;
      en_cnt_samples          <=  1'b0;
      daq_done_reg            <=  1'b0;

      case(st_reg)
        st_idle:              begin
                                rst_cnt_samples <= 1'b1;
                                if (daq_enable == 1'b1)
                                  // latch trigger threshold value
                                  daq_threshold_reg  <= daq_control[31:16];
                                  daq_pretrigger_reg <= daq_control[15:3];
                              end

        st_pretrigger:        en_cnt_samples <= 1'b1;
                              
        st_wait_for_trigger:  en_cnt_samples <= 1'b0;

        st_triggered:         en_cnt_samples <= 1'b1;

        st_done:              begin
                                daq_done_reg <= 1'b1;
                                rst_cnt_samples <= 1'b1;
                              end

      endcase;
    end
  end



  // ----------------------------------------------------------------------------------
  // BRAM address generator
  // ----------------------------------------------------------------------------------

  always @(posedge aclk)
  begin
    if (~aresetn)
      bram_addr_reg <= 1'b0;
    else
      if (s_axis_tvalid == 1'b1)
        bram_addr_reg <= bram_addr_reg + 1;
  end



  // ----------------------------------------------------------------------------------
  // BRAM data write
  // ----------------------------------------------------------------------------------

  always @(posedge aclk)
  begin
    // default assignments
    bram_wr_reg             <=  1'b0;
    bram_data_reg           <= 32'b0;

    case(st_reg)
      st_idle:              bram_wr_reg <= 1'b0;

      st_pretrigger:        begin
                                if (s_axis_tvalid == 1'b1) begin
                                    bram_wr_reg <= 1'b1;
	                           end
			                   if (channel_select == 1'b1) begin
		                          bram_data_reg <= s_axis_tdata_CH2_i; //CH2
                                end
                                else begin
			                     bram_data_reg <= s_axis_tdata_CH1_i; //CH1
                                end
                            end

      st_wait_for_trigger:  begin
                                if (s_axis_tvalid == 1'b1) begin
                                    bram_wr_reg <= 1'b1;
                                end
                                if (channel_select == 1'b1) begin
			                        bram_data_reg <= s_axis_tdata_CH2_i; //CH2
                                end
                                else begin
			                        bram_data_reg <= s_axis_tdata_CH1_i; //CH1
			                    end
			                end

      st_triggered:         begin
                                if (s_axis_tvalid == 1'b1) begin
                                    if (daq_full_reg == 1'b1) begin
                                        bram_wr_reg <= 1'b1;
                                        bram_data_reg <= C_delimiter;   // mark last position in the buffer
                                    end
                                    else begin
                                        bram_wr_reg <= 1'b1;
                                    end
                                    if (channel_select == 1'b1) begin
			      	                    bram_data_reg <= s_axis_tdata_CH2_i; //CH2
			      	                end
                                 end
                                 else begin
			                         bram_data_reg <= s_axis_tdata_CH1_i; //CH1
                                 end
                              end

      st_done:              bram_wr_reg <= 1'b0;

    endcase
  end


  // ----------------------------------------------------------------------------------
  // trigger comparator
  // ----------------------------------------------------------------------------------


  always @(posedge aclk)	
  begin
    if (~aresetn)
      daq_triggered_reg      <= 1'b0;
    else
      daq_triggered_reg      <= 1'b0;

      if (s_axis_tvalid == 1'b1)
        
         if (channel_select == 1'b1) begin
            if(s_axis_tdata_CH2_i >= daq_threshold_reg || (force_trigger == 1)) //CH2
	        daq_triggered_reg  <= 1'b1;
            end else begin
            if(s_axis_tdata_CH1_i >= daq_threshold_reg || (force_trigger == 1)) //CH1
	        daq_triggered_reg  <= 1'b1;
	     end	    
  end



  // ----------------------------------------------------------------------------------
  // sample counter, pretrigger, buffer full
  // ----------------------------------------------------------------------------------

  always @(posedge aclk)
  begin
    if (~aresetn) begin               // synchronous reset
      cnt_samples        <= 1'b0;
      pretriger_done_reg <= 1'b0;
      daq_full_reg       <= 1'b0;
    end
    else begin

      // Default assignment
      pretriger_done_reg <= 1'b0;
      daq_full_reg       <= 1'b0;


      // pretrigger buffer level reached
      if (cnt_samples == daq_pretrigger_reg)
        pretriger_done_reg <= 1'b1;


      // counter reset
      if (rst_cnt_samples == 1'b1)
        cnt_samples <= 0;
      else
        if (en_cnt_samples == 1'b1)
          cnt_samples <= cnt_samples + 1;

      // full buffer
      if (cnt_samples == C_CNT_SAMPLES_FULL)
        daq_full_reg <= 1'b1;

    end
  end


// ====================================================================================
endmodule
// ====================================================================================
