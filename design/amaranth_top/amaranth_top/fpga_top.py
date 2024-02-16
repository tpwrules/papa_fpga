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
            hps.f2h_axi_s0.awid.eq(0), # always write with id 0
            hps.f2h_axi_s0.awlen.eq(top.audio_ram.length),
            hps.f2h_axi_s0.awsize.eq(0b001), # two bytes at a time
            hps.f2h_axi_s0.awburst.eq(0b01), # burst mode: increment
            # heard vague rumors that these should just all be 1 to activate
            # caching as expected...
            hps.f2h_axi_s0.awcache.eq(0b1111),
            # and 5 1 bits for the user data too (though that is from the
            # handbook)...
            hps.f2h_axi_s0.awuser.eq(0b11111),
            hps.f2h_axi_s0.awvalid.eq(top.audio_ram.addr_valid),
            top.audio_ram.addr_ready.eq(hps.f2h_axi_s0.awready),

            hps.f2h_axi_s0.wdata.eq( # route 16 bit data to both 32 bit halves
                Cat(top.audio_ram.data, top.audio_ram.data)),
            hps.f2h_axi_s0.wvalid.eq(top.audio_ram.data_valid),
            hps.f2h_axi_s0.wlast.eq(top.audio_ram.data_last),
            top.audio_ram.data_ready.eq(hps.f2h_axi_s0.wready),

            hps.f2h_axi_s0.bready.eq(hps.f2h_axi_s0.bvalid),
            top.audio_ram.txn_done.eq(hps.f2h_axi_s0.bvalid),
        ]

        # transform 16 bit audio bus into 32 bit AXI bus
        # remove bottom two address bits to stay 32 bit aligned
        m.d.comb += hps.f2h_axi_s0.awaddr.eq(top.audio_ram.addr & 0xFFFFFFFC)
        curr_half = Signal() # 16 bit half of the 32 bit word we're writing
        with m.If(hps.f2h_axi_s0.awvalid & hps.f2h_axi_s0.awready):
            # latch which half we are writing initially
            m.d.sync += curr_half.eq(top.audio_ram.addr[1])
        with m.If(hps.f2h_axi_s0.wvalid & hps.f2h_axi_s0.wready):
            # swap halves after every write
            m.d.sync += curr_half.eq(~curr_half)
        # set strobes to enable low or high bytes according to current half
        m.d.comb += hps.f2h_axi_s0.wstrb.eq(Mux(curr_half, 0b1100, 0b0011))

        # plug off AXI port address write and read data ports
        m.d.comb += [
            hps.f2h_axi_s0.arvalid.eq(0),
            hps.f2h_axi_s0.rready.eq(hps.f2h_axi_s0.rvalid),
        ]

        # hook up AXI -> CSR bridge
        m.submodules.csr_bridge = csr_bridge = AXI3CSRBridge()
        for name in hps.h2f_lw.signature.members.keys():
            if name == "clk": continue
            if hps.h2f_lw.signature.members[name].flow == Out:
                m.d.comb += getattr(csr_bridge, name).eq(
                    getattr(hps.h2f_lw, name))
            else:
                m.d.comb += getattr(hps.h2f_lw, name).eq(
                    getattr(csr_bridge, name))
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
