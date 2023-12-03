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
    parser.add_argument('-c', '--channels', type=int, metavar="N", default=None,
        help="Number of channels to capture (from first N mics/channels), "
             "default all available.")
    parser.add_argument('-g', '--gain', type=int, default=1,
        help="Gain value to multiply microphone data by, default 1.")
    parser.add_argument('-f', '--fake', action="store_true",
        help="Capture from fake microphones instead of real ones.")
    parser.add_argument('-r', '--raw', action="store_true",
        help="Store raw mic data instead of convolved output channels.")

    return parser.parse_args()

def wavdump():
    args = parse_args()

    hw = HW()
    print(f"capture frequency is {hw.mic_freq_hz}Hz")

    hw.set_gain(args.gain)
    hw.set_use_fake_mics(args.fake)
    hw.set_store_raw_data(args.raw)

    channels = args.channels
    max_channels = hw.num_mics if args.raw else hw.num_chans
    if channels is None:
        channels = max_channels
    if channels < 1 or channels > max_channels:
        raise ValueError(f"must be 1 <= channels <= {max_channels}")

    wav = wave.open(args.filename, "wb")
    wav.setnchannels(channels)
    wav.setsampwidth(2)
    wav.setframerate(hw.mic_freq_hz)

    try:
        capture(hw, wav, channels)
    except KeyboardInterrupt:
        print("bye")
    finally:
        wav.close()

if __name__ == "__main__":
    wavdump()
