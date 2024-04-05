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
        version = "0.0.0+unstable-2024-03-26";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "8b1de15973edf51ebe4d5c86a1c9704b17578483";
          hash = "sha256-f8RuFLc3cJuFqgHsp008hB4iM32QE3Qn/VjsJt1cBUE=";
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
        version = "0.4.5+unstable-2024-04-04";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "6857daff54bfa208b26a88a822a697105026902c";
          hash = "sha256-PZ8i4mWUl1h3VTa0iZ0MD6GRIjerxGIuhcPPwsK/xNQ=";
        };
      }));

      amaranth-soc = python-final.callPackage amaranth-soc {};

      amaranth-boards = python-final.callPackage amaranth-boards {};
    })
  ];

  # git rev needed for latest amaranth
  yosys = prev.yosys.overrideAttrs (old: {
    version = "0.39";

    src = final.fetchFromGitHub {
      owner = "YosysHQ";
      repo = "yosys";
      rev = "22c5ab90d1580b6d515a58cf1c8be380d188b989";
      hash = "sha256-uOzWb611Y9d7zYbdqwSXNOurgLLHlANrLKdtFCa7IdA=";
    };

    # remove patch that doesn't apply and we don't care about
    patches = builtins.filter (p: !(final.lib.strings.hasInfix "fix-clang-build.patch" (builtins.toString p))) old.patches;

    # remove now in tree patch by converting to nop
    postPatch = builtins.replaceStrings ["tail +3"] ["tail -n +3"] old.postPatch;
  });

  # git rev needed for latest yosys
  abc-verifier = prev.abc-verifier.overrideAttrs (old: {
      src = final.fetchFromGitHub {
        owner = "yosyshq";
        repo  = "abc";
        rev   = "0cd90d0d2c5338277d832a1d890bed286486bcf5";
        hash  = "sha256-1v/HOYF/ZdfR75eC3uYySKs2k6ZLCTUI0rtzPQs0hKQ=";
      };
  });

  design = prev.lib.makeScope prev.newScope (self: with self; {
    amaranth_top = callPackage ./design/amaranth_top {};
    bitstream = callPackage ./design/bitstream {};
    linux_firmware = callPackage ./design/linux_firmware {};
    application = final.pkgsCross.armv7l-hf-multiplatform.python3Packages.callPackage ./design/application { };
  });
}
