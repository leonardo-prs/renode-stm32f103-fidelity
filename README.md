# Renode × STM32F103 — workspace C2: interrupções (TCC EA019, UNICAMP)

Código e simulação do **Cenário C2** do TCC *"Análise quantitativa da
fidelidade funcional e temporal do Renode em relação ao hardware no
STM32F103"*: pendência, prioridade, preempção, máscaras, entrada e saída de
exceção, encadeamento, chegada tardia, coalescência, `WFI` e o efeito do
quantum. A especificação é a fundamentação (`tcc/documentacao/fundamentacao/`,
cap. `04-c2.typ` e `03-quadro-comum.typ`); as decisões de implementação e os
resultados ficam em `tcc/documentacao/desenvolvimento/c2.typ`. Este README
documenta o código e como reproduzi-lo.

A Parte II, mais abaixo, é a documentação do **C1 herdado** da base deste
workspace (código `c1-*`); o C1 será redesenhado no workspace `cenario1`.

## C2.1 Início rápido

```
nix develop                                   # ou direnv
scripts/c2.sh check                           # build do zero do c2-od + gate estático
scripts/c2.sh run --case C2-09 --name piloto-01
# relatório: data/c2/C2-09/piloto-01/analysis/report.md
scripts/c2.sh analyze --case C2-09 --name piloto-01      # refaz só a análise
PYTHONPATH=scripts python3 -m unittest discover -s scripts/c2/tests -t scripts

scripts/q02.sh check                          # Q-02: build do zero do q02 + gate
scripts/q02.sh run --name piloto-01           # relatório: data/q02/piloto-01/analysis/report.md
PYTHONPATH=scripts python3 -m unittest discover -s scripts/q02/tests -t scripts
```

Saída do `run`/`analyze`: 0 = veredito emitido (IGUAL, DIVERGE ou NÃO
DETERMINÍSTICO; no Q-02, IGUAL, REPROVADO ou NÃO DETERMINÍSTICO), 3 =
EVIDÊNCIA INVÁLIDA, 1 = erro de pré-condição.

## C2.2 Estado

| Caso | Oráculo | Estado | Última campanha |
|---|---|---|---|
| `Q-01` (tempo virtual nos ganchos de endereço) | família Q | IGUAL | `data/q01/piloto-02` (`scripts/q01.sh`) |
| `Q-02` (ganchos de escrita e de exceção, monitor) | família Q | IGUAL, 25/25 critérios | `data/q02/piloto-01` (`scripts/q02.sh`) |
| `C2-09` (desabilitada, pendente, habilitada) | #oD | IGUAL, 30/30 pontos | `data/c2/C2-09/piloto-01` |
| demais `C2-*` | — | não implementados | — |

## C2.3 Firmware `c2-od` (casos #oD, só Renode)

Um único ELF para todos os casos #oD: o caso e os pontos são gravados pelo
monitor do Renode num bloco de parâmetros (`c2_param`, seção `.noinit`) com a
simulação parada, antes da partida. Uma campanha usa assim um só SHA-256.

- `src/c2/common/` — startup **em C** (tabela de vetores, `Reset_Handler`),
  `.ld`, `main` comum (grava VTOR, `PRIGROUP` = 0, `BASEPRI` = 0, `FAULTMASK`
  = `PRIMASK` = 0 explicitamente), tratador único das linhas livres
  (`c2_irq_handler`, conta atendimentos por linha), `c2_point(id)` (ponto
  marcado; o gancho lê o id em R0) e `c2_done`.
- `src/c2/od/` — despachante (`cases.c`) e um arquivo por caso (`c2_09.c`).
- `scripts/c2/catalog.py` — fonte única: ABI host ↔ firmware, linhas livres,
  pontos de cada caso e o oráculo documental. Gera
  `build/c2-od/gen/c2_catalog.h` no configure/build.
- `scripts/c2/gate.py` — gate estático do ELF: vetores, VTOR explícito,
  `c2_param` em `.noinit`, tamanhos das estruturas = catálogo, `c2_point`
  vazia e chamada, sem `LDREX/STREX/CLREX/BKPT`, sem literal de bit-band ou
  da USART1.

**Linhas livres** (estímulo por software, `STIR` ou `ISPR`): IRQ 0–5, 18–22,
35, 36, 41, 42 — linhas da família medium-density a que a plataforma
`renode/stm32f103_hsi8.repl` não liga nenhuma fonte (conferido por teste).

