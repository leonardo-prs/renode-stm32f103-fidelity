# ════════════════════════════════════════════════════════════════════════════════
#  flake.nix — STM32F103 Renode Fidelity TCC
#  Ambiente de desenvolvimento declarativo e reproduzível via Nix flake.
# ════════════════════════════════════════════════════════════════════════════════
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │ O QUE É UM FLAKE NIX?                                                   │
#  └─────────────────────────────────────────────────────────────────────────┘
#  Um "flake" é o formato moderno de empacotamento Nix. Pense nele como um
#  "package.json + lock file + Dockerfile" em um só arquivo:
#
#    - `inputs`     = dependências externas deste flake (análogo a deps npm).
#    - `outputs`    = o que ESTE flake expõe para o mundo. É o "produto":
#                     shells, pacotes, apps. Aqui só expomos um devShell.
#    - `flake.lock` = travado pelo Nix na primeira execução; congela versões
#                     exatas para reprodutibilidade. Após o primeiro
#                     `nix develop`, este arquivo aparece no repo. **DEVE ser
#                     commitado** para que outros devs e CI obtenham as
#                     mesmas versões.
#
#  O `flake.nix` é puramente DECLARATIVO: descreve "o que quero", não "como
#  instalar". Quem faz o trabalho é o `nix` ao executar.
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │ ESCOPO DESTA FLAKE                                                     │
#  └─────────────────────────────────────────────────────────────────────────┘
#  Apenas Linux x86_64. STM32F103 (Cortex-M3) é o alvo dos BINÁRIOS gerados
#  (cross-compile); o ambiente de DESENVOLVIMENTO roda exclusivamente em
#  x86_64-linux. Sem suporte a macOS, ARM, RISC-V, ou qualquer outro host.
#  Se você está em outro sistema operacional, este projeto não te atende.
#
#  WSL2 é aceito como host de desenvolvimento (o dev primário usa WSL2 com
#  Ubuntu), mas isso é transparente para o flake — WSL2 É Linux x86_64 do
#  ponto de vista do Nix. Ver README.md para detalhes da configuração WSL2.
#
  #  ┌─────────────────────────────────────────────────────────────────────────┐
  #  │ CANAL: nixos-26.05 (stable)                                               │
  #  └─────────────────────────────────────────────────────────────────────────┘
  #  Usamos `nixos-26.05` (stable 2026.05). POR QUÊ:
  #
  #    - Renode 1.16.1 está disponível em nixos-26.05 stable (ver
  #      https://search.nixos.org/packages?channel=26.05&query=renode),
  #      não sendo mais necessário recorrer a nixpkgs-unstable.
  #    - gcc-arm-embedded 15.2, cmake 4.1 etc também estão em 26.05.
  #    - O toolchain inteiro fica coerente: uma única resolução de versões.
  #
  #  Migração: projeto anteriormente em nixpkgs-unstable (Renode 1.16.1 só
  #  existia em unstable em 25.05). Com 26.05, migramos para o canal stable.
  #
  #  Reprodutibilidade continua via `flake.lock`, que pinna o hash exato
  #  do nixpkgs e de cada derivação. Enquanto ninguém rodar `nix flake update`,
  #  todos os devs (e a CI) obtêm exatamente as mesmas versões byte-a-byte.
  #
  #  Para atualizar: `nix flake update --commit` (atualiza o lock e commita).
  #  Para inspecionar o que está travado: `nix flake metadata`.
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │ UM ÚNICO SHELL — TUDO INCLUÍDO                                         │
#  └─────────────────────────────────────────────────────────────────────────┘
#  Diferente de projetos maiores, esta flake expõe APENAS UM `devShells.default`
#  com TODAS as ferramentas necessárias (incluindo STM32CubeMX). Justificativa:
#  o fluxo de trabalho deste TCC alterna frequentemente entre "compilar
#  firmware" e "ajustar o .ioc no CubeMX" — separar em dois shells seria
#  fricção sem benefício. O custo de puxar o CubeMX (~1.5 GB adicionais no
#  /nix/store) é aceitável para um projeto MVP.
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │ COMO USAR                                                              │
#  └─────────────────────────────────────────────────────────────────────────┘
#    1ª vez (cria o flake.lock):
#      $ nix develop                # entra no shell com tudo
#    Uso normal:
#      $ cmake -B build/sandbox -DSCENARIO=SANDBOX -G Ninja \
#             -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake
#      $ ninja -C build/sandbox
#    Editar o .ioc:
#      $ stm32cubemx                # GUI aparece (via WSLg no WSL2)
#    Sair:
#      $ exit
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │ PATH PRECEDENCE: NIX SHADOW APT AUTOMATICAMENTE                        │
#  └─────────────────────────────────────────────────────────────────────────┘
#  Quando você entra em um `nix develop`, o Nix PREPENDE `~/.nix-profile/bin`
#  ao PATH. Binários instalados via apt em `/usr/bin` ficam ENCOSTADOS
#  (shadowed). Para confirmar qual está em uso:
#
#      $ which arm-none-eabi-gcc
#      /home/<user>/.nix-profile/bin/arm-none-eabi-gcc     # ← do Nix
#      # vs /usr/bin/arm-none-eabi-gcc                     # ← apt (ignorado)
#
#  Não é necessário desinstalar pacotes apt. Basta entrar no shell.
#
#  ┌─────────────────────────────────────────────────────────────────────────┐
#  │ ST-LINK / OPENOCD — PERMISSÕES USB                                     │
#  └─────────────────────────────────────────────────────────────────────────┘
#  O OpenOCD precisa de permissão para falar com o ST-Link via USB. O pacote
#  `openocd` no nixpkgs vem com a regra udev em
#  `$out/etc/udev/rules.d/60-openocd.rules`. Para ativar:
#
#    - NixOS: adicione ao seu `configuration.nix`:
#        services.udev.packages = [ pkgs.openocd ];
#    - Ubuntu/Debian nativo:
#        sudo cp $(nix eval --raw nixpkgs#openocd)/etc/udev/rules.d/*.rules \
#                /etc/udev/rules.d/
#        sudo udevadm control --reload && sudo udevadm trigger
#    - WSL2: o ST-Link precisa ser ANEXADO via `usbipd-win` no PowerShell do
#      Windows ANTES de usar. Ver README.md seção WSL2.
#
#  Sem isso, `openocd` falha com "LIBUSB_ERROR_ACCESS" ao tentar abrir o
#  ST-Link.
#
# ════════════════════════════════════════════════════════════════════════════════

