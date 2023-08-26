{ pkgs, flakeInputs, pleaseKeepMyInputs }:

pkgs.mkShell {
  buildInputs = [
    pkgs.quartus-prime-lite

    pleaseKeepMyInputs
  ];
}