## C2.4 Observação no Renode

`scripts/c2/collect.py` gera um `.resc` por execução (perfil R1: 8 MIPS,
quantum 125 ns) e roda o Renode com `--port -1`. Três variantes: `bare` (só o
gancho de fim, que lê a memória do firmware), `hooks` (observador externo) e
`full` (observador + traço de execução). O observador registra em
`events.txt`: pontos marcados com o estado do NVIC, primeira instrução de cada
tratador (com o IPSR), início e fim de interrupção, escritas de palavra nos
registradores do NVIC/SCB e `c2_fault`. Formato das linhas no docstring de
`collect.py`.

A análise (`scripts/c2/analysis.py`) primeiro valida o observador — pontos na
sequência esperada, cada início de interrupção seguido do tratador na mesma
instrução, cada fim fechando o tratador aberto, tick = instrução nos ganchos
de endereço e, na variante `full`, o PC de cada evento igual ao do traço na
posição dada pelo contador de instruções — e depois o determinismo e a não
intrusão (o que o firmware vê é igual nas três variantes). Só então compara
com o oráculo.

Comportamento dos ganchos no Renode 1.17.0 (caracterizado no piloto do
C2-09 e verificado no Q-02, abaixo): o gancho de início de interrupção
entrega um índice interno (5), não o número da exceção — o número vem do
IPSR lido na primeira instrução do tratador; o tempo virtual nos ganchos de
início e de fim fica um tick atrás das instruções contadas; o gancho de
escrita dispara com o PC da própria instrução de escrita e tick = instrução.

## C2.4a Q-02 — instrumentos genéricos do Renode (família Q)

Verificação, isolada de qualquer periférico, dos instrumentos que os casos
#oD usam (`03-quadro-comum.typ`, §Verificação dos instrumentos do Renode).
O firmware (`src/q02/q02.c`, preset `q02`) só usa núcleo, SRAM e SCS (o
gate recusa literais de periférico) e não é julgado: produz eventos
conhecidos e registra o que viu. Segmentos: escritas de palavra numa palavra
vigiada (e numa vizinha não vigiada); PendSV e SysTick pedidos pelo ICSR —
simples, encadeados, aninhados e mascarados por `PRIMASK`; um gancho de
endereço que grava na SRAM; o monitor lendo e gravando a SRAM em duas pausas
(`emulation RunFor` + comando `python` do monitor).

A análise (`scripts/q02/analysis.py`) confere cada instrumento contra o
traço, o registro do firmware e a especificação (`scripts/q02/spec.py`, que
também gera `q02_spec.h`) em 25 critérios agrupados por instrumento
(escrita, exceção, monitor, não intrusão). Veredito: IGUAL, REPROVADO (o
instrumento não serve aos casos que dependem dele), NÃO DETERMINÍSTICO ou
EVIDÊNCIA INVÁLIDA. Os testes de sensibilidade (`scripts/q02/tests/`)
alteram uma execução real (fixture do `piloto-01`) um aspecto por vez.

## C2.5 Estrutura

```
src/c2/common/   startup.c c2.c c2.h c2.ld
src/c2/od/       cases.c c2_09.c
src/q02/         q02.c q02.ld
scripts/obs/     elf.py renode.py — comuns à observação externa (Q-02 e C2)
scripts/c2/      catalog.py gen.py gate.py collect.py analysis.py
                 report.py campaign.py __main__.py tests/
scripts/q02/     spec.py gen.py gate.py collect.py analysis.py
                 report.py campaign.py __main__.py tests/ (com fixture)
scripts/c2.sh scripts/q02.sh   CLIs com o ambiente do projeto
data/c2/<caso>/<campanha>/   plan.json, <variante>-<rep>/ (brutos), analysis/
data/q02/<campanha>/         idem
```

O legado do plano anterior (C2 = timers, C3 = NVIC, C4 = USART1) foi removido;
está no histórico do jj.

---

# Parte II — Cenário C1 herdado: núcleo e memória

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

