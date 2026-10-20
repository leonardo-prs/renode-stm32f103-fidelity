# Renode × STM32F103 — Cenário C1: núcleo e memória (TCC EA019, UNICAMP)

Código, plataforma de simulação e campanha automática do **Cenário C1** do TCC
*"Análise quantitativa da fidelidade funcional e temporal do Renode em relação
ao hardware no STM32F103"*. A especificação completa do cenário é o
**material-base do C1** (fora deste repositório, `tcc/material-base/main.typ`);
este README documenta a implementação e como reproduzi-la. A monografia não
está aqui.

O C1 executa, **na placa e no Renode, o mesmo binário** com um conjunto
fechado de operações do núcleo Cortex-M3 r1p1 e da memória do STM32F103, e
compara três lados para cada operação:

| Lado | O que é |
|---|---|
| **Especificação** | oráculo calculado no host a partir do pseudocódigo do ARMv7-M ARM ou de valores tabelados (TRM r1p1, PM0056, RM0008) — `scripts/c1/arm.py` |
| **Placa** | o ELF executado no STM32F103C8T6 da bancada |
| **Renode** | o mesmo ELF no Renode 1.17.0, em dois perfis de plataforma |

nos três níveis de fidelidade do TCC:

| Nível | Pergunta | Evidência |
|---|---|---|
| **Funcional** | resultados, flags, memória e faltas são iguais? | vetores comparados bit a bit com o oráculo e entre ambientes (`c1-func`, `c1-layout`) |
| **Instrução** | a mesma sequência dinâmica de instruções é executada? | traço por `stepi` na placa e no Renode (mesmo script GDB) |
| **Ciclo** | o custo em ciclos de cada operação é igual? | `DWT_CYCCNT` em microbenchmarks diferenciais, com teste de linearidade exato (`c1-cycle`) |

> **Workspace.** Este workspace (jj `cenario1`) reimplementa o C1. As pastas
> dos cenários C2–C4 (`src/c2..c4`, `lib/`, `inc/`, `scripts/fidelity*`,
> `renode/fidelity.resc`) continuam aqui só como contexto e não fazem parte do
> C1.

---

## 1. Início rápido

```bash
nix develop                         # ou direnv allow; ver §2
scripts/c1.sh check                 # build do zero dos 3 presets + gate do ELF
scripts/c1.sh campaign --name piloto-01 --mode pilot --board "stm32f103c8-st-tcc" --no-trace
scripts/c1.sh campaign --name final-01  --mode final --board "stm32f103c8-st-tcc" --pilot-from piloto-01
# relatório: data/c1/final-01/analysis/report.md
```

Diagnóstico de um lote isolado (fora de campanha):

```bash
scripts/c1.sh run   --env hw|renode|renode-doc --preset c1-func  --batch 0
scripts/c1.sh run   --env renode --preset c1-cycle --batch 0 --iters 2 --profile
scripts/c1.sh trace --env hw --preset c1-func --batch 4      # traço por stepi
PYTHONPATH=scripts python3 -m unittest discover -s scripts/c1/tests -t scripts   # testes do oráculo
```

## 2. Bancada e ambiente

**Placa (exemplar único):** STM32F103C8T6 original da ST (marcação
`991KA 93 / MYS 809`) numa Blue Pill, ST-Link/V2 em SWD. Identidade lida pelo
depurador a cada sessão e conferida contra o plano: CPUID `0x411FC231`
(Cortex-M3 **r1p1**), IDCODE `0x20036410`, JEP106 `0x20` (ST), UID
`0a0b0200 30301624 32303030`, F_SIZE 128 KiB (atípico para o C8; os binários
têm menos de 64 KiB). Relógio: **HSI 8 MHz**, sem PLL, flash com 0 estados de
espera (estado de reset; o C1 não toca no RCC). O fio PA9→PA10 da bancada não
é tocado: o gate recusa ELF que referencie a USART1 (literal em qualquer seção
carregada ou par MOVW/MOVT).

**Software** (tudo pelo `flake.nix`, travado no `flake.lock`): GCC Arm 15.3,
CMake 4 + Ninja, OpenOCD 0.12, Renode 1.17.0, Python 3 com matplotlib.

**WSL2:** anexar o ST-Link a cada sessão (PowerShell do Windows):
`usbipd attach --wsl --busid <id>` (o `bind` é feito uma vez).

## 3. Firmwares (presets)

