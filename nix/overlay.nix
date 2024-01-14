final: prev: {
  quartus-prime-lite = final.callPackage ./packages/quartus-prime {
    supportedDevices = [ "Cyclone V" ];
  };

  intel-socfpga-hwlib = final.callPackage ./packages/intel-socfpga-hwlib {};

  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (python-final: python-prev: {
      # upgrade to latest version
      amaranth = (python-prev.amaranth.overrideAttrs (o: {
        version = "0.4.0";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "v0.4.0";
          hash = "sha256-dC+yFPZnKzTYrzzzoPXGbsc0i+Bhh80d/7ngjp8SQdc=";
        };
      }));

      amaranth-soc = (python-prev.amaranth-soc.overrideAttrs (o: {
        version = "unstable-2023-12-15-pr-40";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "be1f028af8573ac985b7c6fa1b8360a7e6a41f49";
          hash = "sha256-XKSGBSwu415oEayv3gQfZePgkeSQQYeUuzchcK3QqLU=";
          # files change depending on github PR status
          postFetch = "rm -f $out/.git_archival.txt $out/.gitattributes";
        };
      }));
    })
  ];

  design = prev.lib.makeScope prev.newScope (self: with self; {
    amaranth_top = callPackage ./design/amaranth_top {};
    bitstream = callPackage ./design/bitstream {};
    linux_firmware = callPackage ./design/linux_firmware {};
    application = final.pkgsCross.armv7l-hf-multiplatform.python3Packages.callPackage ./design/application { };
  });
}
