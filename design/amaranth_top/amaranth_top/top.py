from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member
from amaranth.lib.cdc import ResetSynchronizer

class Top(wiring.Component):
    blink:      Out(1)

    def elaborate(self, platform):
        m = Module()

        MAX_COUNT = int(25e6)
        counter = Signal(range(0, MAX_COUNT-1))
        with m.If(counter == MAX_COUNT-1):
            m.d.sync += counter.eq(0)
            m.d.sync += self.blink.eq(~self.blink)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        return m

# take the signature from the given class and add it to the decorated class
def merge_signature(src_cls):
    def do(dest_cls):
        for n, v in src_cls.__annotations__.items():
            if isinstance(v, Member):
                dest_cls.__annotations__[n] = v

        return dest_cls

    return do

@merge_signature(Top)
class FPGATop(wiring.Component):
    clk50:      In(1)
    rst:        In(1)

    def elaborate(self, platform):
        m = Module()

        # wire up main clock domain
        m.domains.sync = sync = ClockDomain()
        m.d.comb += sync.clk.eq(self.clk50)

        m.submodules += ResetSynchronizer(self.rst)

        # wire up top module
        m.submodules.top = top = Top()
        for name, member in top.signature.members.items():
            if member.flow == In:
                m.d.comb += getattr(top, name).eq(getattr(self, name))
            elif member.flow == Out:
                m.d.comb += getattr(self, name).eq(getattr(top, name))
            else:
                raise ValueError("bad flow")

        return m

def generate():
    import sys
    from pathlib import Path
    from amaranth.back import verilog
    from .platform import AbbreviatedIntelPlatform

    top = FPGATop()
    with open(Path(sys.argv[1]), "w") as f:
        f.write(verilog.convert(top,
            platform=AbbreviatedIntelPlatform(),
            name="amaranth_top",
            # prevent source paths from being written into the design, in
            # particular absolute paths!
            strip_internal_attrs=True,
        ))

if __name__ == "__main__":
    generate()
