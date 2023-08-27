{ config, pkgs, lib, modulesPath, ... }:

{
  imports = [
    (modulesPath + "/profiles/minimal.nix")
    (modulesPath + "/installer/cd-dvd/sd-image.nix")
  ];

  boot.loader.generic-extlinux-compatible.enable = true;
  boot.loader.grub.enable = false;

  sdImage.populateRootCommands = ''
    mkdir -p ./files/boot
    ${config.boot.loader.generic-extlinux-compatible.populateCmd} -c ${config.system.build.toplevel} -d ./files/boot
  '';

  sdImage.populateFirmwareCommands = ''
  '';

  environment.systemPackages = lib.mkForce [];

  # save space and compilation time. might revise?
  hardware.enableAllFirmware = lib.mkForce false;
  hardware.enableRedistributableFirmware = lib.mkForce false;
  sound.enable = false;
  # avoid including non-reproducible dbus docs
  documentation.doc.enable = false;
  documentation.info.enable = lib.mkForce false;
  documentation.nixos.enable = lib.mkOverride 49 false;
  system.extraDependencies = lib.mkForce [ ];

  # Disable wpa_supplicant because it can't use WPA3-SAE on broadcom chips that are used on macs and it is harder to use and less mainained than iwd in general
  networking.wireless.enable = false;

  nixpkgs.overlays = [
    (final: prev: {
      # disabling pcsclite avoids the need to cross-compile gobject
      # introspection stuff which works now but is slow and unnecessary
      iwd = prev.iwd.override {
        withPcsclite = false;
      };
      libfido2 = prev.libfido2.override {
        withPcsclite = false;
      };
      openssh = prev.openssh.overrideAttrs (old: {
        # we have to cross compile openssh ourselves for whatever reason
        # but the tests take quite a long time to run
        doCheck = false;
      });

      # avoids having to compile a bunch of big things (like texlive) to
      # compute translations
      util-linux = prev.util-linux.override {
        translateManpages = false;
      };
    })
  ];

  # avoids the need to cross-compile gobject introspection stuff which works
  # now but is slow and unnecessary
  security.polkit.enable = false;

  # bootspec generation is currently broken under cross-compilation
  boot.bootspec.enable = false;

  # get rid of warning that stateVersion is unset
  system.stateVersion = lib.mkDefault lib.trivial.release;
}
