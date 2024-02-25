## Nix Commands

#### Build Commands

Commands to build interesting parts of the setup for debugging.

1. Build Amaranth tree: `nix build .#design.amaranth_top`
2. Build bitstream: `nix build .#design.bitstream`
3. Build system application: `nix build .#design.application`
4. Build SD card image: `nix build .#nixosConfigurations.de10-nano`

Rebuild system when connected over USB ethernet (password is blank):

`nixos-rebuild --target-host nixos@192.168.80.1 --fast --use-remote-sudo --flake .#de10-nano switch -L`

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