Um preset = um firmware = `build/<preset>/firmware.elf`, `-O2 -g3`. O C1
**não** usa HAL, LL, `SystemInit` nem o startup/.ld do vendor (só os headers
CMSIS de `vendor/`, que é congelado).

| Preset | Conteúdo | Lotes |
|---|---|---|
| `c1-func` | instruções, memória e exceções síncronas: grupos FA, FL, FS, FM, FD, FQ, FB, FC, FMEM, FAL, FBB, FEX, FSY, FEN — 546 formas, 31 521 vetores | 23 (por nível: N1 primeiro; um terminal, dois isolados) |
| `c1-layout` | identidade e estado de reset (FID-01..07), layout de memória (LAY-01..10) | 2 (normal; reset por software) |
| `c1-cycle` | validação do `DWT_CYCCNT` (T-DWT) e custo por classe de instrução (T-ALU … T-COMP) — 227 variantes | 10 |

Comum (`src/c1/common/`):

- `startup.S` — tabela de vetores e `Reset_Handler`. As **primeiras
  instruções** depois do reset gravam LR, SP, CONTROL, máscaras, IPSR e os
  registradores do SCB/DWT/RCC em `.noinit` (FID-03/04), antes de qualquer
  escrita; depois copiam `.data`/`.ramfunc` e zeram `.bss`.
- `c1.ld` — `.ram_vectors` em `0x20000000` (LAY-06), `.ramfunc` (VMA na SRAM,
  LMA na flash), `.noinit`, `.psp`; seções NOLOAD com LMA = VMA (o `LoadELF`
  do Renode preenche com zeros o endereço físico de cada segmento).
- `fault.S` — **falta e retoma**: tratador único de HardFault/MemManage/
  BusFault/UsageFault; o caso publica a aterrissagem, o tratador grava
  CFSR/HFSR/MMFAR/BFAR/PC/xPSR/EXC_RETURN/IPSR, limpa CFSR e HFSR (W1C), põe
  PC = aterrissagem com bit 0 = 0, T = 1 e ITSTATE = 0, e retorna. Aterrissagem
  vazia = falta inesperada → run inválido (ou caso terminal).
- `call.S` — `c1_call`: toda rotina de teste é chamada por aqui; os rótulos
  `c1_call_go`/`c1_call_back` delimitam o traço por stepi.
- `c1.h`/`c1.c` — o registro **C1S1** (abaixo).

## 4. Registro de resultados (ABI "C1S1")

Um único objeto, `c1_snapshot`, lido pelo GDB depois que o firmware para em
`c1_complete()` (nada é lido durante a execução):

```
header   64 palavras: magic/versão/tamanho, preset, hash do catálogo, estado,
         erros, nonce/lote/iterações (cópia do bloco do host), identidade,
         clock, margem de pilha, falta inesperada, cópia da captura do reset
records  {id, status, primeira palavra, nº de palavras} por forma/variante
words    saídas BRUTAS (o firmware não compara nada; quem julga é o host)
```

O host escreve `c1_host` (nonce aleatório, lote, iterações, flags) quando o
alvo para em `main`; o nonce copiado no header prova que o snapshot é deste
run. O decodificador (`scripts/c1/abi.py`) recusa qualquer layout, contagem
ou estado incoerente.

## 5. O catálogo: uma fonte para firmware, oráculo e disassembly

`scripts/c1/` é a fonte única de três coisas que precisam concordar:

| | Firmware | Oráculo | Gate |
|---|---|---|---|
| `func/<grupo>.py` ↔ `src/c1/func/<grupo>.S` | eixos de vetores (produto cartesiano) e a rotina | `oracle(vetor) → campos esperados` | instrução, largura e operandos em `<rotina>_x<k>` |
| `cycle/*.py` ↔ `src/c1/cycle/*.S` | blocos K/2K/3K, registradores, setup | previsão TRM r1p1 e H-T1 | 1ª unidade e alinhamento |
| `layout.py` ↔ `src/c1/layout/` | ordem dos registros | valores do TRM/PM0056/RM0008 | — |

O CMake roda `python -m c1 gen` e gera `build/<preset>/gen/c1_catalog.h` (tabelas
de vetores, lotes, variantes) e `c1_config.h` (capacidades e o **hash do
catálogo**, gravado no snapshot: o host recusa ELF de outro catálogo).

