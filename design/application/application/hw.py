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

    def swap_buffers(self):
        # swap buffers and return (old buffer, old address)

        # ask for buffers to be swapped
        self.r[2] = 1
        # loop until it occurs (at about 48KHz so no point sleeping)
        while (status := self.r[2]) & 1: pass

        which = (status >> 1) & 1 # which buffer did we swap from?
        where = self.r[3] # what was the last address in that buffer?
        return (which, where)

    def get_data(self):
        # swap buffers then return a reference to the buffered data
        which_buf, buf_pos = self.swap_buffers()
        buf_pos >>= 1 # convert from bytes to words

        return self.d[which_buf, :buf_pos].reshape(-1, self.n)

    def set_gain(self, gain):
        # set the value to multiply the microphone data by (i.e. gain)

        gain = int(gain)
        if gain < 1 or gain > 256:
            raise ValueError("must be 1 <= gain <= 256")

        if (gain & (gain - 1)) != 0:
            raise ValueError("gain must be a power of 2")

        gain_log2 = gain.bit_length() - 1

        self.r[4] = gain_log2

    def set_use_fake_mics(self, use_fake_mics=True):
        # set whether fake mics should be used or not

        self.r[5] = 1 if use_fake_mics else 0

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