> **Workspace.** Este workspace (jj `cenario1`) reimplementa o C1.

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
| `c1-func` | instruções, memória e exceções síncronas: grupos FA, FL, FS, FM, FD, FQ, FB, FC, FMEM, FAL, FBB, FEX, FSY, FEN — 547 formas, 31 526 vetores | 23 (por nível: N1 primeiro; um terminal, dois isolados) |
| `c1-layout` | identidade, estado de reset e precondição de relógio (FID-01..08), layout de memória (LAY-01..10) | 2 (normal; reset por software) |
| `c1-cycle` | validação do `DWT_CYCCNT` (T-DWT) e custo por classe de instrução (T-ALU … T-COMP) e acesso a periféricos (T-IO) — 244 variantes | 11 |

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
ou estado incoerente. Na placa, todo run também passa pelo **gate de relógio**
(`abi.clock_checks`, FID-08): HSI sem PLL, AHB/APB sem divisão, `FLASH_ACR`
com 0 estados de espera e pré-busca ligada; fora disso as contagens do TRM
não valem e o run é inválido. No Renode o gate não se aplica: a plataforma
não declara a interface da flash (`FLASH_ACR` lê 0), o que é achado de
FID-08.

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

Campanha definitiva **`final-02`** (2026-10-20, modo final, revisão
`rsyuoppq`, três ambientes, traço por stepi). Repetições pela regra 1 de
Kalibera & Jones aplicada ao piloto `piloto-01`: as 118 séries do piloto
(30 execuções × 30 iterações, nos três ambientes) foram idênticas
(T1² = T2² = 0); daí 1 iteração quente + a fria e 5 execuções por lote.
Instrumento: 0 runs inválidos; abortos do Renode (FEN-07, e LAY-04/LAY-10 sem
o alias) contam como observação. Relatório completo:
`data/c1/final-02/analysis/report.md` (e `resumo.md`, CSVs, figuras).

> **Casos acrescentados depois da `final-02`** (ainda sem campanha): FMEM-09
> (palavra num registrador de periférico, `GPIOB_CRH`), FID-08 (relógio e
> flash no reset; também gate da placa) e T-IO-01..06 (custo de acesso ao
> AHB/APB2 e buffer de escrita, com os mesmos blocos das contrapartes na
> SRAM). Os números abaixo são da `final-02` e não os incluem.

### 9.1 Placa × especificação

A placa confere com o oráculo (ARM ARM + TRM r1p1 + PM0056 + RM0008) em todos
os vetores funcionais e de layout. Onde as fontes se contradizem, a placa
decide (CONFLITO DOCUMENTAL):

| Caso | Conflito | A placa confirma |
|---|---|---|
| FEN-05 (INVPC) | TRM × ARM ARM sobre o quadro empilhado | ARM ARM §B1.5.8: sem quadro novo (quadro do Thread) |
| LAY-07 (VTOR) | PM0056 × TRM sobre os bits implementados | TRM r1p1 Tab. 8-15: TBLOFF[29:7] |
| FBB-04 | RM0008 §9.1.1 (PB4 em pull-up) × §9.2.4 (ODR = 0) | ODR[4] = 1 após o reset; comparam-se só IOPBEN e ODR[5] |

No tempo, 202 variantes caem dentro do intervalo do TRM r1p1, 10 resolvem um
intervalo ambíguo e 14 ficam **fora**: UMLAL/SMLAL pequenos (3 contra 4–7),
T-LS-04.cmp (3 contra 2), T-LS-08.b (3 contra 4), STR/STRH desalinhados (5 e
4 contra 2), T-BB-02 (3 contra 2), **T-BR-03 B<c> não tomado = 3/2** e
**T-BR-06 BX = 9/2**. As variantes com a 1ª unidade em meia palavra (`.h`)
dão os mesmos 3/2 e 9/2: o alinhamento não explica os dois casos. T-LS-10.01
(LDR da flash em fluxo) não é linear com K = 8, 16 ou 32; com **K = 24** é
linear, com c = 4/3: uma carga a cada três custa um ciclo a mais. UDIV (operandos
2^a − 1 ÷ 2^b − 1) custa 3 ciclos se a < b (quociente 0) e 5 + ⌊(a − b)/4⌋
se a ≥ b, até 12 (32 bits ÷ 1); por 0, 2 ciclos (`fig_udiv.png`). Um SVC com tratador vazio custa
22 ciclos dentro da janela. T-DWT-05 falha na placa (Δ(0) = 1, O = 2): com a
janela vazia, a carga de t1 se sobrepõe à de t0 (§18.3). c é diferencial e
linear, então a régua vale para c, e O fica como caracterização (§10).

