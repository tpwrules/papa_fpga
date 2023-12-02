{ stdenvNoCC
, lib
, python3
, yosys
}:

let
  pyEnv = python3.withPackages (p: [
    p.amaranth
    p.amaranth-soc
    p.numpy
  ]);

in stdenvNoCC.mkDerivation {
  name = "amaranth_top";

  # TODO: fix source specification
  src = lib.sources.sourceByRegex ./../../../design/amaranth_top [
    "amaranth_top"
    ".*/[^/]*\.py$"
  ];

  nativeBuildInputs = [ pyEnv yosys ];

  buildPhase = ''
    runHook preBuild

    mkdir -p $out
    python3 -m amaranth_top.top $out/amaranth_top.v

    runHook postBuild
  '';
}
