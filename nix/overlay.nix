final: prev: {
  quartus-prime-lite = final.callPackage ./packages/quartus-prime {
    supportedDevices = [ "Cyclone V" ];
  };

  intel-socfpga-hwlib = final.callPackage ./packages/intel-socfpga-hwlib {};

  pythonPackagesExtensions = let
    amaranth-soc =
      { lib
      , buildPythonPackage
      , fetchFromGitHub
      , amaranth
      , pdm-backend
      }:

      buildPythonPackage rec {
        pname = "amaranth-soc";
        version = "0.0.1"; # ugh pdm: unstable-2024-02-09
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "1e1490ef85433493b9c43050eae8925ec85b2a53";
          hash = "sha256-0eyWuS05E5OtbswROSlYj4CrR1ETNq7W3ub3mJn1AU8=";
        };

        nativeBuildInputs = [ pdm-backend ];
        propagatedBuildInputs = [ amaranth ];

        meta = with lib; {
          description = "System on Chip toolkit for Amaranth HDL";
          homepage = "https://github.com/amaranth-lang/amaranth-soc";
          license = licenses.bsd2;
          maintainers = with maintainers; [ emily thoughtpolice ];
        };
      };
  in prev.pythonPackagesExtensions ++ [
    (python-final: python-prev: {
      # upgrade to latest version
      amaranth = (python-prev.amaranth.overrideAttrs (o: {
        version = "0.4.1"; # unstable-2024-01-22

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "b3639c4cc5938148bbd114aa9efbd410d2893824";
          hash = "sha256-zq7r53UUQ3kAXbiTm5ZHWG+xtjEBg07oiuQeZ9UG4Ds=";
        };
      }));

      amaranth-soc = python-final.callPackage amaranth-soc {};
    })
  ];

  design = prev.lib.makeScope prev.newScope (self: with self; {
    amaranth_top = callPackage ./design/amaranth_top {};
    bitstream = callPackage ./design/bitstream {};
    linux_firmware = callPackage ./design/linux_firmware {};
    application = final.pkgsCross.armv7l-hf-multiplatform.python3Packages.callPackage ./design/application { };
  });
}
