from amaranth import *

# delay (by default the same length as FFSynchronizer) that doesn't do any CDC
class FFDelay(Elaboratable):
    def __init__(self, i, o, *, reset=0, cycles=2):
        self.i = i
        self.o = o

        self._reset = reset
        self._cycles = cycles

    def elaborate(self, platform):
        m = Module()

        flops = [Signal(self.i.shape(), name=f"stage{index}", reset=self._reset)
            for index in range(self._cycles)]
        for i, o in zip((self.i, *flops), flops):
            m.d.sync += o.eq(i)
        m.d.comb += self.o.eq(flops[-1])

        return m
