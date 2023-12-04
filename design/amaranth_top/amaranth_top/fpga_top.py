from amaranth import *
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.cdc import ResetSynchronizer

from .top import Top
from .constants import MIC_FREQ_HZ, NUM_MICS
from .mic import MicCapture
from .convolve import Convolver
from .cyclone_v_pll import IntelPLL

class FPGATop(Component):
    clk50:      In(1)
    rst:        In(1)

    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    GPIO_0_OUT: Out(2)
    GPIO_0_IN:  In(34)
    GPIO_1_OUT: Out(2)
    GPIO_1_IN:  In(34)

    # copy-pasta from verilog
    f2h_axi_s0_awid: Out(8)
    f2h_axi_s0_awaddr: Out(32)
    f2h_axi_s0_awlen: Out(4)
    f2h_axi_s0_awsize: Out(3)
    f2h_axi_s0_awburst: Out(2)
    f2h_axi_s0_awlock: Out(2)
    f2h_axi_s0_awcache: Out(4)
    f2h_axi_s0_awprot: Out(3)
    f2h_axi_s0_awvalid: Out(1)
    f2h_axi_s0_awready: In(1)
    f2h_axi_s0_awuser: Out(5)
    f2h_axi_s0_wid: Out(8)
    f2h_axi_s0_wdata: Out(32)
    f2h_axi_s0_wstrb: Out(4)
    f2h_axi_s0_wlast: Out(1)
    f2h_axi_s0_wvalid: Out(1)
    f2h_axi_s0_wready: In(1)
    f2h_axi_s0_bid: In(8)
    f2h_axi_s0_bresp: In(2)
    f2h_axi_s0_bvalid: In(1)
    f2h_axi_s0_bready: Out(1)
    f2h_axi_s0_arid: Out(8)
    f2h_axi_s0_araddr: Out(32)
    f2h_axi_s0_arlen: Out(4)
    f2h_axi_s0_arsize: Out(3)
    f2h_axi_s0_arburst: Out(2)
    f2h_axi_s0_arlock: Out(2)
    f2h_axi_s0_arcache: Out(4)
    f2h_axi_s0_arprot: Out(3)
    f2h_axi_s0_arvalid: Out(1)
    f2h_axi_s0_arready: In(1)
    f2h_axi_s0_aruser: Out(5)
    f2h_axi_s0_rid: In(8)
    f2h_axi_s0_rdata: In(32)
    f2h_axi_s0_rresp: In(2)
    f2h_axi_s0_rlast: In(1)
    f2h_axi_s0_rvalid: In(1)
    f2h_axi_s0_rready: Out(1)

    mm_bridge_fpga_m0_waitrequest: Out(1)
    mm_bridge_fpga_m0_readdata: Out(32)
    mm_bridge_fpga_m0_readdatavalid: Out(1)
    mm_bridge_fpga_m0_burstcount: In(1)
    mm_bridge_fpga_m0_writedata: In(32)
    mm_bridge_fpga_m0_address: In(10)
    mm_bridge_fpga_m0_write: In(1)
    mm_bridge_fpga_m0_read: In(1)
    mm_bridge_fpga_m0_byteenable: In(4)
    mm_bridge_fpga_m0_debugaccess: In(1)

    def elaborate(self, platform):
        m = Module()

        # wire up main clock domain and PLL. note that all PLL outputs are
        # marked as asynchronous w.r.t. its inputs and each other in the .sdc
        m.domains.sync = sync = ClockDomain()
        m.d.comb += sync.clk.eq(self.clk50)
        m.submodules.main_pll = main_pll = IntelPLL("50 MHz")

        # hook up another PLL for the convolver so the ratios work out
        m.submodules.conv_pll = conv_pll = IntelPLL("50 MHz")

        # hold whole design in reset until PLL is locked
        reset = Signal()
        m.d.comb += reset.eq(self.rst & main_pll.o_locked & conv_pll.o_locked)
        m.submodules += ResetSynchronizer(reset)

        # set up mic capture domain
        mic_capture_freq = MIC_FREQ_HZ * MicCapture.REL_FREQ
        m.domains.mic_capture = mic_capture = ClockDomain()
        m.d.comb += mic_capture.clk.eq(
            main_pll.add_output(f"{mic_capture_freq} Hz"))
        m.submodules += ResetSynchronizer(reset, domain="mic_capture")

        # set up the convolver domain
        convolver_freq = MIC_FREQ_HZ * Convolver.REL_FREQ
        # round up to the next multiple of 1MHz so the PLL ratios will be
        # realizable and Quartus won't explode
        convolver_freq = ((convolver_freq//1e6)+1)*1e6
        m.domains.convolver = convolver = ClockDomain()
        m.d.comb += convolver.clk.eq(
            conv_pll.add_output(f"{convolver_freq} Hz"))
        m.submodules += ResetSynchronizer(reset, domain="convolver")

        # wire up top module
        m.submodules.top = top = Top()
        m.d.comb += [
            top.button_raw.eq(self.button),
            self.blink.eq(top.blink),
            self.status.eq(top.status_leds),
        ]

        # wire up microphone data bus
        m.d.comb += [
            self.GPIO_0_OUT[1].eq(top.mic_sck),
            self.GPIO_0_OUT[0].eq(top.mic_ws),
            self.GPIO_1_OUT[1].eq(top.mic_sck),
            self.GPIO_1_OUT[0].eq(top.mic_ws),
        ]
        for mpi in range(0, NUM_MICS//2, 2):
            m.d.comb += top.mic_data_raw[mpi].eq(self.GPIO_0_IN[33-(mpi//2)])
            if mpi+1 < len(top.mic_data_raw):
                m.d.comb += top.mic_data_raw[mpi+1].eq(
                    self.GPIO_1_IN[33-(mpi//2)])

        # hook up audio RAM bus to AXI port
        m.d.comb += [
            self.f2h_axi_s0_awid.eq(0), # always write with id 0
            self.f2h_axi_s0_awlen.eq(top.audio_ram.length),
            self.f2h_axi_s0_awsize.eq(0b001), # two bytes at a time
            self.f2h_axi_s0_awburst.eq(0b01), # burst mode: increment
            # heard vague rumors that these should just all be 1 to activate
            # caching as expected...
            self.f2h_axi_s0_awcache.eq(0b1111),
            # and 5 1 bits for the user data too (though that is from the
            # handbook)...
            self.f2h_axi_s0_awuser.eq(0b11111),
            self.f2h_axi_s0_awvalid.eq(top.audio_ram.addr_valid),
            top.audio_ram.addr_ready.eq(self.f2h_axi_s0_awready),

            self.f2h_axi_s0_wdata.eq( # route 16 bit data to both 32 bit halves
                Cat(top.audio_ram.data, top.audio_ram.data)),
            self.f2h_axi_s0_wvalid.eq(top.audio_ram.data_valid),
            self.f2h_axi_s0_wlast.eq(top.audio_ram.data_last),
            top.audio_ram.data_ready.eq(self.f2h_axi_s0_wready),

            self.f2h_axi_s0_bready.eq(self.f2h_axi_s0_bvalid),
            top.audio_ram.txn_done.eq(self.f2h_axi_s0_bvalid),
        ]

        # transform 16 bit audio bus into 32 bit AXI bus
        # remove bottom two address bits to stay 32 bit aligned
        m.d.comb += self.f2h_axi_s0_awaddr.eq(top.audio_ram.addr & 0xFFFFFFFC)
        curr_half = Signal() # 16 bit half of the 32 bit word we're writing
        with m.If(self.f2h_axi_s0_awvalid & self.f2h_axi_s0_awready):
            # latch which half we are writing initially
            m.d.sync += curr_half.eq(top.audio_ram.addr[1])
        with m.If(self.f2h_axi_s0_wvalid & self.f2h_axi_s0_wready):
            # swap halves after every write
            m.d.sync += curr_half.eq(~curr_half)
        # set strobes to enable low or high bytes according to current half
        m.d.comb += self.f2h_axi_s0_wstrb.eq(Mux(curr_half, 0b1100, 0b0011))

        # plug off AXI port address write and read data ports
        m.d.comb += [
            self.f2h_axi_s0_arvalid.eq(0),
            self.f2h_axi_s0_rready.eq(self.f2h_axi_s0_rvalid),
        ]

        # hook up CSR interface to Avalon-MM port
        m.d.comb += [
            # only connect word address
            top.csr_bus.addr.eq(self.mm_bridge_fpga_m0_address[2:]),
            top.csr_bus.w_stb.eq(self.mm_bridge_fpga_m0_write),
            top.csr_bus.w_data.eq(self.mm_bridge_fpga_m0_writedata),
            top.csr_bus.r_stb.eq(self.mm_bridge_fpga_m0_read),
            self.mm_bridge_fpga_m0_readdata.eq(top.csr_bus.r_data),
        ]
        # we never need to wait
        m.d.comb += self.mm_bridge_fpga_m0_waitrequest.eq(0)
        # data is always valid the cycle after the request
        m.d.sync += self.mm_bridge_fpga_m0_readdatavalid.eq(
            self.mm_bridge_fpga_m0_read)

        return m

def generate():
    import sys
    from pathlib import Path
    from amaranth.back import verilog
    from .platform import AbbreviatedIntelPlatform

    top = FPGATop()
    with open(Path(sys.argv[1]), "w") as f:
        f.write(verilog.convert(top,
            platform=AbbreviatedIntelPlatform(),
            name="amaranth_top",
            # prevent source paths from being written into the design, in
            # particular absolute paths!
            strip_internal_attrs=True,
        ))

if __name__ == "__main__":
    generate()