{ stdenvNoCC
, lib
, quartus-prime-lite
, amaranth_top
}:

stdenvNoCC.mkDerivation {
  name = "bitstream";

  src = lib.sources.sourceByRegex ./../../../design/bitstream [
    "ip/?[^.]*"
    "ip/.*\.qip$"
    "ip/.*\.v$"
    "[^/]*\.qpf$"
    "[^/]*\.qsf$"
    "[^/]*\.sdc$"
    "[^/]*\.v$"
    "[^/]*\.tcl$"
  ];

  postUnpack = ''
    cp -r ${amaranth_top}/* source/
    chmod -R u+w source/
  '';

  buildPhase = ''
    runHook preBuild

    ${quartus-prime-lite}/bin/quartus_sh --flow compile *.qpf

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out
    cp *.sof $out/bitstream.sof

    runHook postInstall
  '';
}
