# PAPA FPGA System

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

## License

The code in this repository, as well as the produced artifacts, are licensed
under the GPLv3 (or later) license.

```
    PAPA FPGA System
    Copyright (C) 2023-2024 Thomas Watson

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

Certain files are also licensed under the MIT license (detailed in
`/LICENSE.mit`). These files are identified by a corresponding note in their
header. Other files (e.g. vendored code or patches) may have other license
terms. Contact the author for details, or information on availability of
additional terms.
