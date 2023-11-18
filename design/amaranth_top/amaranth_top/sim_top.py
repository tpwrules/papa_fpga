from amaranth import *
from amaranth.lib.wiring import Interface
from amaranth.sim.core import Simulator, Delay, Settle

from .top import Top
from .constants import MIC_FREQ_HZ
from .mic import MIC_FRAME_BITS, MIC_DATA_BITS

def run_sim():
    top = Top()
    sim = Simulator(top)
    sim.add_clock(1/50e6, domain="sync")
    sim.add_clock(1/(2*MIC_FREQ_HZ*MIC_FRAME_BITS), domain="mic_capture")

    # feed some data to the mic after a bit
    def mic_proc():
        for _ in range(64):
            yield
        yield top.mic_data.eq(1)
        yield

    sim.add_sync_process(mic_proc, domain="sync")

    mod_traces = []
    for name in top.signature.members.keys():
        t = getattr(top, name)
        if not isinstance(t, Interface): mod_traces.append(t)

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("sim_top.vcd", "sim_top.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until((1/MIC_FREQ_HZ)*8, run_passive=True)

if __name__ == "__main__":
    run_sim()
