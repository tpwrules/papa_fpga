from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Signature

from .constants import CAP_DATA_BITS

# sample data in the system
class SampleStream(Signature):
    def __init__(self):
        super().__init__({
            "data": Out(signed(CAP_DATA_BITS)),
            "first": Out(1), # first sample of the microphone set
            "new": Out(1), # new microphone data is
        })
