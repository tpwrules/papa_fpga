## Nix Commands

#### Build Commands

Commands to build interesting parts of the setup for debugging.

1. Build SoC system: `nix build .#design.soc_system`
2. Build Amaranth Verilog module: `nix build .#design.amaranth_top`
3. Build bitstream: `nix build .#design.bitstream`
4. Build demo application: `nix build .#design.application`
5. Build SD card image: `nix build .#nixosConfigurations.de10-nano`

#### Prefill NAR Files

Contains all the stuff you might want to avoid lengthy build times.

For Quartus:
1. `mkdir -p profiles`
2. `nix develop --profile profiles/dev`
3. `nix-store --export $(nix-store -qR profiles/dev) | zstd -T0 > ../prefill_quartus_<git hash>.nar.zst`

For the Linux image:
1. `nix build .#nixosConfigurations.de10-nano.config.system.build.toplevel`
2. `nix-store --export $(nix-store -qR result) | zstd -T0 > ../prefill_linux_<git hash>.nar.zst`

To import a `.nar.zst` file:
1. ``zstdcat /path/to/the.nar.zst | sudo `which nix-store` --import``
