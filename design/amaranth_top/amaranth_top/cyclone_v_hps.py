from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class AutoInstance(wiring.Component):
    def elaborate(self, platform):
        m = Module()

        sigs = []
        for name, kind in self.__annotations__.items():
            if kind.flow == In:
                kind = "i"
            elif kind.flow == Out:
                kind = "o"
            sigs.append((kind, name, getattr(self, name)))

        m.submodules[self._module] = Instance(self._module, *sigs)

        return m

class _ClocksResets(AutoInstance):
    _module = "cyclonev_hps_interface_clocks_resets"

    f2h_pending_rst_ack: In(1, init=1)
    f2h_warm_rst_req_n: In(1, init=1)
    f2h_dbg_rst_req_n: In(1, init=1)
    h2f_rst_n: Out(1)
    f2h_cold_rst_req_n: In(1, init=1)

class CycloneVHPS(wiring.Component):
    h2f_rst: Out(1)

    def elaborate(self, platform):
        m = Module()

        # not sure if mandatory
        m.submodules.clocks_resets = clocks_resets = _ClocksResets()
        m.d.comb += self.h2f_rst.eq(~clocks_resets.h2f_rst_n)

        return m
