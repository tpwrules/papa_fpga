from amaranth import *
from amaranth.lib import enum
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.fifo import SyncFIFO

from amaranth_soc import csr

# design goals:
#   * non horribly atrocious latency
#   * not horribly broken

class AXI3CSRBridge(Component):
    awid: In(12)
    awaddr: In(21)
    awlen: In(4)
    awsize: In(3)
    awburst: In(2)
    awlock: In(2)
    awcache: In(4)
    awprot: In(3)
    awvalid: In(1)
    awready: Out(1)
    wid: In(12)
    wdata: In(32)
    wstrb: In(4)
    wlast: In(1)
    wvalid: In(1)
    wready: Out(1)
    bid: Out(12)
    bresp: Out(2)
    bvalid: Out(1)
    bready: In(1)
    arid: In(12)
    araddr: In(21)
    arlen: In(4)
    arsize: In(3)
    arburst: In(2)
    arlock: In(2)
    arcache: In(4)
    arprot: In(3)
    arvalid: In(1)
    arready: Out(1)
    rid: Out(12)
    rdata: Out(32)
    rresp: Out(2)
    rlast: Out(1)
    rvalid: Out(1)
    rready: In(1)

    csr_bus: Out(csr.Signature(addr_width=8, data_width=32))

    def elaborate(self, platform):
        m = Module()

        # data read and write are rather independent of everything else, so just
        # hook them to a FIFO and let them operate independently. each can store
        # one max-sized burst.
        m.submodules.w_fifo = w_fifo = SyncFIFO(width=32, depth=16)
        m.submodules.r_fifo = r_fifo = SyncFIFO(width=32+3+12, depth=16)

        m.d.comb += [
            # interface to AXI side
            w_fifo.w_data.eq(self.wdata),
            w_fifo.w_en.eq(self.wvalid & self.wready),
            self.wready.eq(w_fifo.w_rdy),

            Cat(self.rdata, self.rid, self.rresp, self.rlast).eq(r_fifo.r_data),
            r_fifo.r_en.eq(self.rvalid & self.rready),
            self.rvalid.eq(r_fifo.r_rdy),

            # interface to CSR side
            self.csr_bus.w_data.eq(w_fifo.r_data),
            r_fifo.w_data.eq(self.csr_bus.r_data),
        ]

        # address read and write are independent on the AXI side, but only one
        # can occur on the CSR side. on the AXI side we have independent logic
        # to accept a transaction for each, then a big state machine to
        # actually process it through the CSR bus

        # write information and acceptance logic
        axi_wavail = Signal() # data is valid and write needs to be completed
        axi_wokay = Signal() # write transaction is valid (aligned, etc.)
        axi_waddr = Signal(21)
        axi_wlen = Signal(4)
        axi_wid = Signal(12)

        m.d.comb += self.awready.eq(~axi_wavail)
        with m.If(self.awready & self.awvalid):
            m.d.sync += [
                axi_wavail.eq(1),
                axi_waddr.eq(self.awaddr),
                axi_wlen.eq(self.awlen),
                axi_wid.eq(self.awid),
            ]
            with m.If((self.awsize == 0b010) # 4 bytes
                    & (self.awlock == 0) # not locked
                    & (self.awburst == 0b01) # increment burst
                    & (self.awaddr[:2] == 0)): # aligned
                m.d.sync += axi_wokay.eq(1)
            with m.Else():
                m.d.sync += axi_wokay.eq(0)

        # read information and acceptance logic
        axi_ravail = Signal() # data is valid and read needs to be completed
        axi_rokay = Signal() # read transaction is valid (aligned, etc.)
        axi_raddr = Signal(21)
        axi_rlen = Signal(4)
        axi_rid = Signal(12)

        m.d.comb += self.arready.eq(~axi_ravail)
        with m.If(self.arready & self.arvalid):
            m.d.sync += [
                axi_ravail.eq(1),
                axi_raddr.eq(self.araddr),
                axi_rlen.eq(self.arlen),
                axi_rid.eq(self.arid),
            ]
            with m.If((self.arlock == 0) # not locked
                    & (self.arburst == 0b01) # increment burst
                    & (self.araddr[:2] == 0)): # aligned
                m.d.sync += axi_rokay.eq(1)
            with m.Else():
                m.d.sync += axi_rokay.eq(0)

        # process reads and writes
        priority = Signal() # whether to do read or write if both possible
        wpossible = Signal() # operation information is available
        rpossible = Signal() # and the FIFO has enough data/space
        m.d.comb += [
            wpossible.eq(axi_wavail & (w_fifo.r_level > axi_wlen)),
            rpossible.eq(axi_ravail & (r_fifo.w_level < 16-axi_rlen)),
        ]

        # read bus is registered so we need to delay the FIFO signals
        r_fifo_w_en = Signal()
        r_fifo_rid = Signal(12)
        r_fifo_rresp = Signal(2)
        r_fifo_rlast = Signal()
        r_fifo_dataex = Signal(3+12)
        m.d.sync += [
            r_fifo.w_en.eq(r_fifo_w_en),
            r_fifo_dataex.eq(Cat(r_fifo_rid, r_fifo_rresp, r_fifo_rlast))
        ]
        m.d.comb += r_fifo.w_data.eq(Cat(self.csr_bus.r_data, r_fifo_dataex))

        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If((wpossible & ~rpossible)
                        | (wpossible & rpossible & priority)):
                    m.d.sync += priority.eq(~priority)
                    m.next = "WRITE"
                with m.Elif((~wpossible & rpossible)
                        | (wpossible & rpossible & ~priority)):
                    m.d.sync += priority.eq(~priority)
                    m.next = "READ"

            with m.State("WRITE"):
                m.d.comb += [
                    self.csr_bus.addr.eq(axi_waddr[2:]),
                    self.csr_bus.w_stb.eq(axi_wokay),
                    w_fifo.r_en.eq(1),
                ]
                m.d.sync += [
                    axi_waddr.eq(axi_waddr+4),
                    axi_wlen.eq(axi_wlen-1),
                ]
                with m.If(axi_wlen == 0):
                    m.next = "WRITE_DONE"

            with m.State("WRITE_DONE"):
                m.d.comb += [
                    self.bvalid.eq(1),
                    self.bid.eq(axi_wid),
                    self.bresp.eq(Mux(axi_wokay, 0, 0b10)), # target error
                ]
                with m.If(self.bready):
                    m.d.sync += axi_wavail.eq(0)
                    m.next = "IDLE"

            with m.State("READ"):
                m.d.comb += [
                    self.csr_bus.addr.eq(axi_raddr[2:]),
                    self.csr_bus.r_stb.eq(axi_rokay),
                    r_fifo_w_en.eq(1),
                    r_fifo_rid.eq(axi_rid),
                    r_fifo_rresp.eq(Mux(axi_rokay, 0, 0b10)), # target error
                ]
                m.d.sync += [
                    axi_raddr.eq(axi_raddr+4),
                    axi_rlen.eq(axi_rlen-1),
                ]
                with m.If(axi_rlen == 0):
                    m.d.comb += r_fifo_rlast.eq(1)
                    m.d.sync += axi_ravail.eq(0)
                    m.next = "IDLE"

        return m

