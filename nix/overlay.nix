final: prev: {
  quartus-prime-lite = final.callPackage ./packages/quartus-prime {
    supportedDevices = [ "Cyclone V" ];
  };

  soc_system = final.callPackage ./local/soc_system {};

  quartus = final.callPackage ./local/quartus {};
}
