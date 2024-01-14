{ config, pkgs, lib, modulesPath, design, ... }:

{
  imports = [
    (modulesPath + "/profiles/minimal.nix")
    (modulesPath + "/installer/sd-card/sd-image.nix")
  ];

  boot.loader.generic-extlinux-compatible.enable = true;
  boot.loader.grub.enable = false;
  boot.loader.timeout = 1;
  boot.kernelParams = [
    "console=ttyS0,115200"
  ];

  sdImage.populateRootCommands = ''
    mkdir -p ./files/boot
    ${config.boot.loader.generic-extlinux-compatible.populateCmd} -c ${config.system.build.toplevel} -d ./files/boot

    # use the de0 nano DTB since there is no de10 nano in mainline kernel
    # and it seems to work okay
    FDTDIR=$(echo ./files/boot/nixos/*-d*s) # match "dtbs" and "device-tree-overlays"
    chmod -R u+w $FDTDIR
    mv $FDTDIR/socfpga_cyclone5_de0_nano_soc.dtb $FDTDIR/socfpga_cyclone5_de10_nano.dtb
  '';

  sdImage.populateFirmwareCommands = ''
  '';

  hardware.firmware = [ design.linux_firmware ];

  # u-boot and the SPL live in a partition with a specific MBR ID. we reuse
  # the firmware partition for this purpose and then use DD to write the image
  # into the partition space
  sdImage.firmwareSize = 2; # 2MiB space like stock SD image, binary is about 800K
  sdImage.firmwarePartitionOffset = 1; # 1MiB in
  sdImage.postBuildCommands = let
    uboot = pkgs.buildUBoot {
      defconfig = "socfpga_de10_nano_defconfig";
      filesToInstall = ["u-boot-with-spl.sfp"];
      # automatically boot by default
      extraConfig = ''
        CONFIG_USE_BOOTCOMMAND=y
      '';
    };
  in ''
    # write u-boot and SPL into "firmware" partition space
    dd if=${uboot}/u-boot-with-spl.sfp of=$img bs=1M seek=1 conv=notrunc
    # set MBR ID to 0xA2 so the boot ROM will use this partition
    sfdisk --part-type $img 1 a2
  '';

  # Use less privileged nixos user
  users.users.nixos = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "video" ];
    # hash of empty password
    initialHashedPassword = "$y$j9T$QPt6M9GAEOhYriE0C8wnK0$ygMYgHlcRbmpBTeMxgqGRR4KVoEDH56wivA5G9OdB54";
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

  boot.kernelPatches = [
    {
      name = "enable-of-overlay";
      patch = ./dt-overlay-configfs-interface.patch;
      # 1. enable overlay system and configfs so we can add the overlay
      # 2. disable protections on /dev/mem so we can poke our FPGA design through it
      extraConfig = ''
        OF_OVERLAY y
        OF_CONFIGFS y

        STRICT_DEVMEM n
        IO_STRICT_DEVMEM n
      '';
    }
  ];

  hardware.deviceTree.overlays = [
    # reserve 16MiB at the end of SDRAM (0x3F000000-0x40000000)
    {
      name = "memory-reserve";
      dtsFile = ./memory-reserve.dts;
    }
  ];

  environment.systemPackages = with pkgs; [
    dtc
    design.application

    (python3.withPackages (p: [
      p.numpy
    ]))
  ];

  services.openssh = {
    enable = true;
    settings.PermitRootLogin = "yes";
  };

  # ensure kernel modules for the FPGA are loaded so the bitstream load works
  boot.kernelModules = [
    "socfpga"
    "altera_fpga2sdram"
    "altera_hps2fpga"
    "of_fpga_region"
    "g_ncm" # USB gadget module for USB ethernet
  ];
  systemd.services.bitstream = {
    description = "FPGA bitstream overlay loader";

    wantedBy = [ "multi-user.target" ];
    after = [
      "sys-module-configfs.device" # configfs is available to write overlay
      "systemd-modules-load.service" # socfpga is available to load FPGA
    ];

    serviceConfig = {
      ExecStartPre = "${pkgs.coreutils}/bin/mkdir -p /sys/kernel/config/device-tree/overlays/bitstream";
      # bitstream is pulled from /lib/firmware, we echo the current firmware path so the unit gets reloaded if the bitstream changes
      ExecStart = "${pkgs.bash}/bin/bash -c 'echo -n bitstream.dtbo | tee /sys/kernel/config/device-tree/overlays/bitstream/path ; echo ${design.linux_firmware}'";
      ExecStop = "${pkgs.coreutils}/bin/rmdir /sys/kernel/config/device-tree/overlays/bitstream/";
      RemainAfterExit = "yes";
    };
  };

  # uncomplicate using the server
  networking.firewall.enable = false;

  # run DHCP for access over USB ethernet gadget
  services.dnsmasq = {
    enable = true;

    settings = {
      bind-interfaces = true;
      interface = [ "usb0" ];
      dhcp-range = [ "192.168.80.100,192.168.80.200,255.255.255.0,12h" ];
    };
  };

  # hardcode USB ethernet gadget address for easy access
  networking.interfaces.usb0.ipv4.addresses = [ {
    address = "192.168.80.1";
    prefixLength = 24;
  } ];

  networking.dhcpcd.denyInterfaces = [ "usb0" ];

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

  # enable flakes and experimental commands
  # and make the root user always trusted
  nix.extraOptions = ''
    experimental-features = nix-command flakes
    trusted-users = @wheel
  '';

  # get rid of warning that stateVersion is unset
  system.stateVersion = lib.mkDefault lib.trivial.release;
}
