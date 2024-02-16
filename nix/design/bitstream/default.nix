{ stdenvNoCC
, lib
, quartus-prime-lite
, amaranth_top
}:

stdenvNoCC.mkDerivation {
  name = "bitstream";

  src = "${amaranth_top}";

  nativeBuildInputs = [ quartus-prime-lite ];

  buildPhase = ''
    runHook preBuild

    pushd build
    sh build_top.sh
    popd

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out
    cp build/top.sof $out/bitstream.sof

    runHook postInstall
  '';
}
