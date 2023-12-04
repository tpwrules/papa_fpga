{ stdenvNoCC
, lib
, quartus-prime-lite
}:

stdenvNoCC.mkDerivation {
  name = "soc_system";

  src = lib.sources.sourceByRegex ./../../../design/soc_system [
    ".*\.qsys$"
  ];

  nativeBuildInputs = [ quartus-prime-lite ];

  buildPhase = ''
    runHook preBuild

    qsys-generate *.qsys -syn

    # remove log and report files
    rm */*.rpt
    rm */*.html

    # hack to remove access to FPGA interfaces from HPS
    HFILE=soc_system/synthesis/submodules/soc_system_hps_0_fpga_interfaces.sv
    # chop out module declaration
    head -n $(grep -n ');' $HFILE | head -n 1 | cut -d: -f1) $HFILE > hacked.sv
    echo endmodule >> hacked.sv # end the module so as to remove the contents
    mv hacked.sv $HFILE

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out
    cp -r * $out

    runHook postInstall
  '';
}
