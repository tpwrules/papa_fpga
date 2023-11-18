from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Interface, connect, flipped
from amaranth.lib.cdc import ResetSynchronizer, FFSynchronizer

from .bus import AudioRAMBus

class Top(wiring.Component):
    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    audio_ram: Out(AudioRAMBus())

    def elaborate(self, platform):
        m = Module()

        button = Signal()
        m.submodules += FFSynchronizer(self.button, button)

        MAX_COUNT = int(25e6)
        counter = Signal(range(0, MAX_COUNT-1))
        with m.If(counter == MAX_COUNT-1):
            m.d.sync += counter.eq(0)
            m.d.sync += self.blink.eq(~self.blink & button)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        # write a word when the button is pressed
        with m.FSM("IDLE"):
            with m.State("IDLE"):
                with m.If(~button): # button pressed
                    m.d.sync += [
                        # write address (first address of audio area thru ACP)
                        self.audio_ram.addr.eq(0xBF00_0000),
                        # one word please
                        self.audio_ram.length.eq(0),
                        # signals are valid
                        self.audio_ram.addr_valid.eq(1),
                    ]
                    m.next = "AWAIT"

            with m.State("AWAIT"):
                with m.If(self.audio_ram.addr_ready):
                    m.d.sync += [
                        # deassert valid
                        self.audio_ram.addr_valid.eq(0),
                        # set up data
                        self.audio_ram.data.eq(69),
                        self.audio_ram.data_valid.eq(1),
                        # toggle LED
                        self.status[0].eq(~self.status[0]),
                    ]
                    m.next = "DWAIT"

            with m.State("DWAIT"):
                with m.If(self.audio_ram.data_ready):
                    m.d.sync += [
                        # deassert valid
                        self.audio_ram.data_valid.eq(0),
                        # toggle LED
                        self.status[1].eq(~self.status[1]),
                    ]
                    m.next = "TWAIT"

            with m.State("TWAIT"):
                with m.If(self.audio_ram.txn_done):
                    # toggle LED
                    m.d.sync += self.status[2].eq(~self.status[2])
                    m.next = "BWAIT"

            with m.State("BWAIT"):
                with m.If(button): # button released
                    m.next = "IDLE"

        return m

class FPGATop(wiring.Component):
    clk50:      In(1)
    rst:        In(1)

    blink:      Out(1)
    status:     Out(3)
    button:     In(1)

    # copy-pasta from verilog
    f2h_axi_s0_awid: Out(7)
    f2h_axi_s0_awaddr: Out(32)
    f2h_axi_s0_awlen: Out(8)
    f2h_axi_s0_awsize: Out(3)
    f2h_axi_s0_awburst: Out(2)
    f2h_axi_s0_awcache: Out(4)
    f2h_axi_s0_awuser: Out(64)
    f2h_axi_s0_awvalid: Out(1)
    f2h_axi_s0_awready: In(1)
    f2h_axi_s0_wdata: Out(32)
    f2h_axi_s0_wstrb: Out(4)
    f2h_axi_s0_wvalid: Out(1)
    f2h_axi_s0_wready: In(1)
    f2h_axi_s0_bid: In(7)
    f2h_axi_s0_bvalid: In(1)
    f2h_axi_s0_bready: Out(1)
    f2h_axi_s0_arid: Out(7)
    f2h_axi_s0_araddr: Out(32)
    f2h_axi_s0_arlen: Out(8)
    f2h_axi_s0_arsize: Out(3)
    f2h_axi_s0_arburst: Out(2)
    f2h_axi_s0_arvalid: Out(1)
    f2h_axi_s0_arready: In(1)
    f2h_axi_s0_rid: In(7)
    f2h_axi_s0_rdata: In(32)
    f2h_axi_s0_rlast: In(1)
    f2h_axi_s0_rvalid: In(1)
    f2h_axi_s0_rready: Out(1)

    def elaborate(self, platform):
        m = Module()

        # wire up main clock domain
        m.domains.sync = sync = ClockDomain()
        m.d.comb += sync.clk.eq(self.clk50)

        m.submodules += ResetSynchronizer(self.rst)

        # wire up top module
        m.submodules.top = top = Top()
        for name, member in top.signature.members.items():
            try:
                if isinstance(getattr(self, name), Interface):
                    continue
            except AttributeError:
                continue
            if member.flow == In:
                m.d.comb += getattr(top, name).eq(getattr(self, name))
            elif member.flow == Out:
                m.d.comb += getattr(self, name).eq(getattr(top, name))
            else:
                raise ValueError("bad flow")

        # hook up audio RAM bus to AXI port
        m.d.comb += [
            self.f2h_axi_s0_awid.eq(0), # always write with id 0
            self.f2h_axi_s0_awaddr.eq(top.audio_ram.addr),
            self.f2h_axi_s0_awlen.eq(top.audio_ram.length),
            self.f2h_axi_s0_awsize.eq(0b010), # four bytes at a time
            self.f2h_axi_s0_awburst.eq(0b01), # burst mode: increment
            # heard vague rumors that these should just all be 1 to activate
            # caching as expected...
            self.f2h_axi_s0_awcache.eq(0b1111),
            # and 5 1 bits for the user data too (though that is from the
            # handbook)...
            self.f2h_axi_s0_awuser.eq(0b11111),
            self.f2h_axi_s0_awvalid.eq(top.audio_ram.addr_valid),
            top.audio_ram.addr_ready.eq(self.f2h_axi_s0_awready),

            self.f2h_axi_s0_wdata.eq(top.audio_ram.data),
            self.f2h_axi_s0_wstrb.eq(0b1111),
            self.f2h_axi_s0_wvalid.eq(top.audio_ram.data_valid),
            top.audio_ram.data_ready.eq(self.f2h_axi_s0_wready),

            self.f2h_axi_s0_bready.eq(self.f2h_axi_s0_bvalid),
            top.audio_ram.txn_done.eq(self.f2h_axi_s0_bvalid),
        ]

        # plug off address write and read data ports
        m.d.comb += [
            self.f2h_axi_s0_arvalid.eq(0),
            self.f2h_axi_s0_rready.eq(self.f2h_axi_s0_rvalid),
        ]

        return m

def generate():
    import sys
    from pathlib import Path
    from amaranth.back import verilog
    from .platform import AbbreviatedIntelPlatform

    top = FPGATop()
    with open(Path(sys.argv[1]), "w") as f:
        f.write(verilog.convert(top,
            platform=AbbreviatedIntelPlatform(),
            name="amaranth_top",
            # prevent source paths from being written into the design, in
            # particular absolute paths!
            strip_internal_attrs=True,
        ))

if __name__ == "__main__":
    generate()
