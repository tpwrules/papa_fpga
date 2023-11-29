import sys
import time
import wave
import argparse

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

def parse_args():
    parser = argparse.ArgumentParser(prog="wavdump",
        description="Dump WAV data from mic capture interface.")
    parser.add_argument('filename', type=str,
        help="File to save .wav data to.")
    parser.add_argument('-c', '--channels', type=int, metavar="N", default=2,
        help="Number of channels to capture (from first N mics).")

    return parser.parse_args()

def wavdump():
    args = parse_args()

    hw = HW()

    channels = args.channels
    if channels < 1 or channels > hw.n:
        raise ValueError(f"must be 1 <= channels <= {hw.n}")

    wav = wave.open(args.filename, "wb")
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
