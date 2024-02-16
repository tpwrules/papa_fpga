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

class _DbgApb(AutoInstance):
    _module = "cyclonev_hps_interface_dbg_apb"

    DBG_APB_DISABLE: In(1)
    P_CLK_EN: In(1)

class _TpiuTrace(AutoInstance):
    _module = "cyclonev_hps_interface_tpiu_trace"

    traceclk_ctl: In(1, init=1)

class _BootFromFPGA(AutoInstance):
    _module = "cyclonev_hps_interface_boot_from_fpga"

    boot_from_fpga_ready: In(1)
    boot_from_fpga_on_failure: In(1)
    bsel_en: In(1)
    csel_en: In(1)
    csel: In(2, init=1) # not sure of meaning
    bsel: In(3, init=1) # not sure of meaning

class _HPS2FPGA(AutoInstance):
    _module = "cyclonev_hps_interface_hps2fpga"

    port_size_config: In(2, init=3) # 3 == disabled?

class _FPGA2SDRAM(AutoInstance):
    _module = "cyclonev_hps_interface_fpga2sdram"

    cfg_cport_rfifo_map: In(18)
    cfg_axi_mm_select: In(6)
    cfg_wfifo_cport_map: In(16)
    cfg_cport_type: In(12)
    cfg_rfifo_cport_map: In(16)
    cfg_port_width: In(12)
    cfg_cport_wfifo_map: In(18)

class CycloneVHPS(wiring.Component):
    h2f_rst: Out(1)

    def elaborate(self, platform):
        m = Module()

        # not sure if mandatory
        m.submodules.clocks_resets = clocks_resets = _ClocksResets()
        m.d.comb += self.h2f_rst.eq(~clocks_resets.h2f_rst_n)

        # not sure if mandatory
        m.submodules.dbg_apb = _DbgApb()

        # not sure if mandatory
        m.submodules.tpiu_trace = _TpiuTrace()

        # not sure if mandatory
        m.submodules.boot_from_fpga = _BootFromFPGA()

        # not sure if mandatory
        m.submodules.hps2fpga = _HPS2FPGA()

        # not sure if mandatory
        m.submodules.fpga2sdram = _FPGA2SDRAM()

        return m
