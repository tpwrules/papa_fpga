import sys
import time
import wave

import numpy as np

from .hw import HW

def capture(hw, wav, channels):
    # swap buffers at the beginning since the current one probably overflowed
    hw.swap_buffers()

    print("capture is starting!")
    while True:
        try:
            data = hw.get_data()
        except ValueError:
            print("oops, probably overflowed")
            continue

        print(f"got {len(data)} samples")
        wav.writeframesraw(np.ascontiguousarray(data[:, :channels]))
        time.sleep(0.1)

def wavdump():
    channels = int(sys.argv[1])
    path = sys.argv[2]

    hw = HW()

    assert channels > 0 and channels <= hw.n

    wav = wave.open(path, "wb")
    wav.setnchannels(channels)
    wav.setsampwidth(2)
    wav.setframerate(48000)

    try:
        capture(hw, wav, channels)
    except KeyboardInterrupt:
        print("bye")
    finally:
        wav.close()

if __name__ == "__main__":
    wavdump()
