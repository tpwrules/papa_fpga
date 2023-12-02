final: prev: {
  quartus-prime-lite = final.callPackage ./packages/quartus-prime {
    supportedDevices = [ "Cyclone V" ];
  };

  intel-socfpga-hwlib = final.callPackage ./packages/intel-socfpga-hwlib {};

  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (python-final: python-prev: {
      # latest numpy is broken for cross
      numpy-old = (python-final.callPackage ./packages/numpy-1.25.1 {});

      # upgrade to latest version
      amaranth = (python-prev.amaranth.overrideAttrs (o: {
        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "b0b193f1ad65d1f4f5c16a4b8249f43b3ea29c9f";
          hash = "sha256-EoZDhJDnDbxad3aw8pjuvfVOT1vSn4gUP//ocP2T//c=";
        };
      }));

      amaranth-soc = (python-prev.amaranth-soc.overrideAttrs (o: {
        version = "unstable-2023-11-22-pr-40";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "b814a7730d156054f871ba1cf6bfa9275eb090c7";
          hash = "sha256-OSYsXS2HrtqofhXb+XP5zGkMg9QkZs9GZBMx+36plm4=";
          # files change depending on github PR status
          postFetch = "rm -f $out/.git_archival.txt $out/.gitattributes";
        };
      }));
    })
  ];

  design = prev.lib.makeScope prev.newScope (self: with self; {
    soc_system = callPackage ./design/soc_system {};
    amaranth_top = callPackage ./design/amaranth_top {};
    bitstream = callPackage ./design/bitstream {};
    linux_firmware = callPackage ./design/linux_firmware {};
    application = final.pkgsCross.armv7l-hf-multiplatform.python3Packages.callPackage ./design/application { };
  });
}