**Moldes assembly** (`src/c1/func/moldes.inc`, `src/c1/cycle/blocks.inc`):
toda rotina funcional faz (1) flags via `MSR APSR_nzcvq` e operandos via `LDR`,
(2) **a instrução sob teste**, marcada por `<rotina>_x<k>`, (3) `MRS APSR`, (4)
saídas brutas. Instruções que o montador recusa para o M3 entram com `.inst`.

**Oráculo** (`scripts/c1/arm.py`): `AddWithCarry`, `Shift_C`,
`DecodeImmShift`, `ThumbExpandImm_C`, `SignedSatQ`/`UnsignedSatQ`,
`ConditionPassed`, `ITAdvance`, divisão com `RoundTowardsZero`, campos de bits,
multiplicação longa, bit-band — testado contra os exemplos resolvidos das
fontes (Yiu Tab. 4.7 com a linha 2 corrigida, `0x80000000/−1`, PM0056 §3.3.4,
RM0008 §3.3.2, ITSTATE de FEN-09).

**Gate do ELF** (`scripts/c1/disasm.py`): cada `_x<k>` declarado é conferido no
`objdump` do ELF final; rótulo de teste não declarado também recusa o ELF.
Pegou na implementação, entre outros, o montador trocando `ldr r1, =0x5A5A5A5A`
por `mov.w` (T-LS-05 deixaria de testar uma carga literal).

## 6. Método (resumo; detalhes no material-base)

- **Vetores:** cada ramo do pseudocódigo e as bordas onde as flags mudam —
  conjunto V32 (13 valores), SH (deslocamentos por registrador), COND, uma
  constante modificada de cada forma; 16 e 32 bits testados separadamente.
- **Classes:** A arquitetural, B implementação documentada, C sem documentação
  (a placa é o oráculo), X excluído (`UNPREDICTABLE`, depende da bancada).
- **Níveis:** N1 (núcleo do instrumento), N2 (bordas), N3 (diagnóstico).
- **Campos comparados:** só os definidos e válidos (MMFAR/BFAR só com o bit de
  validade; xPSR empilhado sob máscara; APSR do tratador é UNKNOWN). Valores
  brutos sempre preservados.
- **Vereditos:** IGUAL · IGUAL COM CONFIGURAÇÃO (só o perfil `renode-doc`
  iguala) · DIVERGE (inclui "simulação abortada") · NÃO DETERMINÍSTICO ·
  EVIDÊNCIA INVÁLIDA; e, em paralelo, a placa diante da especificação: conforme
  · PLACA ≠ ESPECIFICAÇÃO · CONFLITO DOCUMENTAL (a placa decide; o relatório diz
  qual leitura venceu).
- **Microbenchmark diferencial:** Δ(n) = O + n·c medido com n = 8, 16, 24;
  c = (Δ(3K) − Δ(K))/2K como fração exata; linearidade
  Δ(3K) − Δ(2K) = Δ(2K) − Δ(K) exata ou c não é publicado; O fora do veredito.
  Fria (1ª chamada) e quentes registradas à parte. Contadores de perfil do DWT
  só como diagnóstico.
- **Repetições** (Kalibera & Jones): piloto com 30 execuções × 30 iterações nos
  casos N1; estimadores S²/T² por nível e regra pré-registrada (regra 1: tudo
  idêntico → 1 iteração quente e 5 execuções na campanha).

## 7. Renode: o sistema sob teste e os dois perfis

`renode/c1.resc` (8 MIPS, quantum global de 125 ns = uma instrução por
quantum; processo novo por run) com:

| Perfil | Plataforma | O que é |
|---|---|---|
| `renode` | `renode/stm32f103_hsi8.repl` | a plataforma do projeto, a mesma de C2–C4 |
| `renode-doc` | `renode/c1_doc.repl` | + só o que a documentação determina: alias de boot da flash em `0x0` (RM0008 §3.4), VTOR = 0 no reset (TRM Tab. 8-15), regiões de bit-band (TRM §4.2), `FilterCcrDiv0Write = false` (CCR.DIV_0_TRP é gravável, PM0056 §4.4.7) |

Nenhuma correção é feita "para passar" num caso. Quando o Renode aborta a
máquina (ex.: "Trying to execute code outside RAM or ROM") ou fica preso em
`0x0`, o coletor registra isso como observação (`simulator_abort`), com a linha
do log, e não como falha do instrumento.

## 8. Campanha

