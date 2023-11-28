from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Signature
from amaranth.lib.fifo import AsyncFIFO

from .bus import AudioRAMBus
from .constants import CAP_DATA_BITS, NUM_MICS

# sample data in the system
class SampleStream(Signature):
    def __init__(self):
        super().__init__({
            "data": Out(signed(CAP_DATA_BITS)),
            "first": Out(1), # first sample of the microphone set
            "new": Out(1), # new microphone data is available
        })

class SampleStreamFIFO(wiring.Component):
    samples_w: In(SampleStream())
    samples_r: Out(SampleStream())
    
    sample_ack: In(1)
    samples_count: Out(32)

    def __init__(self, *, w_domain, r_domain="sync", depth=512):
        super().__init__()

        self._fifo = AsyncFIFO(
            width=1+CAP_DATA_BITS, depth=depth,
            r_domain=r_domain, w_domain=w_domain)

    def elaborate(self, platform):
        m = Module()

        m.submodules.fifo = fifo = self._fifo
        m.d.comb += [
            # write data
            fifo.w_data.eq(Cat(self.samples_w.data, self.samples_w.first)),
            fifo.w_en.eq(self.samples_w.new),

            # read data
            Cat(self.samples_r.data, self.samples_r.first).eq(fifo.r_data),
            self.samples_r.new.eq(fifo.r_rdy),
            fifo.r_en.eq(self.sample_ack),
            self.samples_count.eq(fifo.r_level),
        ]

        return m

class SampleWriter(wiring.Component):
    samples: In(SampleStream())
    sample_ack: Out(1)
    samples_count: In(32)

    audio_ram: Out(AudioRAMBus())

    status: Out(3)

    def elaborate(self, platform):
        m = Module()

        # write words from the stream when available
        BURST_BEATS = 16
        ram_addr = Signal(24) # 16MiB audio area
        burst_counter = Signal(range(max(1, BURST_BEATS-1)))
        m.d.comb += self.audio_ram.data.eq(self.samples.data)
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.samples_count >= BURST_BEATS): # enough data?
                    m.d.sync += [
                        # write address (audio area thru ACP)
                        self.audio_ram.addr.eq(0xBF00_0000 | ram_addr),
                        self.audio_ram.length.eq(BURST_BEATS-1),
                        # address signals are valid
                        self.audio_ram.addr_valid.eq(1),
                        # bump write address
                        ram_addr.eq(ram_addr + 2*BURST_BEATS)
                    ]
                    m.next = "AWAIT"

            with m.State("AWAIT"):
                with m.If(self.audio_ram.addr_ready):
                    m.d.sync += [
                        # deassert address valid
                        self.audio_ram.addr_valid.eq(0),
                        # our data is always valid
                        self.audio_ram.data_valid.eq(1),
                        # init burst
                        burst_counter.eq(BURST_BEATS-1),
                        # toggle LED
                        self.status[0].eq(~self.status[0]),
                    ]
                    m.next = "BURST"

            with m.State("BURST"):
                with m.If(burst_counter == 0):
                    m.d.comb += self.audio_ram.data_last.eq(1)

                with m.If(self.audio_ram.data_ready):
                    m.d.comb += self.sample_ack.eq(1)
                    m.d.sync += burst_counter.eq(burst_counter-1)
                    with m.If(burst_counter == 0):
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
