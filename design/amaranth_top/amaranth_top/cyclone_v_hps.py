# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.
from amaranth import *
from amaranth.lib import wiring, enum
from amaranth.lib.wiring import In, Out

from .axi3 import AXI3Signature

class PortSize(enum.IntEnum, shape=2):
    BITS_32 = 0
    BITS_64 = 1
    BITS_128 = 2
    PORT_UNUSED = 3

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

    def __init__(self, port_size):
        self._port_size = port_size
        if port_size != PortSize.PORT_UNUSED:
            super().__init__(AXI3Signature(
                addr_width=32,
                data_width=(32, 64, 128)[port_size],
                id_width=8,
                user_width=dict(aw=5, ar=5),
            ).flip()) # HPS is the responder
        else:
            super().__init__({})

    def elaborate(self, platform):
        m = Module()

        clk = Signal()
        m.d.comb += clk.eq(ClockSignal())

        ports = [("i", "clk", clk), *self._get_axi_ports()]
        m.submodules[self._module] = Instance(self._module,
            ("i", "port_size_config", self._port_size),
            *(ports if self._port_size != PortSize.PORT_UNUSED else [])
        )

        return m

class _HPS2FPGA(AXI3Instance):
    _module = "cyclonev_hps_interface_hps2fpga"

    def __init__(self, port_size):
        self._port_size = port_size
        if port_size != PortSize.PORT_UNUSED:
            super().__init__(AXI3Signature(
                addr_width=30,
                data_width=(32, 64, 128)[port_size],
                id_width=12,
            ))
        else:
            super().__init__({})

    def elaborate(self, platform):
        m = Module()

        clk = Signal()
        m.d.comb += clk.eq(ClockSignal())

        ports = [("i", "clk", clk), *self._get_axi_ports()]
        m.submodules[self._module] = Instance(self._module,
            ("i", "port_size_config", self._port_size),
            *(ports if self._port_size != PortSize.PORT_UNUSED else [])
        )

        return m

class _HPS2FPGALW(AXI3Instance):
    _module = "cyclonev_hps_interface_hps2fpga_light_weight"

    def __init__(self):
        super().__init__(AXI3Signature(
            addr_width=21,
            data_width=32, # always 32 bits, just not instantiated if unused
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

    # Basic Usage
    # 1. Construct one instance of this class in your design
    # 2. Request various Elaboratables which represent various HPS
    #    ports/interfaces by calling request_...()
    # 3. Add this class as a submodule of your design only once all requests are
    #    complete (i.e. adding to m.submodules)
    # 4. Add requested Elaboratables as submodules of your design (hierarchy
    #    doesn't matter, can be done before step 3)
    # Note: Any requested Elaboratable can be placed in any clock domain; the
    #       HPS handles clock domain crossing internally

    def __init__(self):
        # once elaborated, no further requests can be made
        self._elaborated = False

        self._f2h_requested = False
        self._h2f_requested = False
        self._h2f_lw_requested = False

        super().__init__()

    def request_fpga2hps_port(self, data_width):
        # request the FPGA -> HPS port with a data width of 32, 64, or 128 bits

        if self._elaborated:
            raise ValueError("already elaborated, no more requests possible")
        if self._f2h_requested:
            raise ValueError("port already requested")
        self._f2h_requested = True

        if data_width == 32 or data_width == 64 or data_width == 128:
            port_size = getattr(PortSize, f"BITS_{data_width}")
        else:
            raise ValueError(f"unsupported data_width {data_width}")

        return _FPGA2HPS(port_size)

    def request_hps2fpga_port(self, data_width):
        # request the HPS -> FPGA port with a data width of 32, 64, or 128 bits

        if self._elaborated:
            raise ValueError("already elaborated, no more requests possible")
        if self._h2f_requested:
            raise ValueError("port already requested")
        self._h2f_requested = True

        if data_width == 32 or data_width == 64 or data_width == 128:
            port_size = getattr(PortSize, f"BITS_{data_width}")
        else:
            raise ValueError(f"unsupported data_width {data_width}")

        return _HPS2FPGA(port_size)

    def request_hps2fpga_lw_port(self):
        # request the HPS -> FPGA lightweight port

        if self._elaborated:
            raise ValueError("already elaborated, no more requests possible")
        if self._h2f_lw_requested:
            raise ValueError("port already requested")
        self._h2f_lw_requested = True

        return _HPS2FPGALW()

    def elaborate(self, platform):
        m = Module()

        self._elaborated = True

        # needed to avoid a Quartus bug, see class comments
        m.submodules.hps_dummy = _HPSDummy()

        # hps <-> fpga resets (no clocks that we can see...)
        m.submodules.clocks_resets = clocks_resets = _ClocksResets()
        m.d.comb += self.h2f_rst.eq(~clocks_resets.h2f_rst_n)

        # modules we don't expose yet but that are always created by Qsys
        m.submodules.dbg_apb = _DbgApb()
        m.submodules.tpiu_trace = _TpiuTrace()
        m.submodules.boot_from_fpga = _BootFromFPGA()
        m.submodules.fpga2sdram = _FPGA2SDRAM()

        # hps2fpga and fpga2hps must be instantiated as unused if not requested
        if not self._f2h_requested:
            m.submodules.fpga2hps_unused = _FPGA2HPS(PortSize.PORT_UNUSED)
        if not self._h2f_requested:
            m.submodules.hps2fpga_unused = _HPS2FPGA(PortSize.PORT_UNUSED)
        # lightweight doesn't need to be instantiated as unused

        return m
