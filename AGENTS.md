# AGENTS.md — Contexto do Projeto para Agentes LLM

## Resumo

TCC EA019 (UNICAMP): medir quantitativamente a fidelidade do simulador
**Renode** ao hardware real (**STM32F103C8T6 Blue Pill**, ARM Cortex-M3)
em firmware bare metal. Sete alvos compiláveis (ver § Cenários). Ambiente
de edição: **VS Code** (decisão 2026-10-05: Theia abandonado — pouco robusto;
extensões via Marketplace oficial da Microsoft, suíte verificada em
§ Extensões). O projeto independe de IDE: **tudo roda via terminal** (Nix +
presets + scripts) — o `.vscode/` é camada de conveniência.

## Separação de ambientes — código vs. TCC escrito

> **Este repositório é somente código e simulação.** Toda documentação,
> contexto/bibliografia e desenvolvimento dos textos entregáveis do TCC vive
> em **`C:\Users\Leonardo\projects\tcc`** (WSL: `/mnt/c/Users/Leonardo/projects/tcc`).
> Acesso liberado via `.opencode/opencode.jsonc` (`external_directory` restrito a
> `/mnt/c/Users/Leonardo/projects/tcc/**` — nada além disso em `C:\`). Não criar
> `docs/` ou `context/` aqui; usar o `tcc/` do Windows.

- **Fica aqui (Nix, versionado):** `src/`, `inc/`, `lib/`, `vendor/`, `renode/`,
  `scripts/`, `cmake/`, `.vscode/`, `CMakePresets.json`, `CMakeLists.txt`,
  `flake.nix`, `.editorconfig`.
- **Fica em `tcc/` (Windows, fora do Nix):** `docs/` (justificativa, plano),
  `context/` (bibliography, renode-docs, technical-literature), `contexto/`,
  `referencias/`, `latex/`, `normas/`, `_arquivo/`, monografia.
- `docs/` e `context/` foram **removidos deste repo** em 2025-08-31 após port verificado (hashes `b60a48cd` / `629a59c1`, `12M` idêntico, 44 arquivos).

## Questão central

> Em quais cenários e até qual nível de recurso de hardware o Renode
> produz resultados funcional e temporalmente equivalentes à execução
> em bancada física, dentro de margens aceitáveis?

## Hardware

| Item              | Valor                                |
|-------------------|--------------------------------------|
| MCU               | STM32F103C8T6 (Blue Pill)            |
| Memória           | 64 KB Flash @ 0x08000000, 20 KB SRAM |
| Clock             | **HSI 8 MHz**, sem HSE, sem PLL      |
| LED               | PC13, ativo-baixo                    |
| SWD               | PA13 (SWDIO), PA14 (SWCLK)           |
| Probe             | ST-Link/V2 via OpenOCD               |

**Por que HSI 8 MHz:** reset state do MCU, sem dependência de cristal
externo, drift de ±1% do HSI RC é **caracterizado na metodologia** (não é
bug), zero custo de migração de work validado, Renode não modela wait
states (a 24 MHz+ seria uma armadilha).

## Stack

- **Toolchain:** Nix flake (`nixpkgs/nixpkgs-unstable`). Shell único
  (`nix develop` → `default`, ativado por direnv `.envrc`) com **tudo**
  necessário: `gcc-arm-embedded` 15.3, `cmake` 4.4, `ninja` 1.13,
  `openocd` 0.12, `renode` 1.17.0 (`pkgs.renode`, suporta `I2C.STM32F1_I2C`),
  `python3`, `clang-tools` (clangd + clang-tidy), `pkg-config`.
  **Apenas x86_64-linux** (WSL2 ou Linux nativo).
- **Linguagem:** C17 GNU (`-std=gnu17`)
- **Build:** CMake + Ninja, orquestrado pelo `CMakeLists.txt` (raiz),
  presets em `CMakePresets.json` (Debug/Release → `build/Debug`,
  `build/Release`).
- **Simulador:** Renode (`.repl` + `.resc` em `renode/`)
- **Drivers:** STM32 Low Layer (LL) + CMSIS direto. **HAL proibido**
- **IDE:** **VS Code** — workspace config versionada em `.vscode/`
  (`extensions.json` da suíte Marketplace, `settings.json`, `tasks.json`,
  `launch.json` — portados de `.theia/` em 2026-10-05; refatoração fina das
  tasks/launch pendente, junto com a remoção do legado `.theia/`). Sem
  `.code-workspace`.

## Ambiente de edição (VS Code)

> Migração Theia → VS Code em 2026-10-05. A **fonte de extensões muda**
> (Open VSX → Marketplace oficial da Microsoft): disponibilidade e escolha
> de cada extensão foram reavaliadas uma a uma (§ Extensões). O projeto
> independe da IDE — todo o fluxo (build, sim, coleta, análise) roda via
> terminal com Nix; o `.vscode/` é camada de conveniência.

- **Abrir:** VS Code na raiz do projeto, no ambiente Linux/WSL onde o Nix
  existe. Para clangd/tasks encontrarem os binários: abrir o VS Code de um
  terminal com direnv ativo, **ou** instalar a extensão `mkhl.direnv`
  (recomendada) — ela aplica o `.envrc` ao ambiente do workspace. As tasks
  usam `scripts/direnv_exec.sh` (wrapper com guard: se o nix já está no
  PATH, não muda nada) — funcionam de qualquer jeito.
- **Config versionada em `.vscode/`:**
  - `extensions.json` — suíte Marketplace verificada (§ Extensões). O VS
    Code auto-instala `extensionDependencies` (o gap do Theia não se aplica).
  - `settings.json` — clangd, cortex-debug, higiene
    watcher/search (portado de `.theia/settings.json`, 2026-10-05).
  - `tasks.json` — refatorado (2026-10-06): `problemMatcher` = `$gcc`
    BUILT-IN do VS Code (casa compile e linker) nas build e nas debug-prep
    (o `--build` interno do prep agora surfar erros também); labels
    explícitos por cenário (referenciados pelo launch).
  - `launch.json` — refatorado (2026-10-06): `gdbPath`/`cwd` removidos dos
    configs (cobertos por `cortex-debug.gdbPath` no settings e pelo default
    do VS Code); `svdFile` = `vendor/svd/STM32F103.svd` em todos os configs
    (Peripheral Viewer: TIM2/USART1/GPIOC/RCC/EXTI); paths ELF explícitos
    mantidos — sem cmake-tools não há `${command:...}` útil. `type:
    cortex-debug` e `servertype` (`external`/`openocd`) do upstream
    `marus25.cortex-debug`.
- **Legado:** `.theia/` fica no disco até a refatoração de tasks/launch;
  depois é removida (junto dos forks `embedd-*` do contexto Open VSX).

### Extensões (VS Code Marketplace — fonte migrada em 2026-10-05)

> Suíte migrada do Open VSX (Theia) para o Marketplace oficial. A fonte
> muda, a disponibilidade muda, e a escolha de cada extensão também: os IDs
> abaixo foram verificados via API de query do Marketplace em 2026-10-05
> (versão/datas/installs). O contexto de lock-in Theia/Open VSX **não** se
> aplica mais — decisões técnicas (clangd vs cpptools, suíte ST) permanecem.

| Extensão | Papel | Nota (verificação 2026-10-05) |
|---|---|---|
| `llvm-vs-code-extensions.vscode-clangd` | LSP C/C++ | 4.6★, atual 2026-05; lê `.clangd` gerado pelo CMake |
| `twxs.cmake` | syntax CMake | 0.0.17/2017, mas é A gramática de CMake (46M installs) — só tmLanguage, sem build/LSP; zero interferência no fluxo. **Instalada localmente, mas FORA das recomendações do workspace** (decisão do usuário, 2026-10-06) |
| `marus25.cortex-debug` | debug Cortex-M | **upstream** (repo Marus/cortex-debug ativo: v1.13.0-pre10 2026-07, pushed 2026-10-04). Marketplace: estável 1.12.1 (2023-09) — pré-lançamentos só no GitHub/Open VSX. 1.12.1 cobre tudo que o projeto usa (`servertype external`/`openocd`, `gdbPath`, `openocdPath`). Auto-instala as 4 mcu-debug abaixo |
| `mcu-debug.debug-tracker-vscode` | tracker de sessão | 5.0★; auto-instalada (dep do marus25) |
| `mcu-debug.peripheral-viewer` | SVD viewer | atual 2026-09, engines >=1.107; p/ TIM2/USART1/PC13 (pendência: SVD no launch) |
| `mcu-debug.memory-view` | view de memória | atual 2026-01; SRAM/DWT (cenário A) |
| `mcu-debug.rtos-views` | RTOS views | auto-instalada; inócuo (bare-metal) |
| `ms-python.python` | scripts/ | analyze.py, renode_sweep.py |
| `ms-vscode.vscode-serial-monitor` | serial | **oficial MS** (o ID `ms-vscode.serial-monitor` não existe — verificado; 2.1M installs, atual 2025-11); Cenário B no HW real |
| `ms-vscode.hexeditor` | hex | inspeção de firmware.bin |
| `jnoortheen.nix-ide` | flake.nix | atual 2026-07, engines >=1.105 |
| `mkhl.direnv` | .envrc | aplica o direnv ao env do workspace — resolve clangd PATH |
| `EditorConfig.EditorConfig` | .editorconfig | atual 2026-04 |

**Sem equivalente no Marketplace (perda da migração):**
`embedd-team.embedd-build-analyzer` (flash/RAM por seção — só Open VSX).
Métrica por seção via terminal: `arm-none-eabi-size -A
build/<cenario>/firmware.elf` + `build/<cenario>/firmware.map`.

**Rejeitadas (decisão técnica, não disponibilidade):**
- `ms-vscode.cpptools` — IntelliSense conflita com clangd (source of truth =
  `.clangd` gerado); rating 3.4★.
- `ms-vscode.cmake-tools` — reavaliada 2026-10-06 (doc oficial do projeto):
  com `CMakePresets.json` presente ela usa o `binaryDir` do preset
  (`cmake.buildDirectory` é ignorado — a desinstalação de 2026-10-04 se
  deveu ao contexto Theia/tasks, não à árvore em si). Mas mantém um
  **segundo fluxo** — "active configure/build preset" selecionável na status
  bar — em paralelo ao fluxo único de tasks/scripts. O único ganho real
  (IntelliSense p/ editar CMakeLists.txt) não justifica. Se quiser editar
  CMake com completar: instalar manualmente; `cmake.configureOnOpen=false`
  (em settings) mantém o comportamento sob controle.
- `jeff-hykin.better-cpp-syntax` — REDUNDANTE (re-verificado 2026-10-06):
  o VS Code usa esta gramática como **fonte built-in** do highlight C e
  C++ — instalá-la não muda nada; e ela é só tmLanguage (sem LSP).
- `stmicroelectronics.stm32-vscode-extension` — ecossistema STM32Cube
  IDE/CubeCLT (verificado 2026-09-28: pack de 12+ extensões); workflow
  CubeMX descontinuado.
- `vadimcn.vscode-lldb` — LLDB; o debug aqui é GDB (`gcc-arm-embedded`) +
  cortex-debug.
- `embedd-team.*` — fork do cortex-debug, **só no Open VSX** (verificado:
  404 no Marketplace); removido na migração — upstream `marus25` cobre.

## Layout

```
renode-stm32f103-fidelity/
├── CMakeLists.txt                    # orquestrador (raiz) — user-owned
├── CMakePresets.json                 # presets PER-CENÁRIO → build/<cenario>
├── flake.nix, .envrc                 # ambiente único (toolchain completa)
├── .editorconfig                     # consistência entre máquinas/WSL
├── .vscode/                          # config VS Code VERSIONADA
│   ├── extensions.json, settings.json
│   ├── tasks.json, launch.json       (refatorados 2026-10-06; svdFile)
├── src/                              # nossos cenários (NÃO tocado pelo CubeMX)
│   ├── sandbox.c                     # blink LED PC13 (smoke test)
│   ├── c1_core.c                     # C1: núcleo/baseline
│   ├── c2_irq_baseline.c             # C2 (+ C2_BUSY_LOOP → c2busy)
│   ├── c3_irq_arbitration.c          # C3: arbitração de IRQ
│   ├── c4_usart.c                    # C4: USART1
│   └── echo_peer.c                   # echo USART peer
├── lib/                              # board.c/periph.c — init comum + periféricos
├── inc/                              # headers (reservado)
├── vendor/                           # ST/CMSIS CONGELADO (hashes em vendor/README.md)
│   ├── cmsis/, stm32f1xx_ll/         #   LL drivers, sem HAL
│   ├── startup_stm32f103xb.s, STM32F103XX_FLASH.ld
│   ├── system_stm32f1xx.c, syscalls.c, sysmem.c
│   └── reference/renode-stm32f103-fidelity.ioc   # .ioc arquivado (referência)
├── cmake/                            # toolchain + clangd.in (clangd gerado)
├── renode/                           # stm32f103_hsi8.repl + <cenario>.resc + PLAN.md
├── scripts/                          # run_hw.sh, dump_sram.sh, run_battery.sh,
│                                     # analyze.py, renode_sweep.py,
│                                     # direnv_exec.sh (wrapper p/ tasks VS
│                                     #   Code: garante nix no PATH antes do
│                                     #   direnv; guard — se nix, não muda)
│                                     # scenario_build.sh (configure+build per-
│                                     #   cenário via CMakePresets.json)
│                                     # renode_start.sh / renode_stop.sh (debug)
└── AGENTS.md                         # este arquivo (local, gitignored)
```

### Regras "intocado" vs "nosso"

- **`vendor/`:** ST/CMSIS congelado — **nunca editar**. Integridade por
  SHA-256 (`vendor/README.md`). O workflow CubeMX foi descontinuado: o
  `.ioc` é arquivado em `vendor/reference/` como referência histórica.
- **Nosso (`src/`, `lib/`, `inc/`, `renode/`, `scripts/`, `.vscode/`,
  `CMakePresets.json`, `CMakeLists.txt` raiz, `flake.nix`):** mantido à mão.
- **`.clangd`:** gerado por CMake (`configure_file(cmake/clangd.in)`) a cada
  configure — aponta para o `compile_commands.json` do preset atual (per-
  cenário: build/<cenario>). Ele segue o ÚLTIMO preset configurado — edite/
  compile o cenário que está trabalhando. Não editar manualmente.
- **`AGENTS.md`:** local, gitignored, mas legível pelo agente via `.ignore`.

## Build

```bash
# 1. Ambiente (1ª vez: cria flake.lock + baixa ~2 GB — pode demorar)
nix develop        # ou: direnv allow && cd re-stimulado

# 2. Configure + build via presets PER-CENÁRIO (um cenário por árvore)
cmake --preset c1                             # configura build/c1 (idempotente)
cmake --build --preset c1                     # compila o cenário
scripts/scenario_build.sh c1                  # atalho: configure + build

# 3. Artefatos — PATH ÚNICO (sem cópia sincronizada)
#    build/<cenario>/firmware.elf|bin|map — consumidos por .resc, launch.json,
#    scripts, gdb. Um cenário = uma árvore = um preset.

# 4. Limpar
cmake --build --preset c1 --target clean
```

No VS Code: as mesmas ações são tasks (`.vscode/tasks.json`, cópia direta
de `.theia/tasks.json`), sempre via wrapper `scripts/direnv_exec.sh`.

## Cenários e contratos

Cada cenário é um executável C independente (`add_scenario` no
CMakeLists.txt), com `firmware.elf` próprio em `build/<alvo>/`.
Mapeamento TCC: **Cenário A** (TIM2 + NVIC + GPIO + DWT) = `c1`/`c2`/
`c2busy`/`c3`; **Cenário B** (USART1 115200 8N1) = `c4`/`echo`.

| Alvo    | Fonte                    | Descrição                          |
|---------|--------------------------|------------------------------------|
| sandbox | `src/sandbox.c`          | blink LED PC13 (smoke test)        |
| c1      | `src/c1_core.c`          | núcleo/baseline                    |
| c2      | `src/c2_irq_baseline.c`  | IRQ baseline                       |
| c2busy  | idem, `-DC2_BUSY_LOOP`   | variante busy-loop (contraste)     |
| c3      | `src/c3_irq_arbitration.c` | arbitração de IRQ (DWT no handler) |
| c4      | `src/c4_usart.c`         | USART1 115200 8N1                  |
| echo    | `src/echo_peer.c`        | echo USART peer                    |

## Simulação e debug

- **Renode:** `renode/` contém a plataforma custom HSI 8 MHz
  (`stm32f103_hsi8.repl`) e um `.resc` por cenário (carrega ELF, sobe GDB
  `:3334`, quantum 1 µs). Diffs/justificativas: `renode/PLAN.md`.
- **Debug Renode:** no VS Code, config `Renode: <cenario> (:3334)` — o
  preLaunchTask (`Debug: prep <cenario>`) faz build do alvo + sobe Renode
  via `scripts/renode_start.sh` (mata instância anterior, espera a porta
  abrir). cortex-debug conecta com `servertype: external`. Exceções:
  `echo` não tem `.resc` nem config Renode (o peer roda SEM GDB na
  máquina-2 do `c4.resc` dual-machine; o preLaunchTask do c4 garante o
  `build/echo/firmware.elf`); `sandbox.resc` faz `start` no fim (o GDB
  conecta com o CPU já rodando — `runToEntryPoint` é inócuo, por design).
- **Debug HW:** config `HW: <cenario> (OpenOCD :3333)` — flash + debug via
  ST-Link. Headless: `scripts/run_hw.sh`.
- **Coleta:** `scripts/dump_sram.sh` (gdb), `scripts/run_battery.sh`
  (baterias Renode), `scripts/analyze.py` / `renode_sweep.py`.

## Convenções

- C17 GNU, `-Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes`
  no código nosso. Vendor compila com `-w` (congelado).
- `-ffunction-sections -fdata-sections -Wl,--gc-sections` (dead-code elim)
- Toda variável lida por ISR e por thread/GDB: `volatile`
- Sem `printf`/UART nos cenários — dados via GDB dump
- Todo handler de IRQ: protótipo antes da definição (satisfaz
  `-Wmissing-prototypes`)
- LL apenas. HAL proibido.
- Indentação/quebras: `.editorconfig` (formato neutro). JSONC do `.vscode/`
  com indent 2; C com 4.

## Pendente — tarefas futuras

- [x] `.theia/` completo (tasks/launch/settings/recomendações) no padrão
      nativo do Theia (2026-10-04); `dev-shell.sh`, `TCC.code-workspace`,
      `.vscode/` e `plan/` removidos.
- [x] Migração VS Code (2026-10-05): Theia abandonado (pouco robusto);
      `.vscode/` completo — `extensions.json` (suíte Marketplace verificada)
      + `settings/tasks/launch` portados de `.theia/` (tasks/launch = cópia
      direta). Legado `.theia/` no disco até a refatoração, depois removido.
- [x] Refatorar `.vscode/tasks.json` e `launch.json` (2026-10-06):
      `$gcc` nativo no matcher; `gdbPath`/`cwd` via settings/default;
      `svdFile` plumbado; comentários VS Code. `.theia/` ainda no disco
      (remoção em commit separado).
- [ ] Smoke test de debug no VS Code: config Renode (:3334) com breakpoint
      batendo em `main` (`postDebugTask` encadeia "Renode: stop" nativamente).
- [x] Verificação de coerência tasks/launch × presets/scripts (2026-10-06):
      config `Renode: echo` removido do launch (peer sem GDB por construção
      — machine-2 do c4.resc); task órfã `Debug: prep echo` removida;
      dependência c4→echo garantida em `renode_start.sh` (build do peer
      antes do DUT, preservando o `.clangd` no cenário debugado); smoke
      test do build sandbox OK via comando real da task.
- [ ] Smoke test no HW: `scripts/run_hw.sh` (OpenOCD) → LED pisca.
- [x] SVD do STM32F103 plumbado no `launch.json` (2026-10-06):
      `vendor/svd/STM32F103.svd` — download **direto da ST** (pack
      `STM32F1_svd_V1.2.zip`, st.com CAD resources; hash em
      `vendor/README.md`), validação cruzada bit-a-bit vs
      `modm-io/cmsis-svd-stm32` (idêntico pós-normalização CRLF); 67
      periféricos, TIM2/USART1/GPIOC/RCC/EXTI verificados.
- [ ] Validar `nix develop` em Linux nativo (WSL2 já validado).
- [x] Portado em 2025-08-31 para `C:\Users\Leonardo\projects\tcc\context/`
      (WSL: `/mnt/c/Users/Leonardo/projects/tcc/context/`): Yiu, Coleman,
      Baldassari, Buttazzo, H&P, PM0056, RM0008, docs Renode — **não** criar
      `context/` aqui
- [ ] Escrever `docs/decisoes-metricas-cenarios.md` e
      `docs/metodologia-cenario-a.md` do zero (não portadas do legado) —
      **em `C:\Users\Leonardo\projects\tcc\docs/`**
- [ ] Coletar dados HW e Renode, comparar quantitativamente

## Cross-references (quando criados)

- `renode/PLAN.md` — diffs e justificativas do `.repl`
- `renode/<cenario>.resc` — scripts de simulação
- `C:\Users\Leonardo\projects\tcc\docs\decisoes-metricas-cenarios.md` — metodologia completa, métricas
- `C:\Users\Leonardo\projects\tcc\docs\metodologia-cenario-a.md` — protocolo de medição
- `C:\Users\Leonardo\projects\tcc\docs\justificativa-metodologia.md` — fundamentação já portada (b60a48cd)
- `C:\Users\Leonardo\projects\tcc\docs\plano-execucao-cenarios.md` — plano já portado (629a59c1)
- `C:\Users\Leonardo\projects\tcc\context\` — bibliografia e manuais (12M)
- `README.md` — quickstart para humanos
