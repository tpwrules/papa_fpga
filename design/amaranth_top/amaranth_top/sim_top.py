from amaranth import *
from amaranth.lib.wiring import Interface, connect
from amaranth.sim.core import Simulator, Delay, Settle

from .top import Top
from .constants import MIC_FREQ_HZ
from .mic import MIC_FRAME_BITS, MIC_DATA_BITS
from .bus import FakeAudioRAMBusWriteReceiver

class SimTop(Elaboratable):
    def __init__(self):
        self.top = Top()

    def elaborate(self, platform):
        m = Module()

        m.submodules.top = top = self.top
        m.submodules.fake_rx = fake_rx = FakeAudioRAMBusWriteReceiver()

        connect(m, top.audio_ram, fake_rx.audio_ram)

        return m

def run_sim():
    sim_top = SimTop()
    top = sim_top.top
    sim = Simulator(sim_top)
    sim.add_clock(1/50e6, domain="sync")
    sim.add_clock(1/(2*MIC_FREQ_HZ*MIC_FRAME_BITS), domain="mic_capture")

    # feed some data to the mic after a bit
    def mic_proc():
        for _ in range(64):
            yield
        yield top.mic_data.eq(1)
        yield

    # request a buffer switch
    def switch_proc():
        for _ in range(3300):
            yield

        yield top.csr_bus.addr.eq(2)
        yield top.csr_bus.w_data.eq(1)
        yield top.csr_bus.w_stb.eq(1)
        yield
        yield top.csr_bus.w_stb.eq(0)
        yield

    sim.add_sync_process(mic_proc, domain="sync")
    sim.add_sync_process(switch_proc, domain="sync")

    mod_traces = []
    for name in top.signature.members.keys():
        t = getattr(top, name)
        if isinstance(t, Signal): mod_traces.append(t)

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("sim_top.vcd", "sim_top.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until((1/MIC_FREQ_HZ)*8, run_passive=True)

if __name__ == "__main__":
    run_sim()
