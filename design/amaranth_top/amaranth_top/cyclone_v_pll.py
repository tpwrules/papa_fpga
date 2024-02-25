# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.

# from galibert in #amaranth-lang 2023-11-07
# https://libera.irclog.whitequark.org/amaranth-lang/2023-11-07#35193230;
# https://libera.irclog.whitequark.org/amaranth-lang/2024-02-16#1708056915-1708067745;
from amaranth import *

class IntelPLL(Elaboratable):
    def __init__(self, freq):
        self.o_locked = Signal()
        self.freq = freq
        self.output_signals = []
        self.output_configs = []
        
    def add_output(self, freq, phase = "0 ps", cycle = 50):
        out = Signal()
        self.output_signals.append(out)
        self.output_configs.append([freq, phase, cycle])
        return out

    def elaborate(self, platform):
        m = Module()
        params = {
            'i_refclk': ClockSignal("sync"),
            'i_rst': ResetSignal("sync"),
            'i_fbclk': 1,
            'o_locked': self.o_locked,
            'o_outclk': Cat(self.output_signals),
            'p_reference_clock_frequency': self.freq,
            'p_number_of_clocks': "%d" % len(self.output_configs),
            'p_fractional_vco_multiplier': 'false',
            'p_operation_mode': 'normal',
            'p_pll_type': 'General',
            'p_pll_subtype': 'General'
            }
        for i, o in enumerate(self.output_configs):
            params['p_output_clock_frequency%d' % i] = self.output_configs[i][0]
            params['p_phase_shift%d' % i] = self.output_configs[i][1]
            params['p_duty_cycle%d' % i] = "%d" % self.output_configs[i][2]
        m.submodules.pll = Instance("altera_pll", **params)
        return m
