from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Interface, connect, flipped
from amaranth.lib.cdc import ResetSynchronizer, FFSynchronizer
from amaranth.lib.fifo import AsyncFIFO

from amaranth_soc import csr

from .bus import AudioRAMBus
from .constants import MIC_FREQ_HZ, NUM_MICS
from .cyclone_v_pll import IntelPLL
from .mic import MicCapture, MIC_FRAME_BITS
from .stream import SampleStream, SampleStreamFIFO, SampleWriter

class Top(wiring.Component):
    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    audio_ram: Out(AudioRAMBus())
    csr_bus: In(csr.Signature(addr_width=8, data_width=32))

    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data: In(NUM_MICS//2)

    def elaborate(self, platform):
        m = Module()

        button = Signal()
        m.submodules += FFSynchronizer(self.button, button)

        MAX_COUNT = int(25e6)
        counter = Signal(range(0, MAX_COUNT-1))
        with m.If(counter == MAX_COUNT-1):
            m.d.sync += counter.eq(0)
            m.d.sync += self.blink.eq(~self.blink & button)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        # instantiate mic capture unit in its domain
        m.submodules.mic_capture = mic_capture = \
            DomainRenamer("mic_capture")(MicCapture())
        m.d.comb += [
            self.mic_sck.eq(mic_capture.mic_sck),
            self.mic_ws.eq(mic_capture.mic_ws),
            mic_capture.mic_data.eq(self.mic_data),
        ]

        # FIFO to cross domains from mic capture
        m.submodules.mic_fifo = mic_fifo = \
            SampleStreamFIFO(w_domain="mic_capture")
        connect(m, mic_capture.samples, mic_fifo.samples_w)

        # writer to save sample data to memory
        m.submodules.writer = writer = SampleWriter()
        connect(m, mic_fifo.samples_r, writer.samples)
        connect(m, writer.audio_ram, flipped(self.audio_ram))
        m.d.comb += [
            writer.samples_count.eq(mic_fifo.samples_count),

            self.status.eq(writer.status),
        ]

        # decode busses for all the subordinate components
        # TODO: how to avoid duplication with self.csr_bus.signature?
        m.submodules.csr_decoder = csr_decoder = csr.Decoder(
            addr_width=8, data_width=32)
        # fix address at 0 for now for program consistency
        # TODO: also seems illegit
        csr_decoder.add(writer.csr_bus.signature.create(), addr=0)
        connect(m, flipped(self.csr_bus), csr_decoder.bus)

        return m

class FPGATop(wiring.Component):
    clk50:      In(1)
    rst:        In(1)

    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    GPIO_0_OUT: Out(2)
    GPIO_0_IN:  In(34)

    # copy-pasta from verilog
    f2h_axi_s0_awid: Out(7)
    f2h_axi_s0_awaddr: Out(32)
    f2h_axi_s0_awlen: Out(8)
    f2h_axi_s0_awsize: Out(3)
    f2h_axi_s0_awburst: Out(2)
    f2h_axi_s0_awcache: Out(4)
    f2h_axi_s0_awuser: Out(64)
    f2h_axi_s0_awvalid: Out(1)
    f2h_axi_s0_awready: In(1)
    f2h_axi_s0_wdata: Out(32)
    f2h_axi_s0_wstrb: Out(4)
    f2h_axi_s0_wlast: Out(1)
    f2h_axi_s0_wvalid: Out(1)
    f2h_axi_s0_wready: In(1)
    f2h_axi_s0_bid: In(7)
    f2h_axi_s0_bresp: In(2)
    f2h_axi_s0_bvalid: In(1)
    f2h_axi_s0_bready: Out(1)
    f2h_axi_s0_arid: Out(7)
    f2h_axi_s0_araddr: Out(32)
    f2h_axi_s0_arlen: Out(8)
    f2h_axi_s0_arsize: Out(3)
    f2h_axi_s0_arburst: Out(2)
    f2h_axi_s0_arvalid: Out(1)
    f2h_axi_s0_arready: In(1)
    f2h_axi_s0_rid: In(7)
    f2h_axi_s0_rdata: In(32)
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

        # hold whole design in reset until PLL is locked
        reset = Signal()
        m.d.comb += reset.eq(self.rst & main_pll.o_locked)
        m.submodules += ResetSynchronizer(reset)

        # set up mic capture domain
        # frequency is doubled from microphone data rate
        mic_capture_freq = 2*MIC_FREQ_HZ*MIC_FRAME_BITS
        m.domains.mic_capture = mic_capture = ClockDomain()
        m.d.comb += mic_capture.clk.eq(
            main_pll.add_output(f"{mic_capture_freq} Hz"))
        m.submodules += ResetSynchronizer(reset, domain="mic_capture")

        # wire up top module
        m.submodules.top = top = Top()
        for name, member in top.signature.members.items():
            try:
                if not isinstance(getattr(self, name), Signal):
                    continue
            except AttributeError:
                continue
            if member.flow == In:
                m.d.comb += getattr(top, name).eq(getattr(self, name))
            elif member.flow == Out:
                m.d.comb += getattr(self, name).eq(getattr(top, name))
            else:
                raise ValueError("bad flow")

        # wire up microphone data bus
        m.d.comb += [
            self.GPIO_0_OUT[1].eq(top.mic_sck),
            self.GPIO_0_OUT[0].eq(top.mic_ws),
        ]
        for mpi in range(NUM_MICS//2):
            m.d.comb += top.mic_data[mpi].eq(self.GPIO_0_IN[33-mpi])

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
