from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Interface, connect, flipped
from amaranth.lib.cdc import ResetSynchronizer, FFSynchronizer
from amaranth.lib.fifo import AsyncFIFO

from .bus import AudioRAMBus
from .constants import MIC_FREQ_HZ, USE_FAKE_MICS
from .cyclone_v_pll import IntelPLL
from .mic import MIC_FRAME_BITS, MIC_DATA_BITS, MicClockGenerator, \
    MicDataReceiver, FakeMic

class MicCapture(wiring.Component):
    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data: In(1)

    sample_l: Out(signed(MIC_DATA_BITS))
    sample_r: Out(signed(MIC_DATA_BITS))
    sample_new: Out(1)

    def elaborate(self, platform):
        m = Module()

        # generate and propagate microphone clocks
        m.submodules.clk_gen = clk_gen = MicClockGenerator()
        m.d.comb += [
            self.mic_sck.eq(clk_gen.mic_sck),
            self.mic_ws.eq(clk_gen.mic_ws),
        ]

        # hook up mic data as appropriate
        mic_data = Signal()
        if not USE_FAKE_MICS:
            m.d.comb += mic_data.eq(self.mic_data)
        else:
            m.submodules.fake_mic_l = fake_mic_l = \
                FakeMic("left", 0x80_0000, inc=0x201)
            m.submodules.fake_mic_r = fake_mic_r = \
                FakeMic("right", 0x80_0101, inc=0x201)
            m.d.comb += [
                fake_mic_l.mic_sck.eq(clk_gen.mic_sck),
                fake_mic_l.mic_ws.eq(clk_gen.mic_ws),
                fake_mic_r.mic_sck.eq(clk_gen.mic_sck),
                fake_mic_r.mic_ws.eq(clk_gen.mic_ws),

                mic_data.eq(fake_mic_l.mic_data | fake_mic_r.mic_data),
            ]

        # wire up the microphone receiver
        m.submodules.mic = mic = MicDataReceiver()
        m.d.comb += [
            mic.mic_sck.eq(clk_gen.mic_sck),
            mic.mic_data_sof_sync.eq(clk_gen.mic_data_sof_sync),
            mic.mic_data.eq(mic_data),

            self.sample_l.eq(mic.sample_l),
            self.sample_r.eq(mic.sample_r),
            self.sample_new.eq(mic.sample_new),
        ]

        return m

class Top(wiring.Component):
    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    audio_ram: Out(AudioRAMBus())

    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data: In(1)

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

        # first-word fallthrough FIFO to cross domains from mic capture
        m.submodules.mic_fifo = mic_fifo = AsyncFIFO(
            width=32, depth=256,
            r_domain="sync",
            w_domain="mic_capture",
        )
        m.d.comb += [
            mic_fifo.w_data.eq(
                (mic_capture.sample_l[8:24]<<16) | mic_capture.sample_r[8:24]),
            mic_fifo.w_en.eq(mic_capture.sample_new),
        ]

        # write a word from the data FIFO when available
        ram_addr = Signal(24) # 16MiB audio area
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(mic_fifo.r_rdy): # new word available
                    m.d.sync += [
                        # write address (audio area thru ACP)
                        self.audio_ram.addr.eq(0xBF00_0000 | ram_addr),
                        # one word please
                        self.audio_ram.length.eq(0),
                        # signals are valid
                        self.audio_ram.addr_valid.eq(1),
                        # bump write address
                        ram_addr.eq(ram_addr + 4)
                    ]
                    m.next = "AWAIT"

            with m.State("AWAIT"):
                with m.If(self.audio_ram.addr_ready):
                    m.d.sync += [
                        # deassert valid
                        self.audio_ram.addr_valid.eq(0),
                        # set up data
                        self.audio_ram.data.eq(mic_fifo.r_data),
                        self.audio_ram.data_valid.eq(1),
                        # toggle LED
                        self.status[0].eq(~self.status[0]),
                    ]
                    m.d.comb += mic_fifo.r_en.eq(1) # acknowledge FIFO data
                    m.next = "DWAIT"

            with m.State("DWAIT"):
                with m.If(self.audio_ram.data_ready):
                    m.d.sync += [
                        # deassert valid
                        self.audio_ram.data_valid.eq(0),
                        # toggle LED
                        self.status[1].eq(~self.status[1]),
                    ]
                    m.next = "TWAIT"

            with m.State("TWAIT"):
                with m.If(self.audio_ram.txn_done):
                    # toggle LED
                    m.d.sync += self.status[2].eq(~self.status[2])
                    m.next = "IDLE"

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
    f2h_axi_s0_wvalid: Out(1)
    f2h_axi_s0_wready: In(1)
    f2h_axi_s0_bid: In(7)
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

            top.mic_data.eq(self.GPIO_0_IN[33]),
        ]

        # hook up audio RAM bus to AXI port
        m.d.comb += [
            self.f2h_axi_s0_awid.eq(0), # always write with id 0
            self.f2h_axi_s0_awaddr.eq(top.audio_ram.addr),
            self.f2h_axi_s0_awlen.eq(top.audio_ram.length),
            self.f2h_axi_s0_awsize.eq(0b010), # four bytes at a time
            self.f2h_axi_s0_awburst.eq(0b01), # burst mode: increment
            # heard vague rumors that these should just all be 1 to activate
            # caching as expected...
            self.f2h_axi_s0_awcache.eq(0b1111),
            # and 5 1 bits for the user data too (though that is from the
            # handbook)...
            self.f2h_axi_s0_awuser.eq(0b11111),
            self.f2h_axi_s0_awvalid.eq(top.audio_ram.addr_valid),
            top.audio_ram.addr_ready.eq(self.f2h_axi_s0_awready),

            self.f2h_axi_s0_wdata.eq(top.audio_ram.data),
            self.f2h_axi_s0_wstrb.eq(0b1111),
            self.f2h_axi_s0_wvalid.eq(top.audio_ram.data_valid),
            top.audio_ram.data_ready.eq(self.f2h_axi_s0_wready),

            self.f2h_axi_s0_bready.eq(self.f2h_axi_s0_bvalid),
            top.audio_ram.txn_done.eq(self.f2h_axi_s0_bvalid),
        ]

        # plug off address write and read data ports
        m.d.comb += [
            self.f2h_axi_s0_arvalid.eq(0),
            self.f2h_axi_s0_rready.eq(self.f2h_axi_s0_rvalid),
        ]

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
