{ config, pkgs, lib, modulesPath, ... }:

{
  imports = [
    (modulesPath + "/profiles/minimal.nix")
    (modulesPath + "/installer/sd-card/sd-image.nix")
  ];

  boot.loader.generic-extlinux-compatible.enable = true;
  boot.loader.grub.enable = false;
  boot.kernelParams = [
    "console=ttyS0,115200"
  ];

  sdImage.populateRootCommands = ''
    mkdir -p ./files/boot
    ${config.boot.loader.generic-extlinux-compatible.populateCmd} -c ${config.system.build.toplevel} -d ./files/boot

    # HACK: shorten DTB name so u-boot can load it for now
    # we also use the de0 nano DTB since there is no de10 nano in mainline kernel
    FDTDIR=$(echo ./files/boot/nixos/*-dtbs)
    chmod -R u+w $FDTDIR
    mv $FDTDIR/socfpga_cyclone5_de0_nano_soc.dtb $FDTDIR/x.dtb
  '';

  sdImage.populateFirmwareCommands = ''
  '';

  # Use less privileged nixos user
  users.users.nixos = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "video" ];
    # Allow the graphical user to login without password
    initialHashedPassword = "";
  };

  # Allow the user to log in as root without a password.
  users.users.root.initialHashedPassword = "";

  # Allow passwordless sudo from nixos user
  security.sudo = {
    enable = true;
    wheelNeedsPassword = false;
  };

  # Automatically log in at the virtual consoles.
  services.getty.autologinUser = "nixos";

  environment.systemPackages = with pkgs; lib.mkForce [
    bash
    nano
    nix
    coreutils
  ];

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
