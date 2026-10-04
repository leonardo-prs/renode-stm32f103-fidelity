# AGENTS.md — Contexto do Projeto para Agentes LLM

## Resumo

TCC EA019 (UNICAMP): medir quantitativamente a fidelidade do simulador
**Renode** ao hardware real (**STM32F103C8T6 Blue Pill**, ARM Cortex-M3)
em firmware bare metal. Três artefatos compiláveis: `sandbox` (teste
genérico), `scenario_a` (TIM2 + NVIC + GPIO + DWT), `scenario_b`
(USART1 115200 8N1).

## Separação de ambientes — código vs. TCC escrito

> **Este repositório é somente código e simulação.** Toda documentação,
> contexto/bibliografia e desenvolvimento dos textos entregáveis do TCC vive
> em **`C:\Users\Leonardo\projects\tcc`** (WSL: `/mnt/c/Users/Leonardo/projects/tcc`).
> Acesso liberado via `.opencode/opencode.jsonc` (`external_directory` restrito a
> `/mnt/c/Users/Leonardo/projects/tcc/**` — nada além disso em `C:\`). Não criar
> `docs/` ou `context/` aqui; usar o `tcc/` do Windows.

- **Fica aqui (Nix, versionado):** `Core/`, `Drivers/`, `src/`, `inc/`, `lib/`, `renode/`, `scripts/`, `cmake/`, `startup_*`, `*.ld`, `*.ioc`, `flake.nix`, `CMakeLists.txt`.
- **Fica em `tcc/` (Windows, fora do Nix):** `docs/` (justificativa, plano), `context/` (bibliography, renode-docs, technical-literature), `contexto/`, `referencias/`, `latex/`, `normas/`, `_arquivo/`, monografia.
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
  (`nix develop` → `default`) com **tudo** necessário:
  `gcc-arm-embedded` 15.3 (C11/C17/C18/C23, inclui `arm-none-eabi-gdb`),
  `cmake` 4.4, `ninja` 1.13, `openocd` 0.12, `renode` 1.17.0 (`pkgs.renode`),
  `python3`, `clang-tools` (clangd + clang-tidy),
  `pkg-config`. **Apenas x86_64-linux**.
  Renode 1.17.0 está disponível nativamente no canal unstable do nixpkgs
  (suporta `I2C.STM32F1_I2C`), dispensando overrides customizados.
  Sem `gdb` standalone — `arm-none-eabi-gdb` (mesma toolchain, target
  consistente) já vem no `gcc-arm-embedded`.
  Ver `README.md` para instalação (recomendado: Determinate Nix).
- **Linguagem:** C17 GNU (`-std=gnu17`)
- **Build:** CMake + Ninja, orquestrado pelo `CMakeLists.txt` (raiz)
- **Simulador:** Renode (`.repl` + `.resc` em `renode/`)
- **Drivers:** STM32 Low Layer (LL) + CMSIS direto. **HAL proibido** nos cenários
- **IDE:** VSCode + Cortex-Debug (perfis HW e Renode compartilham o ELF)

## Layout

```
renode-stm32f103-fidelity/
│
├── ST padrão (regenerável por CubeMX) ─────────────────────────
├── renode-stm32f103-fidelity.ioc     # source of truth do HW
├── .mxproject                        # CubeMX metadata
├── Core/Inc, Core/Src                # CubeMX-gerado;
│                                     # main.c com USER CODE BEGIN 2 modificado
├── Drivers/CMSIS, Drivers/STM32F1xx_HAL_Driver   # INTOCÁVEL (ST vendor)
├── startup_stm32f103xb.s             # @ raiz (convenção ST)
├── STM32F103XX_FLASH.ld              # @ raiz (convenção ST)
├── cmake/                            # CubeMX-gerado, NÃO modificar
│   ├── gcc-arm-none-eabi.cmake       # toolchain file
│   └── stm32cubemx/CMakeLists.txt    # INTERFACE lib stm32cubemx
├── CMakeLists.txt                    # NOSSO orquestrador (raiz) — manually maintained
│
├── nosso código (NÃO tocado pelo CubeMX) ──────────────────────
├── src/
│   ├── sandbox.c                     # teste genérico — SCENARIO=SANDBOX
│   ├── scenario_a.c                  # TIM2 + NVIC + GPIO + DWT (futuro)
│   └── scenario_b.c                  # USART1 115200 8N1 (futuro)
├── inc/                              # headers — incluído por padrão
├── lib/                              # módulos compartilhados (sob demanda)
│
├── simulador + tooling + meta ────────────────────────────────
├── renode/                           # stm32f103_hsi8.repl, *.resc, PLAN.md (futuro)
├── scripts/                          # flash_stlink.sh, dump_sram.sh (futuro)
├── flake.nix, .envrc, .gitignore, .ignore
└── AGENTS.md                         # este arquivo (local, gitignored)
```

### Regra "intocado" vs "nosso"

- **ST vendor (`Drivers/`):** nunca modificar.
- **CubeMX-gerado, regenerado em "Generate Code":**
  `Core/`, `startup_stm32f103xb.s`, `STM32F103XX_FLASH.ld`,
  `cmake/stm32cubemx/CMakeLists.txt`, `cmake/gcc-arm-none-eabi.cmake`.
  Exceção: blocos `USER CODE BEGIN/END` em `Core/Src/*.c` são preservados.
- **CubeMX-gerado, MAS user-owned (preservado em regen):**
  `CMakeLists.txt` da raiz. Documentado pela ST como "one-time generated,
  user change is kept". Modifica à vontade.
- **Nosso (`src/`, `inc/`, `lib/`, `renode/`, `scripts/`, `flake.nix`):**
  manualmente mantido.
- **`.opencode/opencode.jsonc`:** permissão `external_directory` para `/mnt/c/Users/Leonardo/projects/tcc/**` — não ampliar para `/mnt/c/**` sem pedir.
- **Proibido criar aqui:** `docs/`, `context/` — vivem em `tcc/` do Windows (ver Separação acima). Qualquer doc novo vai para `/mnt/c/Users/Leonardo/projects/tcc/docs/` ou `context/`.
- **`AGENTS.md`:** local, gitignored, mas legível pelo agente via `.ignore`.
- **`.clangd`:** gerado por CMake via `configure_file(cmake/clangd.in)` a
  cada configure. Não editar manualmente; mudar o nome do build dir exige
  reconfigure.

### Workflow quando reabrires o `.ioc`

O `.ioc` tem `ProjectManager.TargetToolchain=CMake`. Ao clicar "Generate Code":

- **Sobrescreve:** `Core/`, `startup_*`, `*_FLASH.ld`, `cmake/stm32cubemx/`,
  `cmake/gcc-arm-none-eabi.cmake`. Esperado.
- **Preserva (user-owned):** `CMakeLists.txt` raiz. O nosso orquestrador
  sobrevive. Se algo quebrar (raro — só em mudança de toolchain ou project
  name), restaura do git: `git checkout HEAD -- CMakeLists.txt`.
- **Não toca:** `src/`, `inc/`, `lib/`, `renode/`, `scripts/`, `flake.nix`,
  `README.md`, `AGENTS.md`, `.clangd` (o último é gerado por CMake).

## Build

```bash
# 1. Ativar ambiente (1ª vez: cria flake.lock + baixa ~2 GB — pode demorar)
nix develop

# 2. Configurar (uma vez por cenário)
cmake -B build/sandbox -DSCENARIO=SANDBOX -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake

# 3. Build
ninja -C build/sandbox
# → build/sandbox/firmware.elf

# 4. Limpar
ninja -C build/sandbox clean   # só build/
rm -rf build/sandbox/         # tudo
```

O shell Nix tem **todas** as ferramentas (incluindo STM32CubeMX).
Para editar o `.ioc`: `stm32cubemx` (GUI aparece, via WSLg em WSL2).

Cenários disponíveis: `SANDBOX` (→ `src/sandbox.c`), `A` (→ `src/scenario_a.c`),
`B` (→ `src/scenario_b.c`).

## Cenários e contratos

Cada app em `src/<cenario>.c` exporta **uma única função**:
`<cenario>_main(void)`, chamada por `Core/Src/main.c` quando a flag
correspondente está definida. A função **não retorna** — controla o loop
principal (`__WFI()` no caso dos cenários A/B).

| Cenário        | Flag build         | Função             | Status        |
|----------------|--------------------|--------------------|---------------|
| Sandbox        | `-DSCENARIO=SANDBOX` | `sandbox_main()`   | ✅ implementado (blink LED) |
| Cenário A      | `-DSCENARIO=A`     | `scenario_a_main()` | 🔲 placeholder; ver Pendente |
| Cenário B      | `-DSCENARIO=B`     | `scenario_b_main()` | 🔲 placeholder; ver Pendente |

## Convenções

- C17 GNU, `-Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes`
  no código nosso. Vendor passa com warnings.
- `-ffunction-sections -fdata-sections -Wl,--gc-sections` (dead-code elim)
- Toda variável lida por ISR e por thread/GDB: `volatile`
- Sem `printf`/UART nos cenários — dados via GDB dump
- Todo handler de IRQ: protótipo antes da definição (satisfaz
  `-Wmissing-prototypes`)
- `Core/Src/stm32f1xx_it.c` zerado (só fault handlers default). Cada
  app define seus handlers no próprio `.c` (override do `weak` default)
- LL apenas. HAL proibido.

## Pendente — tarefas futuras (k e l do plano original)

### k — Smoke test + Renode + scripts

- [ ] Smoke test no HW: `openocd -f interface/stlink.cfg -f target/stm32f1x.cfg
      -c "program build/sandbox/firmware.elf verify reset exit"` → LED pisca
- [ ] Smoke test no Renode: `.resc` mínimo carrega o mesmo ELF
- [ ] `renode/stm32f103_hsi8.repl` — portado e customizado para HSI 8 MHz:
      clock dos 14 timers = 8 MHz, `systickFrequency` = 1 MHz,
      `dwt.frequency` = 8 MHz, `Tag RCC_CR` = 0x00000083
- [ ] `renode/sandbox.resc`, `renode/scenario_a.resc`, `renode/scenario_b.resc`
      — 1 por cenário, cada um carrega seu ELF + sobe GDB :3333
- [ ] `renode/PLAN.md` — diffs e justificativas do `.repl`
- [ ] `scripts/flash_stlink.sh` — wrapper openocd
- [ ] `scripts/dump_sram.sh` — wrapper gdb-multiarch para extrair buffer DWT
- [ ] `.vscode/settings.json`, `tasks.json`, `launch.json` — 2 perfis
      debug Cortex-Debug (HW openocd + Renode :3333)
- [ ] Validar `nix develop` em WSL2 (1ª vez: ~600-800 MB, 30-60 s)
- [ ] Validar `nix flake lock` e `nix develop` em Linux nativo

### l — Implementar cenários + Drivers LL faltando

- [ ] Reabrir `.ioc` no CubeMX, configurar:
      HSI 8 MHz (sem PLL), TIM2 update IRQ, USART1 115200 8N1
- [ ] CubeMX regenera Core/, Drivers/, startup, linker, cmake/
      → adicionar `ll_tim.c` e `ll_usart.c` ao build
- [ ] Restaurar `CMakeLists.txt` da raiz do git (ver Workflow acima)
- [ ] `src/scenario_a.c` — TIM2 PSC=799 ARR=999 → 100 ms @ 8 MHz,
      DWT CYCCNT no IRQHandler, buffer circular 1024, extração via GDB
- [ ] `src/scenario_b.c` — USART1 115200 8N1, sem DMA, padrão fixo
      de bytes (0x55/0xAA)
- [ ] `lib/dwt/`, `lib/clock_init/`, etc. — criado sob demanda quando
      2+ cenários precisarem do mesmo código
- [x] Portado em 2025-08-31 para `C:\Users\Leonardo\projects\tcc\context/` (WSL: `/mnt/c/Users/Leonardo/projects/tcc/context/`):
      Yiu, Coleman, Baldassari, Buttazzo, H&P, PM0056, RM0008, docs Renode — **não** criar `context/` aqui
- [ ] Escrever `docs/decisoes-metricas-cenarios.md` e
      `docs/metodologia-cenario-a.md` do zero (não portadas do legado) — **em `C:\Users\Leonardo\projects\tcc\docs/`**
- [ ] Coletar dados HW e Renode, comparar quantitativamente
- [ ] `README.md` — quickstart para clone+build (criar quando o smoke test passar)

## Cross-references (quando criados)

- `renode/PLAN.md` — diffs e justificativas do `.repl`
- `renode/<cenario>.resc` — scripts de simulação
- `C:\Users\Leonardo\projects\tcc\docs\decisoes-metricas-cenarios.md` — metodologia completa, métricas
- `C:\Users\Leonardo\projects\tcc\docs\metodologia-cenario-a.md` — protocolo de medição
- `C:\Users\Leonardo\projects\tcc\docs\justificativa-metodologia.md` — fundamentação já portada (b60a48cd)
- `C:\Users\Leonardo\projects\tcc\docs\plano-execucao-cenarios.md` — plano já portado (629a59c1)
- `C:\Users\Leonardo\projects\tcc\context\` — bibliografia e manuais (12M)
- `README.md` — quickstart para humanos
