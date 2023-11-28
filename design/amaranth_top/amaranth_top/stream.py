from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Signature
from amaranth.lib.fifo import AsyncFIFO

from .constants import CAP_DATA_BITS

# sample data in the system
class SampleStream(Signature):
    def __init__(self):
        super().__init__({
            "data": Out(signed(CAP_DATA_BITS)),
            "first": Out(1), # first sample of the microphone set
            "new": Out(1), # new microphone data is
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
