final: prev: {
  quartus-prime-lite = final.callPackage ./packages/quartus-prime {
    supportedDevices = [ "Cyclone V" ];
  };

  design = prev.lib.makeScope prev.newScope (self: with self; {
    soc_system = callPackage ./design/soc_system {};
    quartus = callPackage ./design/quartus {};
  });
}
