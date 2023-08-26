{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: let
    flakeInputs = { inherit nixpkgs; };
    system = "x86_64-linux";

    # a text file containing the paths to the flake inputs in order to stop
    # them from being garbage collected
    pleaseKeepMyInputs = pkgs.writeTextDir "bin/.please-keep-my-inputs"
      (builtins.concatStringsSep " " (builtins.attrValues flakeInputs));

    pkgs = import nixpkgs {
      inherit system;
      config = { allowUnfree = true; };
      overlays = [
        (import ./nix/overlay.nix)
      ];
    };
  in {
    devShell."${system}" = import ./nix/shell.nix
      { inherit pkgs flakeInputs pleaseKeepMyInputs; };

    packages."${system}" = {
      inherit (pkgs) quartus soc_system;
    };
  };
}

