{ stdenv
, lib
, quartus-prime-lite
, dtc
, bitstream
}:

stdenv.mkDerivation {
  name = "linux_firmware";

  src = lib.sources.sourceByRegex ./../../../design/linux_firmware [
    "[^/]*\.cof$"
    "[^/]*\.dtso$"
  ];

  nativeBuildInputs = [ quartus-prime-lite dtc ];

  postUnpack = ''
    cp -r ${bitstream}/* source/
    chmod -R u+w source/
  '';

  buildPhase = ''
    runHook preBuild

    quartus_cpf -c sof_to_rbf.cof

    dtc -O dtb -o bitstream.dtbo -b 0 -@ bitstream.dtso

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/firmware
    cp bitstream.rbf bitstream.dtbo $out/lib/firmware

    runHook postInstall
  '';
}