### 9.2 Renode × placa — nível funcional

| Preset | Casos | IGUAL | IGUAL COM CONFIGURAÇÃO | DIVERGE |
|---|---|---|---|---|
| `c1-func` (31 521 vetores) | 91 | 71 | 5 | 15 |
| `c1-layout` | 17 | 6 | 3 | 8 |

Cada divergência tem a causa localizada no código do Renode 1.17.0
(`scripts/c1/renode_notes.py`; explicação, não oráculo):

- **Faltas que o Renode não gera:**
  - FAL-03/FAL-04: acesso desalinhado; `CCR.UNALIGN_TRP` nunca é lido.
  - FC-11/FEN-05: QADD, SEL e SETEND executam sem UNDEFINSTR (a decodificação não consulta a ausência de DSP).
  - FSY-08/FEN-08: PPB lido sem privilégio, sem BusFault.
  - LAY-09: leitura de endereço não mapeado devolve 0, sem BusFault.
  - FEN-07: XN aborta a máquina em vez de gerar MemManage.
- **Falta no lugar errado:** FC-08/FC-10 — BX/BLX/POP para endereço par falta na própria instrução de desvio com T = 1, em vez de na instrução seguinte com T = 0.
- **Estado arquitetural:**
  - FEX-04: o monitor exclusivo não é limpo na entrada/saída de exceção.
  - FSY-02: EPSR e xPSR expõem T e ITSTATE.
  - FSY-03: FAULTMASK liga dentro do HardFault.
  - FSY-04: BASEPRI guarda 8 bits.
  - FEN-04: STKALIGN = 0 é ignorado.
- **Identidade e reset:**
  - FID-01: CPUID r0p1.
  - FID-02: registradores de características leem 0.
  - FID-03: VTOR "adivinhado" (0x08000000).
  - FID-04: LR = 0.
  - FID-05: ICTR, MPU_TYPER e NUMCOMP.
  - FID-06: F_SIZE e UID não declarados.
  - LAY-07: TBLOFF[31:30] gravável.
  - FBB-04: sem RCC do F1.
- **Só configuração (o perfil `renode-doc` iguala):**
  - FD-03/FEN-06: `FilterCcrDiv0Write`.
  - FBB-01..03: periférico BitBanding não declarado.
  - LAY-01/LAY-04/LAY-10: sem o alias de boot em 0x0. Sem ele, um SYSRESETREQ deixa o núcleo preso em 0x0.

### 9.3 Nível de instrução

- `c1-func`: 544 de 559 chamadas com a **mesma sequência de PCs** na placa e
  no Renode. As 15 diferentes são exatamente as faltas que o Renode não
  gera (FD-03, FC-08, FAL-04, FSY-08, FEN-05, FEN-06). As 368 rotinas em
  linha reta conferem com a contagem estática do disassembly nos dois
  ambientes.
- `c1-cycle`: 232 de 232 chamadas com a mesma sequência.
- **H-T1 exata** (Renode: Δ(K) − Δ(0) = instruções executadas na janela,
  medidas pelo traço do próprio Renode): confirmada em 231 variantes,
  refutada em 0. O tick do Renode é a instrução, e a entrada/saída de
  exceção não custa ticks (T-DWT-06 = 2: SVC + BX LR).

### 9.4 Renode × placa — nível de ciclo

232 variantes: **IGUAL 43, DIVERGE 186, EVIDÊNCIA INVÁLIDA 3**. As 3
inválidas são as variantes de T-LS-10.01 com K não múltiplo de 3, que existem
justamente para mostrar a não linearidade. O Renode conta um tick por
instrução (H-T1), então só iguala onde a placa também gasta um ciclo por
instrução: ALU (inclusive CLZ, RBIT, REV, extensões e campos de bits), MUL,
LDR/LDRB/LDRH em fluxo, STR, MRS/MSR/CPSID, DMB/DSB, blocos IT, CBNZ não
tomado, as verificações T-DWT e CRC-32 bit a bit. Diverge em todo o resto:
multiplicações longas, divisão, cargas dependentes, LDM/STM, desvios
tomados, ISB e exceções. Exemplos (placa/Renode): UDIV
12/1, LDM de 8 registradores 9/1, PUSH+POP de 8 18/2, POP {PC} 6/1, SVC
22/2.

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