{
  # Aparece em `nix flake metadata` e em /nix/store. Documentação humana.
  description = "STM32F103 Renode Fidelity TCC — dev environment (Nix flake)";

  # ── INPUTS ────────────────────────────────────────────────────────────────
  # Pense como "package.json dependencies". Cada input vira uma variável
  # disponível dentro de `outputs`.
  inputs = {
    # nixpkgs: a "biblioteca" de pacotes do Nix (50.000+ pkgs). Canal
    # `nixos-26.05` = stable 2026.05. Ver bloco no header sobre a
    # migração de unstable para 26.05.
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  };

  # ── OUTPUTS ───────────────────────────────────────────────────────────────
  # `{ self, nixpkgs }: corpo` é uma FUNÇÃO. O destructuring extrai apenas
  # os campos nomeados do argumento (cada input declarado em `inputs` vira
  # uma variável aqui).
  outputs = { self, nixpkgs }:
    # `let ... in` é um bloco de bindings locais (variáveis calculadas uma
    # vez, usadas no `in` abaixo). Aqui calculamos `pkgs` e a lista de
    # ferramentas. Mantemos o `let` enxuto — sem grupos intermediários
    # porque não temos mais que separar "lean" vs "dev".
    let

      # ── pkgs: nixpkgs instanciado para x86_64-linux ─────────────────
      # `import nixpkgs` retorna uma função que recebe uma config e
      # devolve o conjunto de pacotes. Estamos customizando:
      #
      #   system = "x86_64-linux";
      #     → Hardcoded. Esta flake NÃO é multiplataforma (ver header).
      #       Se você está em outro host, este flake não te serve.
      #
      #   config.allowUnfree = true;
      #     → stm32cubemx é binário proprietário da ST Microelectronics.
      #       nixpkgs marca como `unfree` e se recusa a construir. Esta
      #       linha libera. É seguro pois confiamos explicitamente na
      #       fonte (ST oficial, hash pinned no package.nix).
      pkgs = import nixpkgs {
        system = "x86_64-linux";
        config.allowUnfree = true;
      };

      # ── Lista de ferramentas (em ordem: toolchain, build, debug, sim) ──
      # `with pkgs; [ ... ]` é um atalho: cada nome dentro do `[ ... ]` é
      # resolvido como `pkgs.nome`. Equivale a `using namespace` em C++.
      # Cuidado com colisões de nomes (raras, mas existem); aqui é seguro.
      tools = with pkgs; [

        # ARM toolchain: gcc, gdb, objcopy, ld, size, nm, addr2line, etc.
        # Todos prefixados com `arm-none-eabi-`. É a única coisa que CRUA
        # produz binários para o STM32F103 (Cortex-M3 ARMv7-M).
        # Versão 15.2.rel1 no canal unstable — suporta C11, C17, C18, C23.
        gcc-arm-embedded

        # Build system usado pelo nosso CMakeLists.txt raiz.
        # `cmake` configura; `ninja` executa (mais rápido que make).
        # `pkg-config` fica disponível para futuros módulos em `lib/` que
        # possam precisar consultar flags de libs externas.
        cmake
        ninja
        pkg-config

        # Flash / debug: openocd fala com o ST-Link (SWD) e expõe um
        # servidor GDB. NÃO incluímos um `gdb` genérico aqui porque:
        #   1. `gcc-arm-embedded` (acima) já provê `arm-none-eabi-gdb`
        #      cross-compilado para ARM — é O debugger certo para o
        #      nosso toolchain (mesma toolchain = mesmo target, sem
        #      ambiguidades de ABI ou convenções de chamada).
        #   2. Incluir `gdb` host polui o PATH com um binário x86_64
        #      capaz de debugar ARM, mas semanticamente errado para
        #      este projeto. Use `arm-none-eabi-gdb` direto.
        #   3. O antigo alias `gdb-multiarch` foi absorvido pelo `gdb`
        #      padrão em nixpkgs recente; não usamos nenhum dos dois.
        openocd

        # Simulador: Renode emula o STM32 inteiro em software, expondo
        # o mesmo servidor GDB na porta 3333. Versão 1.16.1 — exatamente
        # a que o projeto precisa (ver AGENTS.md).
        renode

        # Análise: python3 para scripts em `scripts/` (futuro dump_sram.sh,
        # gdb pretty-printers). `clang-tools` é o meta-pacote que produz
        # os binários `clangd`, `clang-tidy`, `clang-format` etc. (o LSP
        # que o VSCode usa consome o `compile_commands.json` que nosso
        # CMake gera).
        # Em nixpkgs-unstable, `clang-tools` (não `clang-tools-extra`
        # como em versões mais antigas) é o path correto dentro de
        # `llvmPackages_latest`.
        python3
        llvmPackages_latest.clang-tools

        # Configurador gráfico: GUI Java da ST para editar/regenerar o
        # `.ioc`. Requer display:
        #   - Linux nativo: X11/Wayland local, ou X11 forwarding via SSH.
        #   - WSL2: GUI nativa via WSLg (Win11) — sem config extra.
        #   - Sem display: shell funciona, GUI não abre.
        stm32cubemx
      ];

      # ── buildTools: subconjunto mínimo para COMPILAR firmware ──────────
      # Contiene apenas o necessário para `cmake` + `ninja` produzir o ELF.
      # Excluye renode/stm32cubemx (e o resto de `tools`) para que `nix develop`
      # não construa pacotes opcionales quebrados. `default` usa esta lista.
      buildTools = with pkgs; [
        gcc-arm-embedded
        cmake
        ninja
        pkg-config
      ];

    in
    {
      # ── DEVSHELLS ──────────────────────────────────────────────────────
      # Aqui saímos do `let ... in` e declaramos o que a flake expõe.
      # `devShells` é o campo padrão Nix para shells de desenvolvimento;
      # `nix develop` e `direnv` leem dele automaticamente.
      #
      # `devShells` é PER-SYSTEM: a chave de primeiro nível é o sistema
      # (`x86_64-linux`), e só então vem o nome do shell (`default`).
      # Sem a chave de sistema, `nix develop` não encontra o shell.
      devShells.x86_64-linux = {

        # ── SHELL DEFAULT (build mínimo) ────────────────────────────────
        # `nix develop` (sem args) e `direnv` (via `.envrc: use flake`)
        # entram aqui. Contiene apenas `buildTools` (toolchain ARM + build
        # system) para compilar firmware sem construir renode/stm32cubemx.
        #
        # `mkShell` é a função que cria um shell de desenvolvimento.
        # Aceita `packages` (lista de derivações a colocar no PATH do
        # shell) e `shellHook` (string executada na entrada).
        default = pkgs.mkShell {
          name = "stm32-renode-fidelity";

          packages = buildTools;

          # Cabeçalho mínimo + help curto (direnv log silenciado via .envrc).
          shellHook = ''
            echo "stm32-renode-fidelity — nix:build"
            echo "  cmake -B build/sandbox -DSCENARIO=SANDBOX -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake"
            echo "  ninja -C build/sandbox          # compilar"
            echo "  nix develop .#full              # renode/openocd/cubemx"
          '';
        };

        # ── SHELL FULL (todo incluído) ──────────────────────────────────
        # `nix develop full` entra aqui. Tem TUDO: toolchain ARM, build
        # system, flash, debug, simulação, IDE, CubeMX. Usa `tools`.
        full = pkgs.mkShell {
          name = "stm32-renode-fidelity-full";

          packages = tools;

          shellHook = ''
            echo "stm32-renode-fidelity — nix:full"
            echo "  cmake -B build/sandbox -DSCENARIO=SANDBOX -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake"
            echo "  ninja -C build/sandbox          # compilar"
            echo "  renode renode/sandbox.resc      # simular"
            echo "  openocd -f interface/stlink.cfg -f target/stm32f1x.cfg -c \"program build/sandbox/firmware.elf verify reset exit\"  # flash"
          '';
        };
      };
    };
}
