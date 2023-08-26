{ pkgs, flakeInputs, pleaseKeepMyInputs }:

pkgs.mkShell {
  buildInputs = [
    pkgs.hello

    pleaseKeepMyInputs
  ];
}
