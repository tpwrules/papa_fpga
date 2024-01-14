from cpython cimport array
from libc.stdint cimport uint32_t

cdef class VolatileU32Array:
    cdef uint32_t[:] arr

    def __init__(self, arr_in):
        self.arr = arr_in

    def __getitem__(self, int off):
        cdef volatile uint32_t* p = &self.arr[off]
        cdef uint32_t v = p[0]

        return v

    def __setitem__(self, int off, uint32_t val):
        cdef volatile uint32_t* p = &self.arr[off]

        p[0] = val
