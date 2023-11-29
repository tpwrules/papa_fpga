from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Signature, connect, flipped
from amaranth.lib.fifo import AsyncFIFO

from amaranth_soc import csr
from amaranth_soc.csr import field as csr_field

from .bus import AudioRAMBus
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
    csr_bus: In(csr.Signature(addr_width=2, data_width=32))

    status_leds: Out(3)

    class Test(csr.Register):
        # read/write area for testing
        test: csr_field.RW(32)

    class SysParams(csr.Register):
        # TODO: probably not the right place here for this register
        def __init__(self):
            super().__init__("r", csr.FieldMap({
                # number of microphones read by the system
                "num_mics": csr_field.R(8), # TODO: why doesn't this take reset?
            }))

    class SwapState(csr.Register):
        swap: csr_field.RW1S(1) # request swap/swap status
        last_buf: csr_field.R(1) # last buffer swapped from

    class SwapAddr(csr.Register):
        last_addr: csr_field.R(32) # last address in the buffer swapped from

    def __init__(self):
        self._test = self.Test()
        self._sys_params = self.SysParams()
        self._swap_state = self.SwapState()
        self._swap_addr = self.SwapAddr()

        reg_map = csr.RegisterMap()
        reg_map.add_register(self._test, name="test")
        reg_map.add_register(self._sys_params, name="sys_params")
        reg_map.add_register(self._swap_state, name="swap_state")
        reg_map.add_register(self._swap_addr, name="swap_addr")

        # TODO: gross and possibly illegal (is the memory map always the same?)
        csr_sig = self.__annotations__["csr_bus"].signature
        self._csr_bridge = csr.Bridge(reg_map, name="sample_writer",
            addr_width=csr_sig.addr_width, data_width=csr_sig.data_width)
        csr_sig.memory_map = self._csr_bridge.bus.memory_map

        super().__init__() # initialize component and attributes from signature

    def elaborate(self, platform):
        m = Module()

        # bridge containing CSRs
        m.submodules.csr_bridge = csr_bridge = self._csr_bridge
        connect(m, flipped(self.csr_bus), csr_bridge.bus)

        m.d.comb += self._sys_params.f.num_mics.r_data.eq(NUM_MICS)

        swap_desired = Signal() # the host desires a swap
        m.d.comb += swap_desired.eq(self._swap_state.f.swap.data)

        curr_buf = Signal(1) # current buffer we're filling
        # we are swapping (swap is desired and the current FIFO word is the
        # start of a new set, so no more addr increments or FIFO acks)
        swapping = Signal(1)

        # write words from the stream when available
        BURST_BEATS = 16
        buf_addr = Signal(23) # 8MiB buffer
        burst_counter = Signal(range(max(1, BURST_BEATS-1)))
        m.d.comb += self.audio_ram.data.eq(self.samples.data)
        # first flag is set and a swap is desired by the host
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
                        self.status_leds[0].eq(~self.status_leds[0]),
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
                            self.status_leds[1].eq(~self.status_leds[1]),
                        ]
                        m.next = "TWAIT"

            with m.State("TWAIT"):
                with m.If(self.audio_ram.txn_done):
                    # toggle LED
                    m.d.sync += self.status_leds[2].eq(~self.status_leds[2])

                    # it's time to finalize the swap? then do it
                    with m.If(swapping):
                        m.d.sync += [
                            curr_buf.eq(~curr_buf), # swap to next buffer
                            buf_addr.eq(0), # reset the address to start

                            # save address for host
                            self._swap_addr.f.last_addr.r_data.eq(buf_addr),
                            # and the buffer it's for
                            self._swap_state.f.last_buf.r_data.eq(curr_buf),
                        ]
                        # acknowledge swap
                        m.d.comb += self._swap_state.f.swap.clear.eq(1)

                    m.next = "IDLE"

        return m
