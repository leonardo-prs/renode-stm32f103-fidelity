# flake.nix — development environment of the project (x86_64-linux only;
# WSL2 counts as x86_64 Linux). Versions are pinned by flake.lock.
#
#   nix develop                          # or direnv (.envrc: use flake)
#   cmake -B build -G Ninja              # configure once
#   cmake --build build                  # every firmware → build/<fw>/firmware.elf
#
# ST-Link over USB needs the udev rule shipped with openocd
# ($out/etc/udev/rules.d/60-openocd.rules); on WSL2 the ST-Link must be attached
# with usbipd-win first (README.md, "How to reproduce").
{
  description = "STM32F103 Renode Fidelity TCC — dev environment (Nix flake)";

  inputs = {
    # nixpkgs-unstable carries Renode 1.17.0 as pkgs.renode
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; };
      tools = with pkgs; [
        gcc-arm-embedded            # arm-none-eabi-gcc, objcopy, objdump, nm, size
        cmake
        ninja
        openocd                     # board: flash and run through the ST-Link (SWD)
        renode                      # simulator; renode-test uses its own embedded Python
        python3                     # scripts/ (standard library only)
        llvmPackages_latest.clang-tools   # clangd (LSP over build/compile_commands.json)
      ];
    in
    {
      devShells.x86_64-linux.default = pkgs.mkShell {
        name = "stm32-renode-fidelity";
        packages = tools;
        # clangd asks the ARM compiler of compile_commands.json for the target and
        # the system headers (newlib), instead of the host glibc. clangd reads
        # CLANGD_FLAGS from the environment, so it holds for any client of this shell.
        CLANGD_FLAGS = "--query-driver=${pkgs.gcc-arm-embedded}/bin/arm-none-eabi-gcc";
      };
    };
}
