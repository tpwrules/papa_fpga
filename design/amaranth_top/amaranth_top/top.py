from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Interface, connect, flipped
from amaranth.lib.cdc import ResetSynchronizer, FFSynchronizer
from amaranth.lib.fifo import AsyncFIFO

from .bus import AudioRAMBus, RegisterBus
from .constants import MIC_FREQ_HZ, CAP_DATA_BITS, USE_FAKE_MICS, NUM_MICS
from .cyclone_v_pll import IntelPLL
from .mic import MIC_FRAME_BITS, MIC_DATA_BITS, MicClockGenerator, \
    MicDataReceiver, FakeMic
from .stream import SampleStream, SampleStreamFIFO, SampleWriter

class MicCapture(wiring.Component):
    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data: In(NUM_MICS//2)

    samples: Out(SampleStream())

    def elaborate(self, platform):
        m = Module()

        # generate and propagate microphone clocks
        m.submodules.clk_gen = clk_gen = MicClockGenerator()
        m.d.comb += [
            self.mic_sck.eq(clk_gen.mic_sck),
            self.mic_ws.eq(clk_gen.mic_ws),
        ]

        # hook up mic data to fake or real microphones as appropriate
        mic_data = Signal(NUM_MICS//2)
        if not USE_FAKE_MICS:
            m.d.comb += mic_data.eq(self.mic_data)
        else:
            data_out = []
            # mic sequence parameters
            base = 1 << (MIC_DATA_BITS-1) # ensure top bit is captured
            step = 1 << (MIC_DATA_BITS-CAP_DATA_BITS) # ensure change is seen
            for mi in range(0, NUM_MICS):
                side = "left" if mi % 2 == 1 else "right"
                # make sure each mic's data follows a unique sequence
                fake_mic = FakeMic(side, base+(mi*step)+mi, inc=NUM_MICS*step+1)
                m.submodules[f"fake_mic_{mi}"] = fake_mic

                this_mic_data = Signal(1, name=f"mic_data_{mi}")
                data_out.append(this_mic_data)

                m.d.comb += [
                    fake_mic.mic_sck.eq(clk_gen.mic_sck),
                    fake_mic.mic_ws.eq(clk_gen.mic_ws),
                    this_mic_data.eq(fake_mic.mic_data),
                ]

            for mi in range(0, NUM_MICS, 2): # wire up mic outputs
                m.d.comb += mic_data[mi//2].eq(data_out[mi] | data_out[mi+1])

        # wire up the microphone receivers
        def cap(s): # transform from mic sample to captured sample
            return s[MIC_DATA_BITS-CAP_DATA_BITS:]
        sample_out = []
        sample_new = Signal()
        for mi in range(0, NUM_MICS, 2): # one receiver takes data from two mics
            mic_rx = MicDataReceiver()
            m.submodules[f"mic_rx_{mi}"] = mic_rx

            sample_r = Signal(signed(CAP_DATA_BITS), name=f"mic_sample_{mi}")
            sample_l = Signal(signed(CAP_DATA_BITS), name=f"mic_sample_{mi+1}")
            sample_out.extend((sample_r, sample_l))

            m.d.comb += [
                mic_rx.mic_sck.eq(clk_gen.mic_sck), # data in
                mic_rx.mic_data_sof_sync.eq(clk_gen.mic_data_sof_sync),
                mic_rx.mic_data.eq(mic_data[mi//2]),

                sample_l.eq(cap(mic_rx.sample_l)), # sample data out
                sample_r.eq(cap(mic_rx.sample_r)),
            ]

            # all mics run off the same clock so we only need to grab the new
            # sample flag from the first mic
            if mi == 0:
                m.d.comb += sample_new.eq(mic_rx.sample_new)

        # shift out all microphone data in sequence
        sample_buf = Signal(NUM_MICS*CAP_DATA_BITS)
        m.d.comb += self.samples.data.eq(sample_buf[:CAP_DATA_BITS])

        mic_counter = Signal(range(NUM_MICS-1))        
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(sample_new):
                    # latch all microphone data into the sample buffer
                    for mi in range(0, NUM_MICS):
                        m.d.sync += sample_buf.word_select(
                            mi, CAP_DATA_BITS).eq(sample_out[mi])
                    m.d.sync += [
                        mic_counter.eq(NUM_MICS-1), # reset output counter
                        self.samples.first.eq(1), # prime first output flag
                        self.samples.valid.eq(1), # notify about new samples
                    ]
                    m.next = "OUTPUT"

            with m.State("OUTPUT"):
                with m.If(self.samples.valid & self.samples.ready):
                    # remaining samples are not the first
                    m.d.sync += self.samples.first.eq(0)

                    # shift out microphone data
                    m.d.sync += [
                        sample_buf.eq(sample_buf >> CAP_DATA_BITS),
                        mic_counter.eq(mic_counter-1),
                    ]

                    with m.If(mic_counter == 0): # last mic
                        m.d.sync += self.samples.valid.eq(0)
                        m.next = "IDLE"

        return m

class Top(wiring.Component):
    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    audio_ram: Out(AudioRAMBus())
    register_bus: In(RegisterBus().flip()) # is the flip correct?

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

        # register demo
        register_data = Signal(32)
        with m.If((self.register_bus.addr == 0) & (self.register_bus.r_en)):
            m.d.sync += self.register_bus.r_data.eq(register_data)
        with m.If((self.register_bus.addr == 0) & (self.register_bus.w_en)):
            m.d.sync += register_data.eq(self.register_bus.w_data)

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
                if isinstance(getattr(self, name), Interface):
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

        # hook up register bus to Avalon-MM port
        m.d.comb += [
            top.register_bus.addr.eq(self.mm_bridge_fpga_m0_address),
            top.register_bus.w_en.eq(self.mm_bridge_fpga_m0_write),
            top.register_bus.w_data.eq(self.mm_bridge_fpga_m0_writedata),
            top.register_bus.r_en.eq(self.mm_bridge_fpga_m0_read),
            self.mm_bridge_fpga_m0_readdata.eq(top.register_bus.r_data),
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
