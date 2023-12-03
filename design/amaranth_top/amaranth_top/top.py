from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Interface, connect, flipped
from amaranth.lib.cdc import ResetSynchronizer, FFSynchronizer
from amaranth.lib.fifo import AsyncFIFO

from amaranth_soc import csr

import numpy as np

from .bus import AudioRAMBus
from .constants import MIC_FREQ_HZ, NUM_TAPS, NUM_MICS, NUM_CHANS
from .cyclone_v_pll import IntelPLL
from .mic import MicCapture, MicCaptureRegs
from .convolve import Convolver
from .stream import SampleStream, SampleStreamFIFO, SampleWriter

class Blinker(wiring.Component):
    button_raw: In(1)
    blink: Out(1)

    def elaborate(self, platform):
        m = Module()

        button_sync = Signal() # active low
        m.submodules += FFSynchronizer(self.button_raw, button_sync)

        MAX_COUNT = int(25e6)
        counter = Signal(range(0, MAX_COUNT-1))
        with m.If(counter == MAX_COUNT-1):
            m.d.sync += counter.eq(0)
            m.d.sync += self.blink.eq(~self.blink & button_sync)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        return m

class Top(wiring.Component):
    button_raw: In(1)
    blink: Out(1)

    status_leds: Out(3)

    audio_ram: Out(AudioRAMBus())
    csr_bus: In(csr.Signature(addr_width=8, data_width=32))

    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data_raw: In(NUM_MICS//2)

    def __init__(self):
        # TODO: gross and possibly illegal (is the memory map always the same?)
        csr_sig = self.__annotations__["csr_bus"].signature
        self._csr_decoder = csr.Decoder(
            addr_width=csr_sig.addr_width, data_width=csr_sig.data_width)
        csr_sig.memory_map = self._csr_decoder.bus.memory_map

        self._sample_writer = SampleWriter()
        self._mic_capture_regs = MicCaptureRegs(o_domain="mic_capture")

        # add subordinate buses to decoder
        # fix addresses for now for program consistency
        self._csr_decoder.add(self._sample_writer.csr_bus, addr=0)
        self._csr_decoder.add(self._mic_capture_regs.csr_bus, addr=4)

        super().__init__() # initialize component and attributes from signature

    def elaborate(self, platform):
        m = Module()

        m.submodules.blinker = blinker = Blinker()
        m.d.comb += [
            blinker.button_raw.eq(self.button_raw),
            self.blink.eq(blinker.blink),
        ]

        # decode busses for all the subordinate components
        m.submodules.csr_decoder = self._csr_decoder
        connect(m, flipped(self.csr_bus), self._csr_decoder.bus)

        # instantiate mic capture unit in its domain
        m.submodules.mic_capture = mic_capture = \
            DomainRenamer("mic_capture")(MicCapture())
        m.d.comb += [
            self.mic_sck.eq(mic_capture.mic_sck),
            self.mic_ws.eq(mic_capture.mic_ws),
            mic_capture.mic_data_raw.eq(self.mic_data_raw),
        ]

        # instantiate and hook up mic capture registers
        m.submodules.mic_capture_regs = cap_regs = self._mic_capture_regs
        m.d.comb += [
            mic_capture.gain.eq(cap_regs.gain),
            mic_capture.use_fake_mics.eq(cap_regs.use_fake_mics)
        ]

        # FIFO to cross domains from mic capture to the convolver
        m.submodules.mic_fifo = mic_fifo = \
            SampleStreamFIFO(w_domain="mic_capture", r_domain="convolver")
        connect(m, mic_capture.samples, mic_fifo.samples_w)

        # for now generate coefficients that just copy the output to the input
        coefficients = np.zeros((NUM_CHANS, NUM_TAPS, NUM_MICS),
            dtype=np.float64)
        for x in range(min(NUM_MICS, NUM_CHANS)):
            # make each output channel an average of all the input mics
            coefficients[x, -1, :] = 1

        # instantiate convolver in its domain
        m.submodules.convolver = convolver = \
            DomainRenamer("convolver")(Convolver(coefficients))
        connect(m, mic_fifo.samples_r, convolver.samples_i)
        m.d.comb += convolver.samples_i_count.eq(mic_fifo.samples_count)

        # FIFO to cross domains from convolver to the writer
        m.submodules.conv_fifo = conv_fifo = \
            SampleStreamFIFO(w_domain="convolver")
        connect(m, convolver.samples_o, conv_fifo.samples_w)

        # writer to save sample data to memory
        m.submodules.sample_writer = sample_writer = self._sample_writer
        connect(m, conv_fifo.samples_r, sample_writer.samples)
        connect(m, sample_writer.audio_ram, flipped(self.audio_ram))
        m.d.comb += [
            sample_writer.samples_count.eq(conv_fifo.samples_count),

            self.status_leds.eq(sample_writer.status_leds),
        ]

        return m

class FPGATop(wiring.Component):
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
