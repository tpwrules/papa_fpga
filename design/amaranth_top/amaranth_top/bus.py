from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Signature

# rather thin wrapper around AXI
class AudioRAMBus(Signature):
    def __init__(self):
        super().__init__({
            # note: write must not cross 4K page boundary which we choose to
            # mean must start or must end on a 64 byte boundary
            "addr": Out(32),
            "length": Out(4), # 1-16 writes at a time
            "addr_valid": Out(1),
            "addr_ready": In(1),

            "data": Out(32),
            "data_valid": Out(1),
            "data_ready": In(1),

            "txn_done": In(1),
        })
