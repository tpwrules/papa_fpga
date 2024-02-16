from amaranth import *
from amaranth.lib.wiring import Component, In, Out, connect
from amaranth.lib.cdc import ResetSynchronizer

from .top import Top
from .constants import MIC_FREQ_HZ, NUM_MICS
from .mic import MicCapture
from .convolve import Convolver
from .cyclone_v_pll import IntelPLL
from .axi3_csr import AXI3CSRBridge
from .cyclone_v_hps import CycloneVHPS

class FPGATop(Component):
    clk50:      In(1)

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

    h2f_lw_awid: In(12)
    h2f_lw_awaddr: In(21)
    h2f_lw_awlen: In(4)
    h2f_lw_awsize: In(3)
    h2f_lw_awburst: In(2)
    h2f_lw_awlock: In(2)
    h2f_lw_awcache: In(4)
    h2f_lw_awprot: In(3)
    h2f_lw_awvalid: In(1)
    h2f_lw_awready: Out(1)
    h2f_lw_wid: In(12)
    h2f_lw_wdata: In(32)
    h2f_lw_wstrb: In(4)
    h2f_lw_wlast: In(1)
    h2f_lw_wvalid: In(1)
    h2f_lw_wready: Out(1)
    h2f_lw_bid: Out(12)
    h2f_lw_bresp: Out(2)
    h2f_lw_bvalid: Out(1)
    h2f_lw_bready: In(1)
    h2f_lw_arid: In(12)
    h2f_lw_araddr: In(21)
    h2f_lw_arlen: In(4)
    h2f_lw_arsize: In(3)
    h2f_lw_arburst: In(2)
    h2f_lw_arlock: In(2)
    h2f_lw_arcache: In(4)
    h2f_lw_arprot: In(3)
    h2f_lw_arvalid: In(1)
    h2f_lw_arready: Out(1)
    h2f_lw_rid: Out(12)
    h2f_lw_rdata: Out(32)
    h2f_lw_rresp: Out(2)
    h2f_lw_rlast: Out(1)
    h2f_lw_rvalid: Out(1)
    h2f_lw_rready: In(1)

    def elaborate(self, platform):
        m = Module()

        # set up HPS
        m.submodules.hps = hps = CycloneVHPS()

        # wire up main clock domain and PLL. note that all PLL outputs are
        # marked as asynchronous w.r.t. its inputs and each other in the .sdc
        m.domains.sync = sync = ClockDomain()
        m.d.comb += sync.clk.eq(self.clk50)
        m.submodules.main_pll = main_pll = IntelPLL("50 MHz")

        # hook up another PLL for the convolver so the ratios work out
        m.submodules.conv_pll = conv_pll = IntelPLL("50 MHz")

        # hold whole design in reset until PLL is locked
        reset = Signal()
        m.d.comb += reset.eq(
            hps.h2f_rst & main_pll.o_locked & conv_pll.o_locked)
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

        # hook up AXI -> CSR bridge
        m.submodules.csr_bridge = csr_bridge = AXI3CSRBridge()
        for name in self.signature.members.keys():
            if not name.startswith("h2f_lw_"): continue
            bname = name.replace("h2f_lw_", "")
            if self.signature.members[name].flow == In:
                m.d.comb += getattr(csr_bridge, bname).eq(getattr(self, name))
            else:
                m.d.comb += getattr(self, name).eq(getattr(csr_bridge, bname))
        connect(m, csr_bridge.csr_bus, top.csr_bus)

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
