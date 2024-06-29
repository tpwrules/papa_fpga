{ pkgs, flakeInputs, pleaseKeepMyInputs }:

pkgs.mkShell {
  buildInputs = [
    pkgs.quartus-prime-lite
    pkgs.gtkwave

    (pkgs.python3.withPackages (p: [
      p.amaranth
      p.amaranth-soc
      p.amaranth-boards
      p.numpy
      p.matplotlib
    ]))
    pkgs.yosys

    pkgs.nixos-rebuild

    pleaseKeepMyInputs
  ];
}
