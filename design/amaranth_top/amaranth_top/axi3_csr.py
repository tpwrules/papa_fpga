# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.
from amaranth import *
from amaranth.lib import enum
from amaranth.lib.wiring import Component, In, Out
from amaranth.lib.fifo import SyncFIFO

from amaranth_soc import csr

from .axi3 import AXI3Signature

# design goals:
#   * non horribly atrocious latency
#   * not horribly broken

class AXI3CSRBridge(Component):
    axi_bus: In(AXI3Signature(addr_width=21, data_width=32, id_width=12))

    csr_bus: Out(csr.Signature(addr_width=8, data_width=32))

    def elaborate(self, platform):
        m = Module()

        # data read and write are rather independent of everything else, so just
        # hook them to a FIFO and let them operate independently. each can store
        # one max-sized burst.
        m.submodules.w_fifo = w_fifo = SyncFIFO(width=32, depth=16)
        m.submodules.r_fifo = r_fifo = SyncFIFO(width=32+3+12, depth=16)

        axi = self.axi_bus
        m.d.comb += [
            # interface to AXI side
            w_fifo.w_data.eq(axi.w.data),
            w_fifo.w_en.eq(axi.w.valid & axi.w.ready),
            axi.w.ready.eq(w_fifo.w_rdy),

            Cat(axi.r.data, axi.r.id, axi.r.resp, axi.r.last).eq(r_fifo.r_data),
            r_fifo.r_en.eq(axi.r.valid & axi.r.ready),
            axi.r.valid.eq(r_fifo.r_rdy),

            # interface to CSR side
            self.csr_bus.w_data.eq(w_fifo.r_data),
            r_fifo.w_data.eq(self.csr_bus.r_data),
        ]

        # address read and write are independent on the AXI side, but only one
        # can occur on the CSR side. on the AXI side we have independent logic
        # to accept a transaction for each, then a big state machine to
        # actually process it through the CSR bus

        # write information and acceptance logic
        axi_wavail = Signal() # info is valid and write needs to be completed
        axi_wokay = Signal() # write transaction is what we like (aligned, etc.)
        axi_waddr = Signal(21)
        axi_wlen = Signal(4)
        axi_wid = Signal(12)

        m.d.comb += axi.aw.ready.eq(~axi_wavail)
        with m.If(axi.aw.ready & axi.aw.valid):
            m.d.sync += [
                axi_wavail.eq(1),
                axi_waddr.eq(axi.aw.addr),
                axi_wlen.eq(axi.aw.len),
                axi_wid.eq(axi.aw.id),
                axi_wokay.eq( # check if we like the request
                    (axi.aw.size == 0b010) & # 4 bytes
                    (axi.aw.lock == 0) & # not locked
                    (axi.aw.burst == 0b01) & # increment burst
                    (axi.aw.addr[:2] == 0)), # aligned
            ]

        # read information and acceptance logic
        axi_ravail = Signal() # info is valid and read needs to be completed
        axi_rokay = Signal() # read transaction is what we like (aligned, etc.)
        axi_raddr = Signal(21)
        axi_rlen = Signal(4)
        axi_rid = Signal(12)

        m.d.comb += axi.ar.ready.eq(~axi_ravail)
        with m.If(axi.ar.ready & axi.ar.valid):
            m.d.sync += [
                axi_ravail.eq(1),
                axi_raddr.eq(axi.ar.addr),
                axi_rlen.eq(axi.ar.len),
                axi_rid.eq(axi.ar.id),
                axi_rokay.eq( # check if we like the request
                    (axi.ar.size == 0b010) & # 4 bytes
                    (axi.ar.lock == 0) & # not locked
                    (axi.ar.burst == 0b01) & # increment burst
                    (axi.ar.addr[:2] == 0)), # aligned
            ]

        # process reads and writes
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
                # if we just finished e.g. write, then wpossible can't go active
                # again until next cycle (as axi_wavail just went inactive this
                # cycle) so we'll do a read if pending and won't starve it.
                with m.If(wpossible):
                    m.next = "WRITE"
                with m.Elif(rpossible):
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
                    axi.b.valid.eq(1),
                    axi.b.id.eq(axi_wid),
                    axi.b.resp.eq(Mux(axi_wokay, 0, 0b10)), # target error
                ]
                with m.If(axi.b.ready):
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
                    bridge.axi_bus.aw.addr.eq(0),
                    bridge.axi_bus.aw.len.eq(7), # 8 words
                    bridge.axi_bus.aw.size.eq(0b010), # 4 bytes
                    bridge.axi_bus.aw.burst.eq(0b01), # increment burst
                    bridge.axi_bus.aw.valid.eq(1),
                ]
                with m.If(bridge.axi_bus.aw.ready):
                    m.next = "IDLE"

        # write data state machine
        write_remain = Signal(8)
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.start):
                    m.d.sync += write_remain.eq(7)
                    m.next = "WVALID"

            with m.State("WVALID"):
                m.d.comb += bridge.axi_bus.w.valid.eq(1)
                with m.If(bridge.axi_bus.w.ready):
                    m.d.sync += write_remain.eq(write_remain - 1)
                    with m.If(write_remain == 0):
                        m.next = "IDLE"

        # always ready for write response
        m.d.comb += bridge.axi_bus.b.ready.eq(1)

        # read address state machine
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(self.start):
                    m.next = "ARVALID"

            with m.State("ARVALID"):
                m.d.comb += [
                    bridge.axi_bus.ar.addr.eq(0),
                    bridge.axi_bus.ar.len.eq(7), # 8 words
                    bridge.axi_bus.ar.size.eq(0b010), # 4 bytes
                    bridge.axi_bus.ar.burst.eq(0b01), # increment burst
                    bridge.axi_bus.ar.valid.eq(1),
                ]
                with m.If(bridge.axi_bus.ar.ready):
                    m.next = "IDLE"

        # always ready for read data
        m.d.comb += bridge.axi_bus.r.ready.eq(1)

        # read and write something vaguely interesting
        m.d.comb += bridge.axi_bus.w.data.eq(69)
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
