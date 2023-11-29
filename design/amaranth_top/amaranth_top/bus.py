from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Signature

# rather thin wrapper around AXI
class AudioRAMBus(Signature):
    def __init__(self):
        super().__init__({
            # note: write must not cross 4K page boundary which we choose to
            # mean must start or must end on a 32 byte boundary
            "addr": Out(32), # must be even
            "length": Out(4), # 1-16 writes at a time
            "addr_valid": Out(1),
            "addr_ready": In(1),

            "data": Out(16),
            "data_valid": Out(1),
            "data_last": Out(1),
            "data_ready": In(1),

            "txn_done": In(1),
        })

# intended just to always acknowledge writes, not necessarily implement a
# complete AXI receiver
class FakeAudioRAMBusWriteReceiver(wiring.Component):
    audio_ram: In(AudioRAMBus())

    def elaborate(self, platform):
        m = Module()

        beats_received = Signal(64) # number of beats we've received
        beats_target = Signal(64) # number of beats to receive before ack

        abus = self.audio_ram

        # data can always be received
        m.d.comb += abus.data_ready.eq(1)
        with m.If(abus.data_valid):
            m.d.sync += beats_received.eq(beats_received + 1)

        with m.FSM("IDLE"):
            with m.State("IDLE"):
                m.d.sync += abus.addr_ready.eq(1)
                with m.If(abus.addr_valid & abus.addr_ready):
                    m.d.sync += [
                        abus.addr_ready.eq(0), # not ready until beats over
                        beats_target.eq(beats_target + 1 + abus.length),
                    ]
                    m.next = "RECV"

            with m.State("RECV"):
                with m.If(beats_received >= beats_target):
                    m.d.comb += abus.txn_done.eq(1)
                    m.next = "IDLE"

        return m
