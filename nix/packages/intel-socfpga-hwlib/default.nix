{ stdenvNoCC
, fetchFromGitHub
}:

stdenvNoCC.mkDerivation rec {
  pname = "intel-socfpga-hwlib";
  version = "23.08.02";

  src = fetchFromGitHub {
    owner = "altera-opensource";
    repo = "intel-socfpga-hwlib";
    rev = "rel_master_${version}_pr";
    hash = "sha256-uS6T2byu04cYn9YkLZtQr9uJoc50sRj+D9OApqEfFBk=";
  };

  installPhase = ''
    runHook preInstall

    mkdir -p $out
    cp -r * $out

    runHook postInstall
  '';
}
