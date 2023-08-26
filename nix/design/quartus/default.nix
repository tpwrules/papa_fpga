{ stdenvNoCC
, lib
, quartus-prime-lite
, soc_system
}:

stdenvNoCC.mkDerivation {
  name = "quartus";

  src = lib.sources.sourceByRegex ./../../../design/quartus [
    "ip/?[^.]*"
    "ip/.*\.qip$"
    "ip/.*\.v$"
    "[^/]*\.qpf$"
    "[^/]*\.qsf$"
    "[^/]*\.sdc$"
    "[^/]*\.v$"
    "[^/]*\.tcl$"
  ];

  nativeBuildInputs = [ quartus-prime-lite ];

  postUnpack = ''
    cp -r ${soc_system}/* source/
    chmod -R u+w source/
  '';

  buildPhase = ''
    runHook preBuild

    quartus_sh --flow compile *.qpf

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out
    cp *.sof $out/quartus.sof

    runHook postInstall
  '';
}
