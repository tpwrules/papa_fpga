from amaranth import *

def Rose(m, s):
    assert len(s) == 1

    # avoid false triggering on first cycle of design if signal starts high
    last = Signal(1, reset=1)
    m.d.sync += last.eq(s)

    return ~last & s

def Fell(m, s):
    assert len(s) == 1

    # avoid false triggering on first cycle of design if signal starts low
    last = Signal(1, reset=0)
    m.d.sync += last.eq(s)

    return last & ~s
