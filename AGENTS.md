# AGENTS.md — contexto do projeto para agentes LLM (local, gitignored)

## Resumo

TCC EA019 (UNICAMP): mapear, para o STM32F103 (Blue Pill, Cortex-M3, HSI
8 MHz), até onde o **Renode 1.17.0** é fiel ao hardware em três níveis —
**funcional**, **instrução** e **ciclo** — por recurso e condição. Entrega
final (2026-10-09) conforme a diretiva `tmp/REQUISITOS-ENTREGA-FINAL-TCC.md`
(manter esse arquivo). **O README.md é a documentação técnica completa** (para
terceiros); este arquivo só orienta agentes.

## Separação de ambientes — código vs. TCC escrito

> **Este repositório é somente código e simulação.** Toda documentação,
> contexto/bibliografia e desenvolvimento dos textos entregáveis do TCC vive
> em **`D:\tcc`** (WSL: `/mnt/d/tcc`).
> Acesso liberado via `.opencode/opencode.jsonc` (`external_directory` restrito a
> `/mnt/d/tcc/**` — nada além disso em `D:\`). Não criar
> `docs/` ou `context/` aqui; usar o `tcc/` do Windows.

- **Fica aqui (Nix, versionado):** `src/`, `inc/`, `lib/`, `vendor/`, `renode/`,
  `scripts/`, `cmake/`, `.vscode/`, `CMakePresets.json`, `CMakeLists.txt`,
  `flake.nix`, `.editorconfig`.
- **Fica em `tcc/` (Windows, fora do Nix):** `docs/` (justificativa, plano),
  `context/` (bibliography, renode-docs, technical-literature), `contexto/`,
  `referencias/`, `latex/`, `normas/`, `_arquivo/`, monografia.
- `docs/` e `context/` foram **removidos deste repo** em 2025-08-31 após port verificado (hashes `b60a48cd` / `629a59c1`, `12M` idêntico, 44 arquivos).

## Estrutura e fluxo (entrega final)

- Firmwares (um `main` por preset, `-O2 -g3`, LL/CMSIS, sem HAL):
  `c1-functional`, `c1-timing` (`src/c1/`), `c2` (`src/c2/timers.c`),
  `c3` (`src/c3/nvic.c` — NVIC), `c4` (`src/c4/usart.c` — USART). Ordem do
  plano: C3 = NVIC, C4 = USART (a numeração antiga s3/s4 era invertida).
- ABI v3 "FID3": `inc/fidelity.h`, `lib/fidelity.c`, `lib/fidelity_measure.S`;
  decodificador `scripts/fidelity/abi.py`.
- Campanha: `scripts/campaign.sh` → `scripts/fidelity.py campaign` (pacote
  `scripts/fidelity/`: targets, campaign, instr, c1..c4, analysis, perfetto,
  figures, report). Dados em `data/fidelity/<campanha>/` (gitignored);
  `data/exploratory/` = coletas antigas (ABI v1/v2), fora da análise.
- Renode: `renode/stm32f103_hsi8.repl` + script único `renode/fidelity.resc`
  (8 MIPS, quantum 125 ns, loopback USART1, AutoUpdateDelay off). Fonte da
  versão instalada: `/nix/store/*renode-1.17.0/lib/renode/src/`.
- Build: `cmake --workflow --preset <fw>`. Ambiente: `nix develop`/direnv
  (inclui numpy, matplotlib e `trace_processor_shell` v58.2).

## Regras

- `vendor/` congelado (nunca editar; SHA-256 em `vendor/README.md`).
- Bancada: fio PA9→PA10 permanente — só o C4 toca USART1/PA9/PA10 (o gate
  verifica literais no ELF). OpenOCD próprio na :3333 (porta ocupada = erro;
  nunca `pkill`/kill global). Renode em portas ≥ 3336 (debug: 3334).
- Renode com `-e` + `--port N` só executa quando um cliente telnet conecta →
  usar `--port -1`; em erro de comando o Renode fica parado (sempre timeout).
- Placa atual: provável clone (UID zero, CPUID r2p0, F_SIZE 128 KiB, USART
  bufferiza ≥ 8 bytes sem ORE, ~110 ciclos extras na 1ª execução de cada
  trecho de flash). Dados dela são preliminares; a campanha final deve rodar
  na placa genuína.
- `tests/` só existiu durante o desenvolvimento (resultados no README); não
  faz parte da árvore final.
- Sem `printf`/UART fora do C4; variáveis compartilhadas com ISR `volatile` e
  com um único escritor; todo handler com protótipo.

## Extensões (VS Code Marketplace — fonte migrada em 2026-10-05)

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

## Cross-references

- `README.md` — escopo, bancada, campanha, ABI, oráculos, critérios, validações
- `D:\tcc\` — plano de trabalho, bibliografia, monografia (fora do repo)