class AXIDemo(Component):
    start: Out(1)

    addr: Out(8)
    r_data: Out(32)
    r_stb: Out(1)
    w_data: Out(32)
    w_stb: Out(1)

    def elaborate(self, platform):
        m = Module()

        m.submodules.bridge = bridge = AXI3CSRBridge()

        # write address state machine
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.start):
                    m.next = "AWVALID"

            with m.State("AWVALID"):
                m.d.comb += [
                    bridge.awaddr.eq(0),
                    bridge.awlen.eq(7), # 8 words
                    bridge.awsize.eq(0b010), # 4 bytes
                    bridge.awburst.eq(0b01), # increment burst
                    bridge.awvalid.eq(1),
                ]
                with m.If(bridge.awready):
                    m.next = "IDLE"

        # write data state machine
        write_remain = Signal(8)
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.start):
                    m.d.sync += write_remain.eq(7)
                    m.next = "WVALID"

            with m.State("WVALID"):
                m.d.comb += bridge.wvalid.eq(1)
                with m.If(bridge.wready):
                    m.d.sync += write_remain.eq(write_remain - 1)
                    with m.If(write_remain == 0):
                        m.next = "IDLE"

        # always ready for write response
        m.d.comb += bridge.bready.eq(1)

        # read address state machine
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.start):
                    m.next = "ARVALID"

            with m.State("ARVALID"):
                m.d.comb += [
                    bridge.araddr.eq(0),
                    bridge.arlen.eq(7), # 8 words
                    bridge.arsize.eq(0b010), # 4 bytes
                    bridge.arburst.eq(0b01), # increment burst
                    bridge.arvalid.eq(1),
                ]
                with m.If(bridge.arready):
                    m.next = "IDLE"

        # always ready for read data
        m.d.comb += bridge.rready.eq(1)

        # read and write something vaguely interesting
        m.d.comb += bridge.wdata.eq(69)
        m.d.sync += bridge.csr_bus.r_data.eq(bridge.csr_bus.addr)

        # wire demo outputs
        m.d.comb += [
            self.addr.eq(bridge.csr_bus.addr),
            self.r_data.eq(bridge.csr_bus.r_data),
            self.r_stb.eq(bridge.csr_bus.r_stb),
            self.w_data.eq(bridge.csr_bus.w_data),
            self.w_stb.eq(bridge.csr_bus.w_stb),
        ]

        return m

def demo():
    from amaranth.sim.core import Simulator

    top = AXIDemo()
    sim = Simulator(top)
    sim.add_clock(1e-6, domain="sync")

    def start_proc():
        for _ in range(64):
            yield

        yield top.start.eq(1)
        yield

    sim.add_sync_process(start_proc, domain="sync")

    mod_traces = []
    for name in top.__annotations__.keys(): # preserve source order
        mod_traces.append(getattr(top, name))

    clk_hack = sim._fragment.domains["sync"].clk
    with sim.write_vcd("axi_demo.vcd", "axi_demo.gtkw",
            traces=[clk_hack, *mod_traces]):
        sim.run_until(1e-3, run_passive=True)

if __name__ == "__main__":
    demo()
