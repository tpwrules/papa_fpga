# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.
from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from .axi3 import AXI3Signature

class SignatureInstance(wiring.Component):
    def elaborate(self, platform):
        ports = []
        for name, member in self.signature.members.items():
            if not member.is_port:
                raise ValueError(f"member {name} is not a port")
            ports.append(("i" if member.flow == In else "o",
                name, getattr(self, name)))

        return Instance(self._module, *ports)

class AXI3Instance(wiring.Component):
    def _get_axi_ports(self):
        ports = []

        # add all the AXI ports to the ports list
        for cn, chan in self.signature.members.items():
            for pn, port in chan.signature.members.items():
                ports.append(("i" if port.flow == In else "o",
                    f"{cn}{pn}", getattr(getattr(self, cn), pn)))

        return ports

class _ClocksResets(SignatureInstance):
    _module = "cyclonev_hps_interface_clocks_resets"

    f2h_pending_rst_ack: In(1, init=1)
    f2h_warm_rst_req_n: In(1, init=1)
    f2h_dbg_rst_req_n: In(1, init=1)
    h2f_rst_n: Out(1)
    f2h_cold_rst_req_n: In(1, init=1)

class _DbgApb(SignatureInstance):
    _module = "cyclonev_hps_interface_dbg_apb"

    DBG_APB_DISABLE: In(1)
    P_CLK_EN: In(1)

class _TpiuTrace(SignatureInstance):
    _module = "cyclonev_hps_interface_tpiu_trace"

    traceclk_ctl: In(1, init=1)

class _BootFromFPGA(SignatureInstance):
    _module = "cyclonev_hps_interface_boot_from_fpga"

    boot_from_fpga_ready: In(1)
    boot_from_fpga_on_failure: In(1)
    bsel_en: In(1)
    csel_en: In(1)
    csel: In(2, init=1) # not sure of meaning
    bsel: In(3, init=1) # not sure of meaning

class _HPS2FPGA(SignatureInstance):
    _module = "cyclonev_hps_interface_hps2fpga"

    port_size_config: In(2, init=3) # 3 == disabled?

class _FPGA2SDRAM(SignatureInstance):
    _module = "cyclonev_hps_interface_fpga2sdram"

    cfg_cport_rfifo_map: In(18)
    cfg_axi_mm_select: In(6)
    cfg_wfifo_cport_map: In(16)
    cfg_cport_type: In(12)
    cfg_rfifo_cport_map: In(16)
    cfg_port_width: In(12)
    cfg_cport_wfifo_map: In(18)

class _FPGA2HPS(AXI3Instance):
    _module = "cyclonev_hps_interface_fpga2hps"

    def __init__(self):
        super().__init__(AXI3Signature(
            addr_width=32,
            data_width=32,
            id_width=8,
            user_width=dict(aw=5, ar=5),
        ).flip()) # HPS is the responder

    def elaborate(self, platform):
        m = Module()

        clk = Signal()
        m.d.comb += clk.eq(ClockSignal())

        m.submodules[self._module] = Instance(self._module, *(
            # 0 == 32 bits, 3 == disabled?
            ("i", "port_size_config", Signal(2, init=0)),
            ("i", "clk", clk),
            *self._get_axi_ports(),
        ))

        return m

class _HPS2FPGALW(AXI3Instance):
    _module = "cyclonev_hps_interface_hps2fpga_light_weight"

    def __init__(self):
        super().__init__(AXI3Signature(
            addr_width=21,
            data_width=32,
            id_width=12,
        ))

    def elaborate(self, platform):
        m = Module()

        clk = Signal()
        m.d.comb += clk.eq(ClockSignal())

        m.submodules[self._module] = Instance(self._module, *(
            ("i", "clk", clk),
            *self._get_axi_ports(),
        ))

        return m

# there must be an assignment in the .qsf of the form
#   'set_instance_assignment -name hps_partition on -entity <x>'
# this stops quartus (20.1.1.720) whining about
#   'Warning (330000): Timing-Driven Synthesis is skipped because it could not
#    initialize the timing netlist'
# <x> just has to point to an extant entity; that entity doesn't even have to
# contain any logic (but in the qsys files that entity would be
# the "soc_system_hps_0_hps_io_border" entity that has the SDRAM and other I/O
# ports like USB and Ethernet)
class _HPSDummy(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        platform.add_file("hps_secret_dummy_partition_module.v",
            "module hps_secret_dummy_partition_module(); endmodule")

        m.submodules += Instance("hps_secret_dummy_partition_module")

        return m

class CycloneVHPS(wiring.Component):
    h2f_rst: Out(1)

    def __init__(self):
        self.f2h_axi_s0 = _FPGA2HPS()
        self.h2f_lw = _HPS2FPGALW()

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # definitely mandatory
        m.submodules.hps_dummy = _HPSDummy()

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

        # not sure if mandatory
        m.submodules.fpga2hps = self.f2h_axi_s0

        # not mandatory
        m.submodules.hps2fpga_light_weight = self.h2f_lw

        return m
