final: prev: {
  quartus-prime-lite = prev.quartus-prime-lite.override {
    supportedDevices = [ "Cyclone V" ];
    withQuesta = false;
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
        version = "0.0.0+unstable-2024-04-10";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "ce4ad768dc590c38de0d76a560e76a94a615a782";
          hash = "sha256-C5mxh0sGoTDWWVT07emJ8mQr6zIXxA02Uym9RV8ecDs=";
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
        version = "0.0.0+unstable-2024-04-18";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-boards";
          rev = "8be265b8ed89c1bbb4d9785a14dcfa415898a9d7";
          sha256 = "sha256-vEw3LgdKaKLBurw07q/MKCaZNB028+vS59SZbMmrxeI=";
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
        version = "0.4.5+unstable-2024-04-20";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "9201cc3179d53c9fcfb6443e571533d64dbdd417";
          hash = "sha256-oIGcLM5Xa9hzSZar9+4oYgidEuugmC/idt1cb1bOkuo=";
        };

        patches = (o.patches or []) ++ [
          # requires PDM functionality we don't have
          (final.fetchpatch {
            url = "https://github.com/amaranth-lang/amaranth/commit/3fbed68365fb4f0ab5b14e305167467845adbd95.patch";
            hash = "sha256-sTvX3+IAFRlidrqLTzqGh/CodJSR6zDaLqviaoPD8kA=";
            revert = true;
          })
        ];
      }));

      amaranth-soc = python-final.callPackage amaranth-soc {};

      amaranth-boards = python-final.callPackage amaranth-boards {};
    })
  ];

  # git rev needed for latest amaranth
  yosys = prev.yosys.overrideAttrs (old: {
    version = "0.40";

    src = final.fetchFromGitHub {
      owner = "YosysHQ";
      repo = "yosys";
      rev = "refs/tags/yosys-0.40";
      hash = "sha256-dUOPsHoknOjF9RPk2SfXKkKEa4beQR8svzykhpUdcU0=";
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
