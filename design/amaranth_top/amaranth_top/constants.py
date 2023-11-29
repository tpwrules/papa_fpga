from amaranth import *

# constants which parameterize the design as a whole

MIC_FREQ_HZ = 48000
CAP_DATA_BITS = 16 # lowest 8 mic data bits thrown away

# total number of microphones to take input from (must be even)
# right mics are even (0, 2, 4, ...), left mics are odd (1, 3, 5, ...)
# should be good up to like 120 microphones (as there are 128 data times)
NUM_MICS = 36
