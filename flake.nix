{
  # ideally nixos-unstable
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/c757e9bd77b16ca2e03c89bf8bc9ecb28e0c06ad";

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
      inherit (pkgs) design;
    };

    nixosConfigurations.de10-nano = let
      installer-system = nixpkgs.lib.nixosSystem {
        inherit system;

        pkgs = import nixpkgs {
          crossSystem.system = "armv7l-linux";
          localSystem.system = system;
          config = { allowUnfree = true; };
          overlays = [ (import ./nix/overlay.nix) ];
        };

        specialArgs = {
          modulesPath = nixpkgs + "/nixos/modules";
          inherit (pkgs) design; # HACK to use the expected pkgs
        };

        modules = [
          ./nix/nixos/sd-image
        ];
      };

      config = installer-system.config;
    in (config.system.build.sdImage.overrideAttrs (old: {
      # add ability to access the whole config from the command line
      passthru = (old.passthru or {}) // { inherit config; };
    }));
  };
}
