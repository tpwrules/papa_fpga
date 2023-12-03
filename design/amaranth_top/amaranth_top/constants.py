from amaranth import *

# constants which parameterize the design as a whole

MIC_FREQ_HZ = 48000
CAP_DATA_BITS = 16 # lowest 8 mic data bits thrown away

# total number of microphones to take input from (must be even)
# right mics are even (0, 2, 4, ...), left mics are odd (1, 3, 5, ...)
# should be good up to like 120 microphones (as there are 128 data times)
NUM_MICS = 16

# number of output channels to generate (slowest axis for coefficients)
# limited to like 110 since that's how many DSP blocks we have spare and each
# channel needs one DSP block
NUM_CHANS = 25

# number of filter taps used for each channel (middle axis for coefficients)
NUM_TAPS = 101

# then microphones is the fastest axis
