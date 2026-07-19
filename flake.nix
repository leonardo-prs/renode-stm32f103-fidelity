{
  description = "STM32F103 Renode Fidelity TCC — dev shell (Nix flake)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          name = "stm32-renode-fidelity";

          packages = with pkgs; [
            # ARM toolchain (gcc, gdb, objcopy, objdump, size, etc.)
            gcc-arm-embedded

            # Build system
            cmake
            ninja

            # Flash + debug
            openocd          # 0.12.x — driver ST-Link built-in

            # Simulador
            renode           # 1.15.3

            # Análise e IDE
            python3
            gdb-multiarch    # GDB com Python (pretty-printers CMSIS)
            clangd           # LSP para VSCode
            pkg-config
          ];

          # Garante que o ST-Link é visível via udev quando em Linux nativo.
          # Em WSL2 o usbipd-win cuida do passthrough antes do attach.
          shellHook = ''
            echo ""
            echo "STM32F103 Renode Fidelity — dev shell"
            echo "======================================="
            echo ""
            echo "Verificações:"
            command -v arm-none-eabi-gcc >/dev/null && arm-none-eabi-gcc --version | head -1 || echo "  arm-none-eabi-gcc: FALTA"
            command -v cmake            >/dev/null && cmake --version            | head -1 || echo "  cmake: FALTA"
            command -v ninja            >/dev/null && ninja --version            | head -1 || echo "  ninja: FALTA"
            command -v openocd          >/dev/null && openocd --version          | head -1 || echo "  openocd: FALTA"
            command -v renode           >/dev/null && renode --version           | head -1 || echo "  renode: FALTA"
            command -v gdb-multiarch    >/dev/null && gdb-multiarch --version    | head -1 || echo "  gdb-multiarch: FALTA"
            command -v clangd           >/dev/null && clangd --version           | head -1 || echo "  clangd: FALTA"
            echo ""
            echo "Build de smoke (sandbox):"
            echo "  cmake -B build/sandbox -DSCENARIO=SANDBOX -G Ninja \\"
            echo "        -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake"
            echo "  ninja -C build/sandbox"
            echo ""
          '';
        };
      }
    );
}
