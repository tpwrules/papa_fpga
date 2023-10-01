from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out

class Top(wiring.Component):
    clk50:      In(1)
    rst:        In(1)

    blink:      Out(1)

    def elaborate(self, platform):
        m = Module()

        # wire up main clock domain
        m.domains.sync = sync = ClockDomain(async_reset=True)
        m.d.comb += [
            sync.clk.eq(self.clk50),
            sync.rst.eq(self.rst),
        ]

        MAX_COUNT = int(25e6)
        counter = Signal(range(0, MAX_COUNT-1))
        with m.If(counter == MAX_COUNT-1):
            m.d.sync += counter.eq(0)
            m.d.sync += self.blink.eq(~self.blink)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        return m

def generate():
    import sys
    from pathlib import Path
    from amaranth.back import verilog
    from .platform import AbbreviatedIntelPlatform

    top = Top()
    with open(Path(sys.argv[1]), "w") as f:
        f.write(verilog.convert(top,
            platform=AbbreviatedIntelPlatform,
            name="amaranth_top",
            # prevent source paths from being written into the design, in
            # particular absolute paths!
            strip_internal_attrs=True,
        ))

if __name__ == "__main__":
    generate()
