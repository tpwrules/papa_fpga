final: prev: {
  quartus-prime-lite = final.callPackage ./packages/quartus-prime {
    supportedDevices = [ "Cyclone V" ];
  };

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

    amaranth-boards =
      { lib
      , buildPythonPackage
      , fetchFromGitHub
      , amaranth
      , setuptools
      , setuptools-scm
      }:

      buildPythonPackage rec {
        pname = "amaranth-boards";
        version = "0.0.0+unstable-2023-12-13";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-boards";
          rev = "170675812b71ee722bcf8ccdb88409a9ad97ffe2";
          sha256 = "sha256-9ZyzD4hOGW2sG24ISNwYBY6NiDe5q0rwDeMdYtzjwDA=";
        };

        postPatch = ''
          substituteInPlace pyproject.toml \
            --replace-fail '"amaranth>=0.4,<0.5",' ""
        '';

        nativeBuildInputs = [ setuptools setuptools-scm ];
        propagatedBuildInputs = [ amaranth ];

        # no tests
        doCheck = false;

        meta = with lib; {
          description = "Board definitions for Amaranth HDL";
          homepage = "https://github.com/amaranth-lang/amaranth-boards";
          license = licenses.bsd2;
          maintainers = with maintainers; [ emily thoughtpolice ];
        };
      };
  in prev.pythonPackagesExtensions ++ [
    (python-final: python-prev: {
      # upgrade to latest version
      amaranth = (python-prev.amaranth.overrideAttrs (o: {
        version = "0.0.0+unstable-2024-02-15";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "24a392887af19a9d013252759ec209d5a91a378a";
          hash = "sha256-i+TYmFZQ4C7IkZM+0zWcc1uVXE341mZS7o7U894ANik=";
        };
      }));

      amaranth-soc = python-final.callPackage amaranth-soc {};

      amaranth-boards = python-final.callPackage amaranth-boards {};
    })
  ];

  design = prev.lib.makeScope prev.newScope (self: with self; {
    amaranth_top = callPackage ./design/amaranth_top {};
    bitstream = callPackage ./design/bitstream {};
    linux_firmware = callPackage ./design/linux_firmware {};
    application = final.pkgsCross.armv7l-hf-multiplatform.python3Packages.callPackage ./design/application { };
  });
}
