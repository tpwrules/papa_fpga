# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.

# signatures, interfaces, and enums for AXI3 with Amaranth

from dataclasses import dataclass

from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out
from amaranth.utils import exact_log2

@dataclass(frozen=True)
class UserWidth:
    def __post_init__(self):
        for chan in ("aw", "w", "b", "ar", "r"):
            val = int(getattr(self, chan))
            object.__setattr__(self, chan, val) # ensure it's an integer
            if val < 0:
                raise ValueError(
                    f"channel {chan} width must be non-negative, not {val}")

    aw: int = 0
    w: int = 0
    b: int = 0
    ar: int = 0
    r: int = 0

@dataclass(frozen=True)
class AXI3Params:
    def __post_init__(self):
        # ensure widths are integers
        for sig in ("addr_width", "data_width", "id_width"):
            object.__setattr__(self, sig, int(getattr(self, sig)))

        # data width signal must be a power of 2 at least 8
        if self.data_width < 8 or self.data_width > 1024:
            raise ValueError(f"data_width out of range")
        data_bits = exact_log2(self.data_width)

        # assume we have to address at least one data element
        if self.addr_width < data_bits or self.addr_width > 128:
            raise ValueError(f"addr_width out of range")

        if self.id_width <= 0:
            raise ValueError(f"id_width must be positive")

        uw = self.user_width
        if isinstance(uw, int):
            if uw < 0:
                raise ValueError(f"user_width must be non-negative")
            uw = UserWidth(aw=uw, w=uw, b=uw, ar=uw, r=uw)
        else: # assume it's a dict
            uw = UserWidth(**uw)
        object.__setattr__(self, "user_width", uw)

    # address signal width in bits
    addr_width: int

    # data signal width in bits
    data_width: int

    # id signal width in bits
    id_width: int

    # user signal width in bits, for each channel (aw/w/b/ar/r). can optionally
    # be passed as an integer to set all channels to the same.
    # technically not in AXI3 but Cyclone V needs it so...
    user_width: UserWidth = 0

    @property
    def strobe_width(self):
        return self.data_width//8 # constructor has ensured it's a power of 2

# all channels are described from the perspective of the initiator of that
# particular channel (i.e. valid is always an Out)

class _AXISignaturePiece(wiring.Signature):
    @property
    def params(self):
        return self._params

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.params == other.params

    def __repr__(self):
        return f"{type(self).__name__}({self.params})"

class AddressChannelSignature(_AXISignaturePiece):
    def __init__(self, params, is_write):
        self._params = params
        user_width = params.user_width.aw if is_write else params.user_width.ar
        super().__init__({
            "valid": Out(1), # stream signals
            "ready": In(1),

            "id": Out(params.id_width),
            "addr": Out(params.addr_width),
            "len": Out(4),
            "size": Out(3),
            "burst": Out(2),
            "lock": Out(2),
            "cache": Out(4),
            "prot": Out(3),
            **({"user": Out(user_width)} if user_width > 0 else {})
        })

class WriteDataChannelSignature(_AXISignaturePiece):
    def __init__(self, params):
        self._params = params
        super().__init__({
            "valid": Out(1), # stream signals
            "ready": In(1),

            "id": Out(params.id_width),
            "data": Out(params.data_width),
            "strb": Out(params.strobe_width),
            "last": Out(1),
            **({"user": Out(params.user_width.w)}
                if params.user_width.w > 0 else {})
        })

class WriteResponseChannelSignature(_AXISignaturePiece):
    def __init__(self, params):
        self._params = params
        super().__init__({
            "valid": Out(1), # stream signals
            "ready": In(1),

            "id": Out(params.id_width),
            "resp": Out(2),
            **({"user": Out(params.user_width.b)}
                if params.user_width.b > 0 else {})
        })

class ReadDataChannelSignature(_AXISignaturePiece):
    def __init__(self, params):
        self._params = params
        super().__init__({
            "valid": Out(1), # stream signals
            "ready": In(1),

            "id": Out(params.id_width),
            "data": Out(params.data_width),
            "resp": Out(2),
            "last": Out(1),
            **({"user": Out(params.user_width.r)}
                if params.user_width.r > 0 else {})
        })

class AXI3Signature(_AXISignaturePiece):
    def __init__(self, params=None, **kwargs):
        if params is None and len(kwargs) == 0:
            raise ValueError("must have params or args")
        if params is not None and len(kwargs) > 0:
            raise ValueError("can't have params and args")
        if params is not None:
            self._params = params
        else:
            self._params = AXI3Params(**kwargs)

        super().__init__({
            "aw": Out(AddressChannelSignature(self._params, is_write=True)),
            "w": Out(WriteDataChannelSignature(self._params)),
            "b": In(WriteResponseChannelSignature(self._params)),
            "ar": Out(AddressChannelSignature(self._params, is_write=False)),
            "r": In(ReadDataChannelSignature(self._params)),
        })
