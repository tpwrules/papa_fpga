## DE10-Nano + NixOS Demo

Goal: build a bitstream and HPS image from source using Nix with no blobs or
non-free non-mainline software (except for Quartus and mandatory Verilog IP)

Demo:
1. Set MSEL[4:0] to "00000" (i.e. all DIP switches UP)
2. `nix build .#nixosConfigurations.de10-nano` then zstdcat/dd
    `result/sd-image/*.img.zst` to an SD card
3. Plug in SD card, USB UART (115200 baud), and power, then run `demo` at prompt

Todo:
* non-maximal kernel config
* fix cross hacks
* refactor Nix derivation components to be more reusable
* more interesting demo
* some cool automatic way of assigning a MAC address
* more reasonable way of setting up bitstream under Linux
* bitstream compression and faster loading
* integrate Amaranth better incl. simulation
