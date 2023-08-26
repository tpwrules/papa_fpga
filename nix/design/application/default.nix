{ stdenv
, lib
, intel-socfpga-hwlib

, quartus-prime-lite
, soc_system
}:

stdenv.mkDerivation {
  name = "application";

  src = ./../../../design/application;

  nativeBuildInputs = [ quartus-prime-lite ];

  makeFlags = [
    "CROSS_COMPILE=${stdenv.cc.targetPrefix}"
    "HWLIBS_ROOT=${intel-socfpga-hwlib}/armv7a/hwlib"
  ];

  preBuild = ''
    # generate SoC header file
    # we need to do some Tcl gymnastics to both locate the executables to do
    # this, and to run them in the environment with all their libraries
    SOPC_PATH=$(echo ${soc_system}/*.sopcinfo)
    quartus_sh --tcl_eval puts "[exec [file join \\\$quartus(binpath) ../sopc_builder/bin/sopcinfo2swinfo] --input=$SOPC_PATH --output=design.swinfo]"
    quartus_sh --tcl_eval puts "[exec [file join \\\$quartus(binpath) ../sopc_builder/bin/swinfo2header] --swinfo design.swinfo --single hps_0.h --module hps_0]"
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin
    cp HPS_FPGA_LED $out/bin

    runHook postInstall
  '';
}
