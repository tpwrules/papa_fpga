import unittest

from amaranth import *
from amaranth.sim.core import Simulator, Delay, Settle

from .top import Top

class Test(unittest.TestCase):
    def test_led(self):
        top = Top()
        sim = Simulator(top)
        sim.add_clock(1/50e6, domain="sync")

        mod_traces = []
        for name in top.signature.members.keys():
            mod_traces.append(getattr(top, name))

        clk_hack = sim._fragment.domains["sync"].clk
        with sim.write_vcd("out.vcd", "out.gtkw",
                traces=[clk_hack, *mod_traces]):
            sim.run_until(1e-6, run_passive=True)

if __name__ == "__main__":
    unittest.main()
