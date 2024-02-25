## PAPA FPGA

Basic Usage:
1. Set MSEL[4:0] to "00000" (i.e. all DIP switches UP)
2. `nix build .#nixosConfigurations.de10-nano` then zstdcat | dd
    `result/sd-image/*.img.zst` to an SD card
3. Plug in SD card, USB UART (115200 baud), and power, then run `sudo wavdump`
   at prompt

#### System Objectives

* Collect data from N I2S microphones
* Convolve the data from the Nth microphone with M independent K-tap filters
  (for N x M x K total filter coefficients)
* Produce M output channels as the sum of the particular N convolved signals
* Save this data to disk or stream it out over the network

#### Notes

Other Goal: build a bitstream and HPS image from source using Nix with no blobs
or non-free non-mainline software (except for Quartus)

Todo:
* non-maximal kernel config
* fix cross hacks
* refactor Nix derivation components to be more reusable
* some cool automatic way of assigning a MAC address
* more reasonable way of setting up bitstream under Linux
* bitstream compression and faster loading
* document better
