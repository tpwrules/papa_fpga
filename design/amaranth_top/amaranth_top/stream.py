from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Signature
from amaranth.lib.fifo import AsyncFIFO

from .bus import AudioRAMBus, RegisterBus
from .constants import CAP_DATA_BITS, NUM_MICS

# sample data in the system
class SampleStream(Signature):
    def __init__(self):
        super().__init__({
            "data": Out(signed(CAP_DATA_BITS)),
            "first": Out(1), # first sample of the microphone set

            "ready": In(1), # receiver is ready for new data
            "valid": Out(1), # transmitter has new data
        })

class SampleStreamFIFO(wiring.Component):
    samples_w: In(SampleStream())
    samples_r: Out(SampleStream())

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
            fifo.w_en.eq(self.samples_w.valid & self.samples_w.ready),
            self.samples_w.ready.eq(fifo.w_rdy),

            # read data
            Cat(self.samples_r.data, self.samples_r.first).eq(fifo.r_data),
            fifo.r_en.eq(self.samples_r.ready & self.samples_r.valid),
            self.samples_r.valid.eq(fifo.r_rdy),
            self.samples_count.eq(fifo.r_level),
        ]

        return m

class SampleWriter(wiring.Component):
    samples: In(SampleStream())
    samples_count: In(32)

    audio_ram: Out(AudioRAMBus())
    register_bus: In(RegisterBus())

    status: Out(3)

    def elaborate(self, platform):
        m = Module()

        curr_buf = Signal(1)
        last_buf = Signal(1)
        last_addr = Signal(32)
        test_reg = Signal(32)

        # the host wants to swap buffers
        swap_desired = Signal(1)
        # we are swapping (swap is desired and the current FIFO word is the
        # start of a new set, so no more addr increments or FIFO acks)
        swapping = Signal(1)

        # address 0 is read/write for testing
        # address 1 is number of microphones, read only
        # address 2 is read/write for swap desired on bit 0
        #     (hardware sets to 0 when swap occurs)
        #      read only for last buffer swapped from on bit 1
        # address 3 is last address before the last swap
        with m.If(self.register_bus.r_en):
            m.d.sync += self.register_bus.r_data.eq(0) # clear out unused bits
            with m.Switch(self.register_bus.addr[2:4]):
                with m.Case(0):
                    m.d.sync += self.register_bus.r_data.eq(test_reg)

                with m.Case(1):
                    m.d.sync += self.register_bus.r_data.eq(NUM_MICS)

                with m.Case(2):
                    m.d.sync += self.register_bus.r_data.eq(
                        Cat(swap_desired, last_buf))

                with m.Case(3):
                    m.d.sync += self.register_bus.r_data.eq(last_addr)

        with m.If(self.register_bus.w_en):
            with m.Switch(self.register_bus.addr[2:4]):
                with m.Case(0):
                    m.d.sync += test_reg.eq(self.register_bus.w_data)

                with m.Case(1):
                    pass # read only

                with m.Case(2):
                    with m.If(self.register_bus.w_data[0]):
                        m.d.sync += swap_desired.eq(1)

                with m.Case(3):
                    pass # read only

        # write words from the stream when available
        BURST_BEATS = 16
        buf_addr = Signal(23) # 8MiB buffer
        burst_counter = Signal(range(max(1, BURST_BEATS-1)))
        m.d.comb += self.audio_ram.data.eq(self.samples.data)
        # first flag is set and a swap is desired
        m.d.comb += swapping.eq(
            self.samples.valid & self.samples.first & swap_desired)
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.samples_count >= BURST_BEATS): # enough data?
                    m.d.sync += [
                        # write address (audio area thru ACP)
                        self.audio_ram.addr.eq(
                            Cat(buf_addr, curr_buf, Const(0xBF, 8))),
                        self.audio_ram.length.eq(BURST_BEATS-1),
                        # address signals are valid
                        self.audio_ram.addr_valid.eq(1),
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
                    with m.If(~swapping):
                        m.d.comb += self.samples.ready.eq(1) # FIFO ack
                        m.d.sync += buf_addr.eq(buf_addr + 2) # bump write addr

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

                    # it's time to finalize the swap? then do it
                    with m.If(swapping):
                        m.d.sync += [
                            curr_buf.eq(~curr_buf), # save next buffer
                            last_addr.eq(buf_addr), # save address for host
                            last_buf.eq(curr_buf), # and the buffer it's for
                            buf_addr.eq(0), # reset buffer to start
                            swap_desired.eq(0), # ack swap
                        ]

                    m.next = "IDLE"

        return m
