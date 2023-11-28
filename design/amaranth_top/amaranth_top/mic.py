from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.cdc import FFSynchronizer
from amaranth.sim.core import Simulator, Delay, Settle

from .constants import MIC_FREQ_HZ, NUM_MICS, USE_FAKE_MICS, CAP_DATA_BITS
from .stream import SampleStream

MIC_DATA_BITS = 24 # each word is a signed 24 bit number
MIC_FRAME_BITS = 64 # 64 data bits per data frame from the microphone

class MicClockGenerator(wiring.Component):
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
        # generate delayed start of frame pulse for input modules
        m.submodules += FFSynchronizer(mic_data_sof, self.mic_data_sof_sync)

        return m

class MicDataReceiver(wiring.Component):
    # receive data from a microphone
    mic_sck: In(1)
    mic_data: In(1)
    mic_data_sof_sync: In(1)

    sample_l: Out(signed(MIC_DATA_BITS))
    sample_r: Out(signed(MIC_DATA_BITS))
    sample_new: Out(1) # pulsed when new sample data is available

    def elaborate(self, platform):
        m = Module()

        # synchronize mic data to module clock
        mic_data_sync = Signal()
        m.submodules += FFSynchronizer(self.mic_data, mic_data_sync)

        buffer = Signal(MIC_FRAME_BITS)
        # shift in new data on rising edge of clock into the MSB of buffer
        with m.If(self.mic_sck):
            m.d.sync += buffer.eq(Cat(buffer[1:], mic_data_sync))

        m.d.sync += self.sample_new.eq(0) # usually no data available
        # once the frame is over, save the data in the outputs
        with m.If(self.mic_data_sof_sync):
            m.d.sync += [
                self.sample_l.eq(buffer[1:1+MIC_DATA_BITS][::-1]),
                self.sample_r.eq(buffer[33:33+MIC_DATA_BITS][::-1]),
                self.sample_new.eq(1),
            ]

        return m

class FakeMic(wiring.Component):
    # fake microphone output data in accordance with timing diagrams
    # (assumes mic_sck is half "sync"'s clock rate)
    mic_sck: In(1)
    mic_ws: In(1)

    mic_data: Out(1)

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
                self.mic_data.eq(buffer[-1]),
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

class MicDemo(wiring.Component):
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
            mic_rcv.mic_data.eq(mic_l.mic_data | mic_r.mic_data),
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
    top = MicDemo()
    sim = Simulator(top)
    sim.add_clock(1/(2*MIC_FREQ_HZ*MIC_FRAME_BITS), domain="sync")

    mod_traces = []
    for name in top.signature.members.keys():
        mod_traces.append(getattr(top, name))

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("mic_demo.vcd", "mic_demo.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until(1e-3, run_passive=True)

if __name__ == "__main__":
    demo()
