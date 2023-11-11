from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.cdc import FFSynchronizer
from amaranth.sim.core import Simulator, Delay, Settle

class MicClockGenerator(wiring.Component):
    # generate the microphone clock suitable for wiring to the microphone's
    # input pins. the generated clock is half the module clock. the cycle
    # output represents the current input data cycle; it is delayed with
    # FFSynchronizers so it is synchronous with input data.
    mic_sck: Out(1)
    mic_ws: Out(1)
    cycle: Out(range(64))

    def elaborate(self, platform):
        m = Module()

        # local non-delayed cycle counter
        cycle = Signal(range(64))

        # toggle clock
        m.d.sync += self.mic_sck.eq(~self.mic_sck)
        # bump the cycle counter on the positive edge of the mic cycle
        with m.If(~self.mic_sck):
            m.d.sync += cycle.eq(cycle + 1)

        # lower word select on falling edge before cycle start
        with m.If((cycle == 63) & self.mic_sck):
            m.d.sync += self.mic_ws.eq(0)
        # raise word select on falling edge before second half of cycle
        with m.If((cycle == 31) & self.mic_sck):
            m.d.sync += self.mic_ws.eq(1)

        # generate delayed cycle counter for input modules
        m.submodules += FFSynchronizer(cycle, self.cycle)

        return m

def demo():
    mic = MicClockGenerator()
    sim = Simulator(mic)
    sim.add_clock(1/(2*48000*64), domain="sync")

    mod_traces = []
    for name in mic.signature.members.keys():
        mod_traces.append(getattr(mic, name))

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("mic_demo.vcd", "mic_demo.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until(1e-3, run_passive=True)

if __name__ == "__main__":
    demo()
