from amaranth import *
from amaranth.lib.wiring import Component, In, Out, connect, flipped
from amaranth.utils import ceil_log2

import numpy as np

from .constants import NUM_MICS, CAP_DATA_BITS, NUM_CHANS, NUM_TAPS
from .stream import SampleStream, SampleStreamFIFO

COEFF_BITS = 19 # multiplier supports 18x19 mode

# generate the signals for all the channel blocks and store the sample data
class Sequencer(Component):
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
        mem_size = 1 << ceil_log2(NUM_TAPS * NUM_MICS)
        sample_memory = Memory(width=CAP_DATA_BITS, depth=mem_size)
        m.submodules.samp_w = samp_w = sample_memory.write_port()
        m.submodules.samp_r = samp_r = sample_memory.read_port(
            transparent=False)

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

# Cyclone V DSP block which does what we want and hopefully gets inferred
# properly
class DSPMACBlock(Component):
    # using 18x19 mode

    mul_a: In(signed(18)) # A input is 18 bits
    mul_b: In(signed(19)) # B input is 19 bits
    result: Out(signed(64)) # result is from 64 bit accumulator

    clear: In(1) # synchronously clear the accumulator (else accumulate)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.clear):
            m.d.sync += self.result.eq(0)
        with m.Else():
            m.d.sync += self.result.eq(self.result +
                (self.mul_a * self.mul_b))

        return m

class ChannelProcessor(Component):
    clear_accum: In(1) # if 1 then clear, else accumulate
    curr_sample: In(signed(CAP_DATA_BITS))
    coeff_index: In(range((NUM_TAPS * NUM_MICS)-1))

    sample_out: Out(signed(CAP_DATA_BITS))
    sample_new: Out(1) # pulsed when new sample data is available

    def __init__(self, coefficients):
        # coefficients as float values, we convert them to fixed point ourselves
        expected_shape = (NUM_TAPS, NUM_MICS)
        if coefficients.shape != expected_shape:
            raise ValueError(
                f"shape {coefficients.shape} != expected {expected_shape}")

        assert CAP_DATA_BITS <= 18 # DSP A input
        assert COEFF_BITS <= 19 # DSP B input

        # coefficients are all -1 to 1 and the sum of the coefficients is
        # (just about) exactly the number of microphones. we need 2 integer
        # bits for the coefficients, 1 for sign and 1 to accommodate
        # coefficients just slightly more than abs(1). the rest we can make
        # fraction bits. the input and output data we treat as fully integer,
        # but we need to divide by the number of microphones too
        coeff_frac_bits = COEFF_BITS-2

        # we can do most of the division by the number of mics by throwing
        # away bits, but we have to do the rest by scaling the coefficients.
        # compute the number of bits to throw away (which will be too few)
        # then reduce the coefficients to do the rest.
        num_mic_bits = ceil_log2(NUM_MICS) # could be too many
        if NUM_MICS == 1 << num_mic_bits:
            num_mic_frac = 1 # don't need to scale coefficients
        else:
            num_mic_bits -= 1 # reduce to throw away too few
            num_mic_frac = (1<<num_mic_bits)/NUM_MICS # then scale coeffs

        # we want the output to be integral so we throw away the fractional bits
        # from the coefficients too
        self._trunc_bits = num_mic_bits + coeff_frac_bits

        # multiplication of CAP_DATA_BITS.0 * 2.COEFF_BITS-2 equals
        # (CAP_DATA_BITS+2).(COEFF_BITS-2) or a total bit quantity of
        # CAP_DATA_BITS+COEFF_BITS. we intend to sum NUM_TAPS*NUM_MICS
        # of them, so we need enough bits for that too
        total_bits = CAP_DATA_BITS + COEFF_BITS + ceil_log2(NUM_TAPS * NUM_MICS)
        assert total_bits <= 64 # accumulator size

        # scale coefficients to do the rest of the division by num_mics
        coefficients = coefficients * num_mic_frac
        # convert coefficients to signed fixed point with the given number of
        # fractional bits
        coefficients = (coefficients * (1 << coeff_frac_bits)).astype(np.int64)
        # make sure they're all in range
        assert np.all(np.abs(coefficients) < (1 << (COEFF_BITS-1)))
        # mask to convert to unsigned values
        coefficients &= (1 << COEFF_BITS)-1

        # save as a list for Amaranth
        self._coeff_rom_data = [int(v) for v in coefficients.reshape(-1)]

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # re-register control and data signals to improve timing
        clear_accum = Signal.like(self.clear_accum)
        curr_sample = Signal.like(self.curr_sample)
        coeff_index = Signal.like(self.coeff_index)
        m.d.sync += [
            clear_accum.eq(self.clear_accum),
            curr_sample.eq(self.curr_sample),
            coeff_index.eq(self.coeff_index),
        ]

        # RAM to hold coefficients
        mem_size = 1 << ceil_log2(NUM_TAPS * NUM_MICS)
        coeff_memory = Memory(
            width=COEFF_BITS, depth=mem_size, init=self._coeff_rom_data)
        m.submodules.coeff_r = coeff_r = coeff_memory.read_port(
            transparent=False)
        m.d.comb += [
            coeff_r.en.eq(1), # always reading
            coeff_r.addr.eq(coeff_index), # from the given index
        ]

        # set up DSP block to do our multiply-accumulate
        m.submodules.mac = mac = DSPMACBlock()
        # memory delays by one cycle and we put the coefficient in the B port
        # since that's one bit wider and we want that extra bit
        m.d.sync += mac.mul_a.eq(curr_sample)
        m.d.comb += mac.mul_b.eq(coeff_r.data)
        # clear is in effect synchronous since we are using that to delay
        m.d.sync += mac.clear.eq(clear_accum)

        # hook up (truncated) output
        m.d.comb += self.sample_out.eq(mac.result[self._trunc_bits:])
        # and synchronized new flag (which is the cycle the clear input of the
        # accumulator is asserted)
        sample_new = Signal()
        m.d.comb += sample_new.eq(~mac.clear & clear_accum)
        m.d.sync += self.sample_new.eq(sample_new)

        return m

