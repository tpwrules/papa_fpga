final: prev: {
  quartus-prime-lite = prev.quartus-prime-lite.override {
    supportedDevices = [ "Cyclone V" ];
    withQuesta = false;
  };

  vde2 = prev.vde2.override (old: {
    wolfssl = old.wolfssl.overrideAttrs (old: {
      configureFlags = builtins.filter (f: (f != "--enable-intelasm") && (f != "--enable-aesni")) old.configureFlags;
    });
  });

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
        version = "0.0.0+unstable-2024-06-10";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-soc";
          rev = "e1b842800533f44924f21c3867bc2290084d100f";
          hash = "sha256-GAGQEncONY566v8hLjGeZ7CRlOt36vHg+0a5xcB+g1Y=";
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
      , pdm-backend
      }:

      buildPythonPackage rec {
        pname = "amaranth-boards";
        version = "0.0.0+unstable-2024-06-22";
        format = "pyproject";

        src = fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth-boards";
          rev = "ad5a939b86020c53e0e193620b96ca19d5960192";
          sha256 = "sha256-1a0LhDVSl0fSyRXwn/jf8JhvPwvZtlDc1pWKh4g+OW8=";
        };

        nativeBuildInputs = [ pdm-backend ];
        propagatedBuildInputs = [ amaranth ];

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
      amaranth = (python-prev.amaranth.overridePythonAttrs (o: {
        version = "0.5.0";

        src = final.fetchFromGitHub {
          owner = "amaranth-lang";
          repo = "amaranth";
          rev = "a0750b89c6060d9f809159a012a26cff4e22e69d";
          hash = "sha256-+EV2NgYSuCbYTQKeBUN+/D0attfrJ3cso7U6RjLEIbg=";
        };

        dependencies = (o.dependencies or []) ++ [
          python-final.jschon
        ];
      }));

      amaranth-soc = python-final.callPackage amaranth-soc {};

      amaranth-boards = python-final.callPackage amaranth-boards {};

      jschon = python-final.buildPythonPackage {
        pname = "jschon";
        version = "0.11.1";

        src = final.fetchFromGitHub {
          owner = "marksparkza";
          repo = "jschon";
          rev = "v0.11.1";
          hash = "sha256-uOvEIEUEILsoLuV5U9AJCQAlT4iHQhsnSt65gfCiW0k=";
          fetchSubmodules = true;
        };

        propagatedBuildInputs = [ python-final.rfc3986 ];

        checkInputs = [
          python-final.pytest
          python-final.pytest-httpserver
          python-final.hypothesis
        ];
      };
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
