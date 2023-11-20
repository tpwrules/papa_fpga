from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.cdc import FFSynchronizer
from amaranth.sim.core import Simulator, Delay, Settle

from .constants import MIC_FREQ_HZ

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
