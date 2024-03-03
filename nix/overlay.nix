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
        version = "0.0.0+unstable-2024-02-16";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "9f46553aa4289e2a11788a73fade6410a371b162";
          hash = "sha256-ZllDSrZEu16jZtbQ7crQSj3XCbsthueXtaAvyf45dmY=";
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
        version = "0.0.0+unstable-2024-02-28";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-boards";
          rev = "b67996c48f1bc91412605acd7012f242514d3927";
          sha256 = "sha256-C1NFu3vBaplju1HKrfzJa/z78H0AN09CZ4f5CeBdVuw=";
        };

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
        version = "0.4.3+unstable-2024-03-03";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "127fe1fd2e33f94520ceff8e42f04383f5f10591";
          hash = "sha256-cuwsrnmloI8KTQ9dKH+GT5xL9UhXQSv+zV9DgoQBDg8=";
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