`scripts/c1.sh campaign` executa: pré-verificação → build do zero (zero
warnings) → gate → **plano congelado** (`plan.json`: SHA-256 dos ELFs, hashes
dos catálogos, lotes, repetições, perfis e hash das plataformas, exemplar,
ferramentas, revisão) → placa (exemplar conferido; gravação verificada) →
Renode nos dois perfis (paralelo, `--jobs`) → traço por stepi → análise.
O ELF executado é copiado para `build/<preset>.elf` da campanha; a análise só
resolve símbolos e disassembly num ELF com o SHA-256 do plano e recusa se o
catálogo das fontes não tiver o hash da campanha.

| Opção | Efeito |
|---|---|
| `--mode pilot` | lotes N1, 30 execuções, 30 iterações quentes no `c1-cycle` |
| `--mode final --pilot-from P` | todos os lotes; repetições pela regra aplicada ao piloto P |
| `--env` | subconjunto de `hw renode renode-doc` |
| `--no-trace` | pula o traço por stepi |
| `--resume` | retoma só com o MESMO plano |

Saída: `0` completa (divergências são resultado, não erro); `3` evidência
incompleta; `1` erro de pré-condição, build, gate ou plano.

```
data/c1/<campanha>/
  plan.json  campaign.log  build/<preset>.elf  build/<preset>.log
  hw/sessions/run-NNN/                 OpenOCD, identificação do exemplar
  <ambiente>/<preset>/bNN/run-NNN/     snapshot.bin, run.json, gdb.log, renode.log
  trace/<ambiente>/<preset>/bNN/       trace.json (PCs por chamada), stepi.log
  analysis/   report.md  results.json  kalibera.json  *.csv  fig_*.png
```

Tentativas nunca são apagadas; snapshots e `run.json` ficam somente-leitura.

## 9. Resultados

RESULTADOS_PLACEHOLDER

## 10. Desvios em relação ao material-base

| Ponto | O que mudou | Por quê |
|---|---|---|
| Separadora de T-LS-07, T-LS-08, T-LSM-05b | `adds r4, r4, #1` | `r7` guarda t0 no esqueleto do bloco |
| T-LSM-01/02 com N ≥ 5 | listas `{r1-r4, r8…}` | r5–r7 são registradores do instrumento; o custo depende só de N |
| T-DWT-06 | roda com PRIMASK = 0 | com PRIMASK = 1 o SVC escalaria para HardFault (nenhuma fonte de interrupção está habilitada) |
| `IT AL` (FC-02) | palavra crua (`.inst.n`) | o montador recusa IT AL, legal no ARMv7-M sem "senão" (§A7.7.38) |
| FEX-02 | `CLREX` antes do `STREX` | garante o monitor em Open Access sem depender do vetor anterior |
| T-DWT-05 | reportado, não invalida a régua | na placa Δ(0) = 1 ≠ O = 2 (carga de t1 sobreposta à de t0, TRM §18.3); c é diferencial e a linearidade é verificada caso a caso |
| Perfis do Renode | `renode` e `renode-doc` na mesma campanha | equivale às "duas campanhas registradas" do material-base, com o mesmo ELF |
| T-AL/T-BB | reaproveitam os blocos de T-LS com a base deslocada | mesma unidade, só os operandos mudam |

## 11. Estrutura

```
src/c1/common/   startup.S c1.ld c1.h c1.c fault.S call.S
src/c1/func/     main.c func.c svc.S moldes.inc fa.S … fen.S
src/c1/layout/   main.c layout.S
src/c1/cycle/    main.c blocks.inc dwt.S alu.S ls.S br.S fe.S
scripts/c1/      arm.py catalog.py vectors.py func/ cycle/ layout.py gen.py
                 abi.py targets.py disasm.py evaluate.py timing.py trace.py
                 campaign.py analysis.py report.py tests/
scripts/c1.sh    CLI com o ambiente do projeto
renode/          c1.resc c1_doc.repl stm32f103_hsi8.repl
vendor/          ST/CMSIS congelados (SHA-256 em vendor/README.md)
```

## 12. Limites

O C1 não é uma suíte exaustiva da ISA nem uma auditoria do código do Renode;
conclusões valem para o **exemplar, as versões, a configuração e as operações
examinados**. Exclusões (comportamento `UNPREDICTABLE`, lockup, WFI/WFE, MPU,
FPU, DSP — só a ausência é testada —, componentes de depuração, mudança de
relógio) e ameaças à validade estão no material-base (cap. Limites).
