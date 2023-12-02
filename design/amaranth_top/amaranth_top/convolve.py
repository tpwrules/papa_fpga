import math

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, connect, flipped
from amaranth.utils import log2_int

import numpy as np

from .constants import NUM_MICS, CAP_DATA_BITS, NUM_CHANS, NUM_TAPS
from .stream import SampleStream, SampleStreamFIFO

COEFF_BITS = 19 # multiplier supports 18x19 mode

# generate the signals for all the channel blocks and store the sample data
class Sequencer(wiring.Component):
    samples_i: In(SampleStream()) # sample data to process
    samples_i_count: In(32)

    # control and data signals to processing blocks
    clear_accum: Out(1) # if 1 then clear, else accumulate
    curr_sample: Out(signed(CAP_DATA_BITS))
    coeff_index: Out(range((NUM_TAPS * NUM_MICS)-1))

    def elaborate(self, platform):
        m = Module()

        # control and data signals are sent to the output bus synchronously to
        # improve timing
        clear_accum = Signal.like(self.clear_accum)
        curr_sample = Signal.like(self.curr_sample)
        coeff_index = Signal.like(self.coeff_index)
        m.d.sync += [
            self.clear_accum.eq(clear_accum),
            self.curr_sample.eq(curr_sample),
            self.coeff_index.eq(coeff_index),
        ]

        # memory to store sample data
        # storage must be a power of two so that Quartus will infer BRAM
        mem_size = 1 << log2_int(NUM_TAPS * NUM_MICS, need_pow2=False)
        sample_memory = Memory(width=CAP_DATA_BITS, depth=mem_size)
        m.submodules.samp_w = samp_w = sample_memory.write_port()
        m.submodules.samp_r = samp_r = sample_memory.read_port()

        # read data is connected to the sample output and has a one cycle delay
        m.d.comb += curr_sample.eq(samp_r.data)
        # write data does not have a delay, but we might write what we read or
        # we might write new data
        write_new = Signal()
        m.d.comb += [
            samp_w.data.eq(Mux(write_new, self.samples_i.data, samp_r.data)),
            self.samples_i.ready.eq(write_new),
        ]

        # main sequencer state machine
        sample_num = Signal.like(coeff_index)
        m.d.sync += [ # by default...
            clear_accum.eq(1), # tell accumulators to clear themselves
            samp_w.en.eq(0), # not writing
        ]
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.samples_i.valid): # at least one sample
                    with m.If(~self.samples_i.first): # not the first sample?
                        m.d.comb += self.samples_i.ready.eq(1) # discard it
                    with m.Elif(self.samples_i_count >= NUM_MICS):
                        # we have a full set of samples (so we won't ever hit an
                        # invalid stream word) and the first sample is
                        # correctly flagged as the first
                        m.d.sync += sample_num.eq(0) # reset sample counter
                        m.next = "PROCESS"

            with m.State("PROCESS"):
                # are we on the first set of mics (and need to write new data)
                first_set = Signal()
                m.d.comb += first_set.eq(sample_num < NUM_MICS)

                # this cycle (combinatorially)
                m.d.comb += [
                    # read sample data
                    samp_r.addr.eq(sample_num),
                    samp_r.en.eq(1),
                ]
                # next cycle (synchronously)
                m.d.sync += [
                    # write sample data (first set of mics are new)
                    write_new.eq(first_set),
                    samp_w.addr.eq(Mux(first_set, # to the previous time block
                        sample_num + ((NUM_TAPS-1) * NUM_MICS),
                        sample_num - NUM_MICS)),
                    samp_w.en.eq(1),

                    # the read data will be available next cycle so update the
                    # coefficient index and tell accumulators to stop clearing
                    coeff_index.eq(sample_num),
                    clear_accum.eq(0),
                ]

                m.d.sync += sample_num.eq(sample_num + 1) # next sample
                with m.If(sample_num == (NUM_TAPS * NUM_MICS) - 1):
                    m.next = "IDLE" # done with the sequence

        return m

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

        # sequencer to generate sample numbers and store the data
        m.submodules.sequencer = sequencer = Sequencer()
        connect(m, flipped(self.samples_i), sequencer.samples_i)
        m.d.comb += sequencer.samples_i_count.eq(self.samples_i_count)

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
