# AGENTS.md — contexto do projeto para agentes LLM (local, gitignored)

## Resumo

TCC EA019 (UNICAMP): mapear, para o STM32F103 (Blue Pill, Cortex-M3, HSI
8 MHz), até onde o **Renode 1.17.0** é fiel ao hardware em três níveis —
**funcional**, **instrução** e **ciclo** — por recurso e condição. Entrega
final (2026-11-09) conforme a diretiva `tmp/REQUISITOS-ENTREGA-FINAL-TCC.md`
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
- **Referências (Zotero, coleção do TCC):** `tcc/zotero/` —
  `references.bib` (citekeys) e `artefacts/<citekey>.pdf` + `<citekey>.md`.
  Todo PDF da coleção tem o `.md` com o texto **na íntegra** (OCR via
  `ocr2md`; `sync_ocr2md.py`). Para ler/citar uma referência, preferir o
  `.md`; usar o PDF só para conferir figuras/tabelas.
- `docs/` e `context/` foram **removidos deste repo** em 2025-08-31 após port verificado (hashes `b60a48cd` / `629a59c1`, `12M` idêntico, 44 arquivos).

## Estrutura e fluxo — novo C1 (workspace jj `cenario1`)

Especificação: `tcc/material-base/main.typ` (+ `c1/*.typ`). Este workspace
reimplementa o C1 do zero; C2–C4 (`src/c2..c4`, `lib/`, `inc/`,
`scripts/fidelity*`, `renode/fidelity.resc`) ficam só como contexto e serão
removidos pelo autor no fim.

- Firmwares (um preset cada, `-O2 -g3`, sem HAL/LL, só headers CMSIS):
  `c1-func` (vetores funcionais em lotes), `c1-layout` (FID/LAY, 2 lotes: normal
  e reset por software), `c1-cycle` (T-DWT e microbenchmarks diferenciais).
  `src/c1/common/`: startup próprio (captura do reset), `c1.ld`, registro
  C1S1 (`c1.h`), falta-e-retoma (`fault.S`), `call.S` (rótulos do stepi).
- Catálogo = fonte única (`scripts/c1/`): `func/<grupo>.py` ↔
  `src/c1/func/<grupo>.S`, `cycle/*.py` ↔ `src/c1/cycle/*.S`, `layout.py`.
  O CMake gera `build/<preset>/gen/c1_{config,catalog}.h` (`python -m c1 gen`);
  o hash do catálogo vai para o snapshot. Oráculo: `arm.py` (testes em
  `scripts/c1/tests`). Gate: `disasm.py` confere cada rótulo `_x<k>`.
- CLI: `scripts/c1.sh {campaign,analyze,run,trace,check}`. Dados em
  `data/c1/<campanha>/` (gitignored); análise em `analysis/report.md`.
- Renode: `renode/c1.resc` + perfis `renode` (`stm32f103_hsi8.repl`, a
  plataforma do projeto) e `renode-doc` (`c1_doc.repl`: só correções
  documentadas). 8 MIPS, quantum 125 ns.
- Fonte do Renode instalado: `/nix/store/*renode-1.17.0/lib/renode/src/`.
- Build: `cmake --workflow --preset <preset>` (zero warnings é política).

## Regras

- `vendor/` congelado (nunca editar; SHA-256 em `vendor/README.md`).
- Bancada: fio PA9→PA10 permanente — só o C4 toca USART1/PA9/PA10 (o gate
  verifica literais no ELF). OpenOCD próprio na :3333 (porta ocupada = erro;
  nunca `pkill`/kill global). Renode em portas ≥ 3336 (debug: 3334).
- Renode com `-e` + `--port N` só executa quando um cliente telnet conecta →
  usar `--port -1`; em erro de comando o Renode fica parado (sempre timeout).
- Placa do TCC (única): STM32F103C8T6 ST original (marcação `991KA 93 /
  MYS 809`), CPUID 0x411FC231 (Cortex-M3 r1p1), IDCODE 0x20036410 (DEV 0x410,
  rev Y/X), ROM table JEP106 0x20 (ST), UID `0a0b0200 30301624 32303030`,
  F_SIZE informa 128 KiB (atípico p/ C8; irrelevante — binários < 64 KiB).
- Nunca rebuildar presets durante uma campanha: o Renode carrega o ELF de
  `build/` e cada run registra o SHA-256 do ELF.
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
