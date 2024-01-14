from amaranth import *
from amaranth.lib.wiring import Component, In, Out, connect, flipped
from amaranth.lib.cdc import FFSynchronizer

from amaranth_soc import csr
from amaranth_soc.csr import Field

from .constants import NUM_MICS, CAP_DATA_BITS
from .stream import SampleStream
from .misc import FFDelay

MIC_DATA_BITS = 24 # each word is a signed 24 bit number
MIC_FRAME_BITS = 64 # 64 data bits per data frame from the microphone

class MicClockGenerator(Component):
    # generate the microphone clock suitable for wiring to the microphone's
    # input pins. the generated clock is half the module clock.
    mic_sck: Out(1)
    mic_ws: Out(1)
    # pulsed on the cycle the mic transmits the first frame data bit.
    # (cycle after WS falls, before FF delay) (note also the first data bit is
    # hi-z and these cycles are with reference to the module clock)
    mic_data_sof_sync: Out(1)

    def elaborate(self, platform):
        m = Module()

        # cycle counter within the frame
        cycle = Signal(range(MIC_FRAME_BITS))

        # toggle clock
        m.d.sync += self.mic_sck.eq(~self.mic_sck)
        # bump the cycle counter on the positive edge of the mic cycle
        with m.If(~self.mic_sck):
            m.d.sync += cycle.eq(cycle + 1)

        # lower word select on falling edge before cycle start
        with m.If((cycle == MIC_FRAME_BITS-1) & self.mic_sck):
            m.d.sync += self.mic_ws.eq(0)
        # raise word select on falling edge before second half of cycle
        with m.If((cycle == (MIC_FRAME_BITS//2)-1) & self.mic_sck):
            m.d.sync += self.mic_ws.eq(1)

        mic_data_sof = Signal()
        m.d.comb += mic_data_sof.eq((cycle == 0) & self.mic_sck)
        # generate delayed start of frame pulse for input modules due to the
        # CDC delay they put on the data line
        m.submodules += FFDelay(mic_data_sof, self.mic_data_sof_sync)

        return m

class MicDataReceiver(Component):
    # receive data from a microphone
    mic_sck: In(1)
    mic_data_raw: In(1)
    mic_data_sof_sync: In(1)

    # optional fake microphone input. switch is in no way clean!
    use_fake_mic: In(1)
    mic_fake_data_raw: In(1)

    sample_l: Out(signed(MIC_DATA_BITS))
    sample_r: Out(signed(MIC_DATA_BITS))
    sample_new: Out(1) # pulsed when new sample data is available

    def elaborate(self, platform):
        m = Module()

        # synchronize mic data to module clock
        mic_data_sync = Signal()
        fake_data_sync = Signal()
        m.submodules += FFSynchronizer(self.mic_data_raw, mic_data_sync)
        m.submodules += FFDelay(self.mic_fake_data_raw, fake_data_sync)

        buffer = Signal(MIC_FRAME_BITS)
        # shift in new data on rising edge of clock into the MSB of buffer
        with m.If(self.mic_sck):
            m.d.sync += buffer.eq(Cat(buffer[1:], Mux(
                self.use_fake_mic, fake_data_sync, mic_data_sync)))

        m.d.sync += self.sample_new.eq(0) # usually no data available
        # once the frame is over, save the data in the outputs
        with m.If(self.mic_data_sof_sync):
            m.d.sync += [
                self.sample_l.eq(buffer[1:1+MIC_DATA_BITS][::-1]),
                self.sample_r.eq(buffer[33:33+MIC_DATA_BITS][::-1]),
                self.sample_new.eq(1),
            ]

        return m

class FakeMic(Component):
    # fake microphone output data in accordance with timing diagrams
    # (assumes mic_sck is half "sync"'s clock rate)
    mic_sck: In(1)
    mic_ws: In(1)

    mic_data_raw: Out(1)

    def __init__(self, channel, start=0, inc=1):
        super().__init__()

        if channel == "left":
            self._sensitive = self._fell
        elif channel == "right":
            self._sensitive = self._rose
        else:
            raise ValueError("bad channel")

        self._start = start
        self._inc = inc

    def elaborate(self, platform):
        m = Module()

        counter = Signal(MIC_DATA_BITS, reset=self._start)
        sample = Signal(MIC_DATA_BITS)
        buffer = Signal(MIC_DATA_BITS)

        # on rising edge of word select, sample the "sound"
        with m.If(self._rose(m, self.mic_ws)):
            m.d.sync += [
                sample.eq(counter),
                counter.eq(counter+self._inc),
            ]

        # when the correct word select is asserted, move sample to buffer to
        # shift out
        with m.If(self._sensitive(m, self.mic_ws)):
            m.d.sync += buffer.eq(sample)

        # shift the buffer on the rising edge so it comes out synchronous with
        # the falling edge
        with m.If(self._rose(m, self.mic_sck)):
            m.d.sync += [
                buffer.eq(buffer << 1),
                self.mic_data_raw.eq(buffer[-1]),
            ]

        return m

    def _rose(self, m, s):
        assert len(s) == 1

        # avoid false triggering on first cycle of design if signal starts high
        last = Signal(1, reset=1)
        m.d.sync += last.eq(s) # only applies when conditions match where called

        return ~last & s

    def _fell(self, m, s):
        assert len(s) == 1

        # avoid false triggering on first cycle of design if signal starts low
        last = Signal(1, reset=0)
        m.d.sync += last.eq(s) # only applies when conditions match where called

        return last & ~s

# scale mic data according to gain, and clamp instead of wrapping. also
# responsible for reducing the bit depth. currently the "scale" is just a
# straight multiplication with gain+1 (so that 0 is gain=1) and low bit
# truncate. we do it entirely combinatorially because of laziness
class GainProcessor(Component):
    sample_in: In(signed(MIC_DATA_BITS))
    sample_out: Out(signed(CAP_DATA_BITS))

    gain: In(8)

    def elaborate(self, platform):
        m = Module()

        # compute signed minimum and maximum output values
        max_val = (1<<(CAP_DATA_BITS-1))-1
        min_val = -(max_val)-1

        # scale by shifting according to gain
        scaled_data = Signal(signed(2*MIC_DATA_BITS))
        m.d.comb += scaled_data.eq(self.sample_in * (self.gain + 1))

        # remove low bits
        num_low_bits = MIC_DATA_BITS-CAP_DATA_BITS
        truncated_data = Signal(signed(2*MIC_DATA_BITS - num_low_bits))
        m.d.comb += truncated_data.eq(scaled_data >> num_low_bits)

        # clamp truncated value
        with m.If(truncated_data < min_val):
            m.d.comb += self.sample_out.eq(min_val)
        with m.Elif(truncated_data > max_val):
            m.d.comb += self.sample_out.eq(max_val)
        with m.Else():
            m.d.comb += self.sample_out.eq(truncated_data)

        return m


# separate component for CDC reasons
class MicCaptureRegs(Component):
    csr_bus: In(csr.Signature(addr_width=2, data_width=32))

    # settings, synced to mic capture domain (given by o_domain)
    gain: Out(8)
    use_fake_mics: Out(1)

    class Gain(csr.Register, access="rw"):
        gain: Field(csr.action.RW, 8)

    class FakeMics(csr.Register, access="rw"):
        use_fake_mics: Field(csr.action.RW, 1)

    def __init__(self, *, o_domain):
        self._o_domain = o_domain

        self._gain = self.Gain()
        self._fake_mics = self.FakeMics()

        reg_map = csr.RegisterMap()
        reg_map.add_register(self._gain, name="gain")
        reg_map.add_register(self._fake_mics, name="fake_mics")

        csr_sig = self.__annotations__["csr_bus"].signature
        self._csr_bridge = csr.Bridge(reg_map, name="mic_capture",
            addr_width=csr_sig.addr_width, data_width=csr_sig.data_width)

        super().__init__() # initialize component and attributes from signature

        self.csr_bus.memory_map = self._csr_bridge.bus.memory_map

    def elaborate(self, platform):
        m = Module()

        # bridge containing CSRs
        m.submodules.csr_bridge = csr_bridge = self._csr_bridge
        connect(m, flipped(self.csr_bus), csr_bridge.bus)

        m.submodules += FFSynchronizer(self._gain.f.gain.data, self.gain,
            o_domain=self._o_domain)
        m.submodules += FFSynchronizer(self._fake_mics.f.use_fake_mics.data,
            self.use_fake_mics, o_domain=self._o_domain)

        return m

class MicCapture(Component):
    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data_raw: In(NUM_MICS//2)

    # settings, synced to our domain
    gain: In(8)
    use_fake_mics: In(1)

    samples: Out(SampleStream())

    # frequency relative to the microphone sample frequency (i.e. multiply that
    # by this to get the expected operation frequency)
    # generated bit clock is half the module clock so we need to double
    REL_FREQ = 2*MIC_FRAME_BITS

    def elaborate(self, platform):
        m = Module()

        # generate and propagate microphone clocks
        m.submodules.clk_gen = clk_gen = MicClockGenerator()
        m.d.comb += [
            self.mic_sck.eq(clk_gen.mic_sck),
            self.mic_ws.eq(clk_gen.mic_ws),
        ]

        # set up fake microphones for testing purposes
        fake_data_raw = Signal(NUM_MICS//2)
        fake_outs = []
        # mic sequence parameters
        base = 1 << (MIC_DATA_BITS-1) # ensure top bit is captured
        step = 1 << (MIC_DATA_BITS-CAP_DATA_BITS) # ensure change is seen
        for mi in range(0, NUM_MICS):
            side = "left" if mi % 2 == 1 else "right"
            # make sure each mic's data follows a unique sequence when captured
            fake_mic = FakeMic(side, base+(mi*step)+mi, inc=NUM_MICS*step+1)
            m.submodules[f"fake_mic_{mi}"] = fake_mic

            this_mic_fake_raw = Signal(1, name=f"mic_fake_raw_{mi}")
            fake_outs.append(this_mic_fake_raw)

            m.d.comb += [
                fake_mic.mic_sck.eq(clk_gen.mic_sck),
                fake_mic.mic_ws.eq(clk_gen.mic_ws),
                this_mic_fake_raw.eq(fake_mic.mic_data_raw),
            ]

        for mi in range(0, NUM_MICS, 2): # wire up mic outputs
            m.d.comb += fake_data_raw[mi//2].eq(fake_outs[mi] | fake_outs[mi+1])

        # wire up the microphone receivers
        sample_out = []
        sample_new = Signal()
        for mi in range(0, NUM_MICS, 2): # one receiver takes data from two mics
            mic_rx = MicDataReceiver()
            m.submodules[f"mic_rx_{mi}"] = mic_rx

            sample_r = Signal(signed(MIC_DATA_BITS), name=f"mic_sample_{mi}")
            sample_l = Signal(signed(MIC_DATA_BITS), name=f"mic_sample_{mi+1}")
            sample_out.extend((sample_r, sample_l))

            m.d.comb += [
                mic_rx.mic_sck.eq(clk_gen.mic_sck), # data in
                mic_rx.mic_data_sof_sync.eq(clk_gen.mic_data_sof_sync),
                mic_rx.mic_data_raw.eq(self.mic_data_raw[mi//2]),

                mic_rx.use_fake_mic.eq(self.use_fake_mics), # fake data in
                mic_rx.mic_fake_data_raw.eq(fake_data_raw[mi//2]),

                sample_l.eq(mic_rx.sample_l), # sample data out
                sample_r.eq(mic_rx.sample_r),
            ]

            # all mics run off the same clock so we only need to grab the new
            # sample flag from the first mic
            if mi == 0:
                m.d.comb += sample_new.eq(mic_rx.sample_new)

        # shift out all microphone data in sequence through the buffer
        sample_buf = Signal(NUM_MICS*MIC_DATA_BITS)
        buf_out = sample_buf[:MIC_DATA_BITS] # we shift the lower bits out

        mic_counter = Signal(range(NUM_MICS-1))
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(sample_new):
                    # latch all microphone data into the sample buffer
                    for mi in range(0, NUM_MICS):
                        m.d.sync += sample_buf.word_select(
                            mi, MIC_DATA_BITS).eq(sample_out[mi])
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
                        sample_buf.eq(sample_buf >> MIC_DATA_BITS),
                        mic_counter.eq(mic_counter-1),
                    ]

                    with m.If(mic_counter == 0): # last mic
                        m.d.sync += self.samples.valid.eq(0)
                        m.next = "IDLE"

        # run buffer output sample through gain processor (which is fully
        # combinatorial) and hook it to output
        m.submodules.gain_processor = gain_processor = GainProcessor()
        m.d.comb += [
            gain_processor.sample_in.eq(buf_out),
            self.samples.data.eq(gain_processor.sample_out),

            gain_processor.gain.eq(self.gain),
        ]

        return m

class MicDemo(Component):
    mic_sck: Out(1)

    sample_l: Out(signed(MIC_DATA_BITS))
    sample_r: Out(signed(MIC_DATA_BITS))
    sample_new: Out(1)

    def elaborate(self, platform):
        m = Module()

        m.submodules.mic_clk = mic_clk = MicClockGenerator()
        m.submodules.mic_rcv = mic_rcv = MicDataReceiver()
        m.submodules.mic_l = mic_l = FakeMic("left", start=0xaa1000)
        m.submodules.mic_r = mic_r = FakeMic("right", start=0xaa2000)

        # wire clock to data receiver
        m.d.comb += [
            mic_rcv.mic_sck.eq(mic_clk.mic_sck),
            mic_rcv.mic_data_sof_sync.eq(mic_clk.mic_data_sof_sync),
        ]

        # wire mics up
        m.d.comb += [
            mic_l.mic_sck.eq(mic_clk.mic_sck),
            mic_r.mic_sck.eq(mic_clk.mic_sck),
            mic_l.mic_ws.eq(mic_clk.mic_ws),
            mic_r.mic_ws.eq(mic_clk.mic_ws),
            mic_rcv.mic_data_raw.eq(mic_l.mic_data_raw | mic_r.mic_data_raw),
        ]

        # wire demo outputs
        m.d.comb += [
            self.mic_sck.eq(mic_clk.mic_sck),

            self.sample_l.eq(mic_rcv.sample_l),
            self.sample_r.eq(mic_rcv.sample_r),
            self.sample_new.eq(mic_rcv.sample_new),
        ]

        return m

def demo():
    from amaranth.sim.core import Simulator
    from .constants import MIC_FREQ_HZ

    top = MicDemo()
    sim = Simulator(top)
    sim.add_clock(1/(MIC_FREQ_HZ*MicCapture.REL_FREQ), domain="sync")

    mod_traces = []
    for name in top.signature.members.keys():
        mod_traces.append(getattr(top, name))

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("mic_demo.vcd", "mic_demo.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until(1e-3, run_passive=True)

if __name__ == "__main__":
    demo()
