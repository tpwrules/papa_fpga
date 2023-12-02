from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped

import numpy as np

from .constants import NUM_MICS, CAP_DATA_BITS, NUM_CHANS, NUM_TAPS
from .stream import SampleStream, SampleStreamFIFO

COEFF_BITS = 19 # multiplier supports 18x19 mode

class Convolver(wiring.Component):
    samples_i: In(SampleStream())
    samples_i_count: In(32)

    samples_o: Out(SampleStream())

    # frequency relative to the microphone sample frequency (i.e. multiply that
    # by this to get the expected operation frequency)
    # for each sample frequency we need to process all taps and all mics, so we
    # do that, plus 1% more to be sure we're always ahead of capture
    REL_FREQ = int(NUM_MICS * NUM_TAPS * 1.01)

    def __init__(self, coefficients):
        # coefficients as float values, we convert them to fixed point ourselves
        expected_shape = (NUM_CHANS, NUM_TAPS, NUM_MICS)
        if coefficients.shape != expected_shape:
            raise ValueError(
                f"shape {coefficients.shape} != expected {expected_shape}")

        self._coefficients = np.empty(expected_shape, dtype=np.float64)
        np.copyto(self._coefficients, coefficients)

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        connect(m, flipped(self.samples_i), flipped(self.samples_o))
        m.d.comb += self.samples_i.ready.eq(1)

        return m

class ConvolverDemo(wiring.Component):
    samp_i: Out(signed(CAP_DATA_BITS))
    samp_i_first: Out(1)

    samp_o: Out(signed(CAP_DATA_BITS))
    samp_o_first: Out(1)

    def __init__(self, coefficients):
        self._coefficients = coefficients

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # set up FIFO to hold samples for convolver input and output
        m.submodules.sample_i_fifo = sample_i_fifo = SampleStreamFIFO(
            w_domain="sync", r_domain="convolver", depth=2*NUM_MICS)
        m.submodules.sample_o_fifo = sample_o_fifo = SampleStreamFIFO(
            w_domain="convolver", r_domain="sync", depth=2*NUM_MICS)

        # set up convolver
        m.submodules.convolver = convolver = \
            DomainRenamer("convolver")(Convolver(self._coefficients))
        connect(m, sample_i_fifo.samples_r, convolver.samples_i)
        connect(m, convolver.samples_o, sample_o_fifo.samples_w)
        m.d.comb += convolver.samples_i_count.eq(sample_i_fifo.samples_count)

        # generate increasing samples forever sort of like the fake mics
        # (our sync domain runs at MIC_FREQ_HZ*NUM_MICS so a new sample every
        # cycle)
        curr_sample = Signal(signed(CAP_DATA_BITS))
        mic_index = Signal(range(NUM_MICS-1))
        m.d.comb += [
            sample_i_fifo.samples_w.first.eq(mic_index == 0),
            sample_i_fifo.samples_w.valid.eq(1),
            sample_i_fifo.samples_w.data.eq(curr_sample),
        ]
        m.d.sync += [
            curr_sample.eq(curr_sample + 1),
            mic_index.eq(mic_index + 1),
        ]
        with m.If(mic_index == NUM_MICS-1):
            m.d.sync += mic_index.eq(0)

        # set up testbench outputs
        m.d.comb += [
            self.samp_i.eq(sample_i_fifo.samples_w.data),
            self.samp_i_first.eq(sample_i_fifo.samples_w.first),
            self.samp_o.eq(Mux(sample_o_fifo.samples_r.valid,
                sample_o_fifo.samples_r.data, 0)),
            self.samp_o_first.eq(
                sample_o_fifo.samples_r.first & sample_o_fifo.samples_r.valid),
            sample_o_fifo.samples_r.ready.eq(1)
        ]

        return m

def demo():
    global NUM_CHANS

    from amaranth.sim.core import Simulator

    from .constants import MIC_FREQ_HZ

    assert NUM_CHANS >= NUM_MICS
    NUM_CHANS = NUM_MICS # gross

    # for now generate coefficients that just copy the output to the input
    coefficients = np.zeros((NUM_CHANS, NUM_TAPS, NUM_MICS), dtype=np.float64)
    for x in range(NUM_CHANS):
        # for the most recent time, use mic x to get the output for chan x
        # and all others use 0
        coefficients[x, -1, x] = 1

    top = ConvolverDemo(coefficients)
    sim = Simulator(top)
    sim.add_clock(1/(MIC_FREQ_HZ*NUM_MICS), domain="sync")
    sim.add_clock(1/(MIC_FREQ_HZ*Convolver.REL_FREQ), domain="convolver")

    mod_traces = []
    for name in top.signature.members.keys():
        mod_traces.append(getattr(top, name))

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("convolve_demo.vcd", "convolve_demo.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until(10/(MIC_FREQ_HZ), run_passive=True)

if __name__ == "__main__":
    demo()
