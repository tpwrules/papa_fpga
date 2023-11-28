import os
import mmap

import numpy as np

class HW:
    def __init__(self):
        # open file descriptors to memory so we can map it. one is sync
        # (to access registers) and the other is not (for the cache-coherent
        # data buffer in SDRAM)
        try:
            self._buf_fd = os.open("/dev/mem", os.O_RDWR)
        except PermissionError:
            self._closed = True # prevent __del__ from running
            raise

        self._reg_fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)

        # memory map the two areas

        # 16 MiB buffer area at end of 1GiB SDRAM
        self._buf_mmap = mmap.mmap(self._buf_fd,
            0x100_0000, offset=0x3f00_0000)
        # 1KiB register area at start of FPGA lightweight slave region
        self._reg_mmap = mmap.mmap(self._reg_fd,
            0x400, offset = 0xff20_0000)

        # expose as numpy arrays

        # expose as two regions of signed 16 bit words
        self.d = np.frombuffer(self._buf_mmap, dtype=np.int16).reshape(2, -1)
        # expose as uint32 register data
        self.r = np.frombuffer(self._reg_mmap, dtype=np.uint32)

        self._closed = False

        # access test register to make sure the bus seems alive
        val = self.r[0]
        val = ((val + 0x1234) * 3) & 0xFFFF_FFFF # permute the value somehow
        self.r[0] = val
        if self.r[0] != val:
            raise ValueError("test register not responding")

        # read number of microphones
        self.n = self.r[1]

        # wait for any existing buffer swap to have completed
        while self.r[2] & 1: pass

    def close(self):
        if self._closed:
            raise ValueError

        self.d = None
        self.r = None

        self._buf_mmap.close()
        self._buf_mmap = None
        self._reg_mmap.close()
        self._reg_mmap = None

        os.close(self._buf_fd)
        self._buf_fd = None
        os.close(self._reg_fd)
        self._reg_fd = None

        self._closed = True

    def __del__(self):
        if not self._closed:
            self.close()
