# AGENTS.md — contexto do projeto para agentes LLM

Vale para **todos os workspaces jj** deste repositório (um por cenário).
É agnóstico ao cenário: o que é específico de um workspace fica na tabela
de estado abaixo — **mantê-la atualizada** ao abrir, avançar ou fechar um
workspace. O `README.md` de cada workspace é a documentação técnica do
cenário implementado nele (para terceiros); este arquivo só orienta agentes.

## Resumo

TCC EA019 (UNICAMP): mapear, para o STM32F103 (Blue Pill, Cortex-M3 r1p1,
HSI 8 MHz), até onde o **Renode 1.17.0** é fiel ao hardware em três níveis —
**funcional**, **instrução** e **ciclo** — por recurso e condição. Entrega
final: 2026-11-09, conforme `tmp/REQUISITOS-ENTREGA-FINAL-TCC.md` (gitignored;
a cópia existe no workspace `cenario1`: `../cenario1/tmp/` — manter esse
arquivo).

## Workspaces e estado (atualizar sempre)

```
jj workspace list        # nome → diretório irmão em ~/projects/
```

| Workspace | Dir | Cenário | Estado (2026-11-03) |
|---|---|---|---|
| `default` | `../renode-stm32f103-fidelity` | histórico (C1–C4 antigos) | só referência; não desenvolver aqui |
| `cenario1` | `../cenario1` | **C1** núcleo e acesso ao chip | implementado (presets `c1-*`, campanha `final-02`), **mas não é o definitivo**: o desenho do C1 será refeito conforme `tcc/documentacao/fundamentacao/03a-c1-auditoria.typ` e `03b-c1.typ` (o C1 fica por último, para cobrir o que C2–C4 usam — critério K1) |
| `c2` | `.` (`../c2`) | **C2** interrupções + caso Q | em desenvolvimento; nasceu de `cenario1`. **Limpo em 2026-11-03**: só o que vai para o produto final; C1 herdado, primeira implementação do C2, Q antigos e plano anterior em `tmp/legado/` (não versionado, índice em `tmp/legado/README.md`). Caso único de verificação dos instrumentos do Renode, **`Q-01` IGUAL 17/17** (reescrito e simplificado em 2026-11-03: `src/q/q.c`, `scripts/q.py`, `scripts/sim.py`, `data/q/piloto-01`; substitui o Q-01 antigo e o Q-02). **C2 redesenhado na fundamentação em 2026-11-03** (`04-c2.typ`): 16 casos em 5 etapas (1 regras `C2-01`–`04`, 2 tempo do núcleo `05`–`06`, 3 janelas por monitor `07`–`09`, 4 timers `10`–`12`, 5 placa #oP `13`–`16`), um firmware por etapa (etapas 1–2 compartilham). A primeira implementação (numeração antiga; o `C2-09` pilotado, IGUAL 30/30, é o `C2-01` novo) está em `tmp/legado/c2-primeira-implementacao/`. Próximo: etapas 1–2 do C2 nos moldes do Q-01 |
| `c3` | — | **C3** interface física | a criar |
| `c4` | — | **C4** comunicação serial | não iniciado |

Consequências práticas:

- O workspace contém só o que vai para o produto final. Material antigo
  (C1 herdado, primeira implementação do C2, versões anteriores do caso Q,
  plano anterior com C2 = timers/C3 = NVIC/C4 = USART1) fica em
  `tmp/legado/`, **não versionado e não apagado**: é contexto, não
  especificação. Manter essa pasta organizada (uma subpasta por origem,
  índice em `tmp/legado/README.md`); o que for retirado do workspace vai
  para lá, nunca para a lixeira. Tudo também está no histórico do jj.
- Antes de editar, confirmar em qual workspace se está (`jj workspace list`,
  `jj log`) — cada workspace tem o seu `@`.

## Versionamento e publicação

- **Workspaces e branches de trabalho são processo de desenvolvimento.**
  Neles o agente commita livremente (uma revisão por mudança coerente,
  mensagem descritiva); commits intermediários não são publicados.
- **`main` é o produto público.** O repositório GitHub ficará público só
  com a `main`, que hoje está limpa. No fim, o autor faz um único merge do
  produto final na `main`, com release e tag git dessa versão. Agentes
  **nunca** movem, mesclam ou dão push na `main` (nem em tags) sem pedido
  explícito do autor.
- Isso vale para este repositório de código. No jj do `tcc/` continua
  valendo: não commitar sem pedido do autor.

## Método × desenvolvimento (o que vai para o trabalho final)

O código e o texto finais devem ser **defensáveis pelo autor diante da
banca** (TCC, não mestrado): só o que ele consegue explicar linha a linha.
Critério para cada mecanismo: *se for retirado, algum veredito ou número do
trabalho muda ou fica sem sustentação?*

- **Sim → método:** fica no produto final, na forma mais simples possível
  (oráculo legível com citação, comparação, registro da campanha — SHA do
  ELF, versão do Renode, data —, repetições, e a verificação mínima dos
  instrumentos da família Q de que um resultado depende).
- **Não → desenvolvimento:** verificações que só pegam erro de construção
  (gate do ELF, testes de sensibilidade, regressão byte a byte, pyright,
  geradores de header) podem e devem ser usadas para confiança interna,
  mas ficam **separadas** do pipeline final (ex.: `scripts/dev/`) e fora da
  monografia (no máximo uma frase dizendo que existiram).
- Verificação de desenvolvimento **só pode abortar** ("pare e conserte");
  nunca filtra, corrige ou reclassifica dados. Se algo descarta ou muda um
  resultado, é método e tem de estar declarado.
- Firmware em C compilado é aceito sem demérito (ELF publicado com
  SHA-256); assembly só onde a instrução é o próprio objeto (nível de
  ciclo/instrução do C1), e aí o apêndice traz a listagem do `objdump`.
- Não acrescentar sofisticação ao pipeline final por iniciativa própria.

## Parte escrita: `tcc/` (symlink → `/mnt/d/tcc`)

> **Este repositório é somente código e simulação.** Monografia,
> documentação do projeto e bibliografia vivem em `tcc/` (Windows `D:\tcc`,
> um repositório jj/git próprio, com seu `AGENTS.md` — ler antes de editar
> lá). Não criar `docs/` ou `context/` aqui. Acesso externo restrito a
> `/mnt/d/tcc/**`.

```
tcc/
├── monografia/                   # texto final (template FEEC) — só mediante pedido do autor
├── documentacao/
│   ├── fundamentacao/            # ESPECIFICAÇÃO C1–C4 — somente leitura para agentes
│   ├── desenvolvimento/          # REGISTRO do que foi construído — agentes mantêm
│   └── legado/c1/                # material-base do C1 antigo — congelado, histórico
└── zotero/                       # references.bib + artefacts/<citekey>.pdf/.md
```

### `tcc/documentacao/fundamentacao/` — especificação (não alterar)

- `main.typ` (+ `main.pdf`; variantes `main-noite`/`main-sepia`) e capítulos
  `.typ`: `03-quadro-comum` (classes A/B/C/X, perguntas F/T/L, oráculo
  único D/P, vereditos, bancada), `03a`/`03b` (C1 revisto), `04-c2`,
  `05-c3`, `06-c4`, `07-integracao` (dependências entre cenários),
  `08-limites`. **É a especificação de C1–C4** e prevalece sobre o plano
  antigo. Identificadores de caso (`C2-05`, `C3-04`…) são estáveis e devem
  aparecer igual no firmware, nos dados, na análise e no desenvolvimento.
- Ler o `.typ` (texto); usar o PDF só para conferir figuras/tabelas.
- **Agentes não alteram a fundamentação por decisão própria — nunca.** Se
  encontrar erro, inconsistência com o hardware/manual, ou perceber que o
  autor está mudando uma premissa (no código, na conversa ou nos dados), o
  máximo permitido é **apontar o problema e oferecer** a reescrita do trecho;
  editar só com **autorização explícita** do autor para aquela mudança.
  Enquanto não houver autorização, a divergência é registrada no
  desenvolvimento (ver abaixo), não corrigida na fundamentação.

### `tcc/documentacao/desenvolvimento/` — registro (agentes mantêm)

- Documenta **o que foi construído e por quê**, naquilo que a fundamentação
  não decidiu: decisões de implementação e seus motivos (e alternativas
  descartadas), convenções (nomes, layout de memória, formato de registro,
  CLI), instrumentos e sua validação, pré-requisitos (ex.: `Q-01`),
  campanhas executadas (nome, ELF/SHA, ambiente, data), resultados e
  vereditos por caso, problemas encontrados e como foram resolvidos,
  divergências percebidas em relação à fundamentação.
- **Não é cópia do código.** Não colar fonte nem pseudocódigo do que já
  está implementado aqui; referenciar o arquivo/símbolo
  (`src/q/…`, `scripts/q.py`, preset, campanha em `data/<cN>/<n>/`) e
  explicar a decisão. Trecho curto só quando ele é o próprio objeto da
  decisão (ex.: a sequência de instruções que define um estímulo).
- **Manter atualizado de forma automática, sem pedir confirmação**: ao
  concluir uma decisão, um instrumento, uma campanha ou uma análise neste
  workspace, registrar no desenvolvimento na mesma sessão. Fatos verificados
  (com caminho/ID), não planos; o que for hipótese aparece como tal.
- Organização: um arquivo `.typ` por frente (ex.: `comum.typ`,
  `familia-q.typ`, `c2.typ`, …), incluído em `main.typ`; cada workspace edita
  principalmente a sua frente. Usar o `lib.typ` local (etiquetas de caso
  `clA`…`clX`, `qF`/`qT`/`qL`, `oD`/`oP` da fundamentação). Após editar,
  compilar sem erro:
  `cd /mnt/d/tcc && typst compile --font-path /mnt/c/Windows/Fonts --root . documentacao/desenvolvimento/main.typ`
  (o typst é snap: não grava em `/tmp`). Não commitar no jj do `tcc/` sem
  pedido do autor.
- O `README.md` de cada workspace continua sendo a documentação técnica de
  uso do código (para terceiros); o desenvolvimento é o registro de
  decisões e resultados para o TCC.

### Demais

- `tcc/documentacao/legado/c1/` — material-base do C1 antigo (campanha
  `final-02` já executada): especificação do código `c1-*` atual, só
  histórico; não alterar (não compila mais: citekey removido do `.bib`).
- **Referências (Zotero, coleção do TCC):** `tcc/zotero/references.bib`
  (citekeys) e `tcc/zotero/artefacts/<citekey>.pdf` + `<citekey>.md`. Todo
  PDF tem o `.md` com o texto **na íntegra** (OCR via `ocr2md`;
  `sync_ocr2md.py`). Para fundamentar uma escolha de implementação, citar
  pelo citekey + localização (ex.: `stmicroelectronics2021` §27.3.5),
  lendo o `.md`. Os citekeys da documentação e da monografia são os mesmos.
- Outros: `tcc/tmp/docs/` (justificativa, plano de execução antigo),
  `tcc/tmp/reports/` (relatório intermediário, `hardware.md`).

## Princípios de método (de `documentacao/fundamentacao/`)

- **Renode como caixa-preta**: expectativas sobre o Renode vêm só da
  documentação pública e dos resultados do C1, nunca do código-fonte (o
  fonte instalado, `/nix/store/*renode-1.17.0/lib/renode/src/`, serve para
  diagnosticar, não para justificar expectativas).
- **Um oráculo por caso**: `oD` (documento → roda só no Renode, estímulo
  exato, varredura completa) ou `oP` (placa → mesmo binário nos dois
  ambientes). Instrumento falho = EVIDÊNCIA INVÁLIDA, nunca divergência.
- "Ciclo" = HCLK 8 MHz; "tick" = unidade de contador (`DWT_CYCCNT`,
  `TIMx_CNT`).

## Build e fluxo (comum a todos os workspaces)

- Ambiente: `nix develop` (ou direnv, `.envrc` = `use flake`).
- Um preset CMake por firmware, `-O2 -g3`, sem HAL/LL, só headers CMSIS:
  `cmake --workflow --preset <preset>` → `build/<preset>/`. **Zero warnings
  é política.** Presets em `CMakePresets.json`; o `.clangd` é gerado no
  configure.
- Molde de um caso (critério método × desenvolvimento): um firmware em C
  (`src/<caso>/`, preset próprio) e um script Python só com a biblioteca
  padrão (`scripts/<caso>.py`) que gera o `.resc` de cada execução, roda o
  Renode por `scripts/sim.py`, compara com a referência do caso e escreve
  `data/<caso>/<campanha>/resultado.md` com o ambiente. Sem gerador de
  header, gate ou testes no pipeline final; verificações de
  desenvolvimento ficam fora dele.
- Q-01 (instrumentos do Renode, só Renode):
  ```
  python3 scripts/q.py --name <n> [--reps 2] [--no-build]   # build do zero + bare/full × reps + resultado.md
  python3 scripts/q.py --name <n> --analyze
  ```
  Instrumentos presos a periférico ficam nos cenários; nos casos #oD,
  estímulo e observação vão, sempre que possível, para eventos que o Q-01
  verificou (escrita do firmware, entrada em tratador, valor lido) — ver
  `03-quadro-comum.typ` §Verificação dos instrumentos do Renode.
- C2: 16 casos em 5 etapas (`04-c2.typ` §Como o C2 está organizado), um
  firmware por etapa (etapas 1–2 compartilham); a implementar no molde
  acima.
- Renode: plataforma `renode/stm32f103_hsi8.repl`, perfil R1 (8 MIPS,
  quantum 125 ns) em todos os casos; `renode/debug.resc` só para depuração
  no VS Code (`scripts/renode_start.sh <preset>`, GDB em :3334).

## Regras

- `vendor/` congelado (nunca editar; SHA-256 em `vendor/README.md`).
- Bancada (placa única, ver identidade abaixo). Fios conforme
  `03-quadro-comum.typ` §Bancada: **J1 PA2→PB11** (C4), **J2 PA6→PA0**
  (C3); J0 PA9→PA10 continua soldado mas **não é usado** — nenhum firmware
  aciona USART1/PA9/PA10.
  Segurança elétrica: nunca duas saídas push-pull no mesmo fio; pinos dos
  fios ficam como entrada até o caso configurá-los; fios só com a placa
  desligada. Confirmar com o autor quais fios estão montados antes de um
  caso `oP`.
- OpenOCD próprio na :3333 (porta ocupada = erro; nunca `pkill`/kill
  global). Renode em portas ≥ 3336 (debug: 3334). Workspaces diferentes
  compartilham a mesma placa e as mesmas portas — nunca rodar campanhas
  de dois workspaces ao mesmo tempo.
- Renode com `-e` + `--port N` só executa quando um cliente telnet conecta →
  usar `--port -1`; em erro de comando o Renode fica parado (sempre timeout).
- Placa do TCC (única): STM32F103C8T6 ST original (marcação `991KA 93 /
  MYS 809`), CPUID 0x411FC231 (Cortex-M3 r1p1), IDCODE 0x20036410 (DEV
  0x410, rev Y/X), ROM table JEP106 0x20 (ST), UID `0a0b0200 30301624
  32303030`, F_SIZE informa 128 KiB (atípico p/ C8; irrelevante — binários
  < 64 KiB).
- Nunca rebuildar presets durante uma campanha: o Renode carrega o ELF de
  `build/` e cada run registra o SHA-256 do ELF.
- Sem `printf`/UART como canal de log (a USART é objeto de estudo do C4,
  não instrumento); variáveis compartilhadas com ISR `volatile` e com um
  único escritor; todo handler com protótipo.

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

- `README.md` — documentação técnica do cenário deste workspace
- `tcc/AGENTS.md` — orientação para o repositório do TCC escrito
- `tcc/documentacao/fundamentacao/main.typ` — especificação vigente de C2–C4 (e do C1 revisto); não alterar sem autorização
- `tcc/documentacao/desenvolvimento/main.typ` — registro de decisões e resultados; agentes mantêm
