{ stdenvNoCC
, lib
, quartus-prime-lite
}:

stdenvNoCC.mkDerivation {
  name = "soc_system";

  src = lib.sources.sourceByRegex ./../../../src/qsys [
    ".*\.qsys$"
  ];

  nativeBuildInputs = [ quartus-prime-lite ];

  buildPhase = ''
    runHook preBuild

    qsys-generate *.qsys -syn

    # remove log and report files
    rm */*.rpt
    rm */*.html

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out
    cp -r * $out

    runHook postInstall
  '';
}