class Convolver(Component):
    samples_i: In(SampleStream())
    samples_i_count: In(32)

    samples_o: Out(SampleStream())

    # frequency relative to the microphone sample frequency (i.e. multiply that
    # by this to get the expected operation frequency)
    # for each sample frequency we need to process all taps and all mics then
    # clear the accumulators, so we do that, plus 1% more to be sure we're
    # always ahead of capture
    REL_FREQ = int(((NUM_MICS * NUM_TAPS)+1)*1.01)

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

        # wire up channel processors
        sample_out = []
        sample_new = Signal()
        for ci in range(0, NUM_CHANS):
            processor = ChannelProcessor(self._coefficients[ci])
            m.submodules[f"processor_{ci}"] = processor

            this_sample = Signal(signed(CAP_DATA_BITS), name=f"sample_{ci}")
            sample_out.append(this_sample)

            m.d.comb += [
                processor.clear_accum.eq(sequencer.clear_accum),
                processor.curr_sample.eq(sequencer.curr_sample),
                processor.coeff_index.eq(sequencer.coeff_index),
                this_sample.eq(processor.sample_out),
            ]

            # all processors run off the same clock so we only need to grab the
            # new sample flag from the first one
            if ci == 0:
                m.d.comb += sample_new.eq(processor.sample_new)

        # shift out all the sample data in sequence through the buffer
        sample_buf = Signal(NUM_CHANS*CAP_DATA_BITS)
        # we shift the lower bits out
        m.d.comb += self.samples_o.data.eq(sample_buf[:CAP_DATA_BITS])

        chan_counter = Signal(range(NUM_CHANS-1))
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(sample_new):
                    # latch all the processed data into the sample buffer
                    for ci in range(0, NUM_CHANS):
                        m.d.sync += sample_buf.word_select(
                            ci, CAP_DATA_BITS).eq(sample_out[ci])
                    m.d.sync += [
                        chan_counter.eq(NUM_CHANS-1), # reset output counter
                        self.samples_o.first.eq(1), # prime first output flag
                        self.samples_o.valid.eq(1), # notify about new samples
                    ]
                    m.next = "OUTPUT"

            with m.State("OUTPUT"):
                with m.If(self.samples_o.valid & self.samples_o.ready):
                    # remaining samples are not the first
                    m.d.sync += self.samples_o.first.eq(0)

                    # shift out processed data
                    m.d.sync += [
                        sample_buf.eq(sample_buf >> CAP_DATA_BITS),
                        chan_counter.eq(chan_counter-1),
                    ]

                    with m.If(chan_counter == 0): # last channel
                        m.d.sync += self.samples_o.valid.eq(0)
                        m.next = "IDLE"

        return m

class ConvolverDemo(Component):
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
        # make each output channel an average of all the input mics
        coefficients[x, -1, :] = 1

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
