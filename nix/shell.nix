{ pkgs, flakeInputs, pleaseKeepMyInputs }:

pkgs.mkShell {
  buildInputs = [
    pkgs.quartus-prime-lite
    pkgs.gtkwave

    (pkgs.python3.withPackages (p: [
      p.amaranth
      p.amaranth-soc
    ]))
    pkgs.yosys

    pleaseKeepMyInputs
  ];
}
