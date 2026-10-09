# Resumo do projeto — Renode × STM32F103 (fidelidade)

> Gerado em 2026-10-09. Duas partes: **Parte 1** (leitura de ~5 min, direta)
> e **Parte 2** (didática, com detalhes de funcionamento). Ficam de fora
> pastas temporárias e de anotações (`tmp/`, `.slim/`, `data/exploratory/`,
> builds, locks) e o conteúdo interno de `vendor/`, que é código de terceiros congelado.

---

# PARTE 1 — Resumo rápido

## 1. O projeto em um parágrafo

TCC (EA019/UNICAMP) que mede **até onde o simulador Renode 1.17.0 reproduz
um STM32F103 real** (Blue Pill, Cortex-M3, HSI 8 MHz) em três níveis:
**funcional** (mesmos resultados/flags/ordens), **instrução** (mesma
sequência de PCs) e **ciclo** (mesmos tempos em ticks do DWT CYCCNT). O
**mesmo ELF** roda na placa (via ST-Link/OpenOCD/GDB) e no Renode (GDB
server). O firmware grava resultados e eventos numa estrutura em RAM
(ABI "FID3"), e o host faz o dump dela no fim do run. Oráculos em Python,
escritos a partir dos manuais (RM0008/PM0056/C17), avaliam cada run, e uma
análise classifica cada recurso. Um comando (`scripts/campaign.sh`) faz
tudo: build, gate, placa, Renode, traço de instruções, calibração, análise,
figuras e traces Perfetto.

**Quatro cenários:** C1 núcleo/memória (funcional + tempo de cargas), C2
timers e IRQ periódica, C3 NVIC (prioridade/preempção/máscaras), C4 USART1
em loopback PA9→PA10.

## 2. Pastas

| Pasta | Conteúdo |
|---|---|
| `src/` | Firmwares: um `main` por preset (`c1/`, `c2/`, `c3/`, `c4/`) |
| `lib/`, `inc/` | Código comum do firmware: clock (`board`) e instrumentação (ABI FID3) |
| `vendor/` | CMSIS, LL da ST, startup, linker script e SVD. **Congelado** (SHA-256 conferido) |
| `renode/` | Plataforma `.repl` e script `.resc` únicos para todos os cenários |
| `scripts/` | Entrada da campanha (`campaign.sh`), CLI (`fidelity.py`), pacote Python `fidelity/`, helpers do VS Code |
| `cmake/` | Toolchain arm-none-eabi e modelo do `.clangd` |
| `.vscode/` | Tasks de build/debug (só conveniência) |
| raiz | `CMakeLists.txt`, `CMakePresets.json`, `flake.nix`/`flake.lock` (ambiente Nix), `README.md` (documentação técnica completa) |
| `data/fidelity/<campanha>/` | Saídas das campanhas (não versionado) |

## 3. Arquivos

**Firmware (C/ASM, roda na placa e no Renode):**
- `lib/board.c/.h`: força HSI 8 MHz, AHB/APB /1 e flash com 0 wait states, além de `board_set_apb()` para o C2.
- `inc/fidelity.h` + `lib/fidelity.c`: ABI FID3, com o snapshot global (header, casos, palavras e 4 anéis de eventos, um por contexto escritor), tickets globais por LDREX/STREX, nonce do host, pintura de pilha e HardFault → FAILED.
- `lib/fidelity_measure.S`: bracket em assembly `LDR CYCCNT → BLX fn → LDR CYCCNT` para medir uma função.
- `src/c1/functional.c`: 30 casos (629 verificações) de aritmética 32/64 bits, bits, conversões, SRAM (larguras, ordem de bytes, padrões, desalinhado), flash `.rodata`, cópia, `switch` e recursão.
- `src/c1/timing.c` (+ `table.h`): 9 cargas (`empty`, `alu`, `mul`, `div_small/large`, `sram_copy`, `flash_sum`, `branch`, `crc`) × n = 16/64/256 × 4 repetições, medidas com o bracket.
- `src/c2/timers.c`: 49 casos com TIM2/TIM3/TIM1, cobrindo contagem, perfis APB /1 /2 /4, PSC/ARR preload, UG/URS, UIF×UIE×pending, IRQ periódica, atendimento atrasado e coalescência.
- `src/c3/nvic.c`: 18 casos com EXTI0/EXTI1 pendidas por software, cobrindo arbitragem, preempção, PRIMASK, BASEPRI, tail-chain e re-pend.
- `src/c4/usart.c`: 22 casos com USART1 por polling, cobrindo byte único, stop-and-wait, rajada, baud, formatos, flags, leitura atrasada (ORE), pressão de TX e RE = 0.

**Renode:** `renode/stm32f103_hsi8.repl` (plataforma reduzida, 8 MHz) e
`renode/fidelity.resc` (8 MIPS, quantum de 125 ns, hub UART em loopback, GDB server).

**Scripts:**
- `campaign.sh`: entra no Nix e chama `fidelity.py campaign`.
- `fidelity.py`: CLI com os comandos `campaign`, `analyze`, `run` e `check`.
- `fidelity/targets.py`: executa na placa (OpenOCD) e no Renode com o mesmo protocolo GDB.
- `fidelity/campaign.py`: orquestração, plano congelado, locks, tentativas, retomada e calibração.
- `fidelity/abi.py`: decodifica e valida o snapshot.
- `fidelity/c1.py`…`c4.py`: oráculos por cenário.
- `fidelity/instr.py`: traço por stepi.
- `fidelity/analysis.py`: estatística e classificação.
- `report.py`, `figures.py` e `perfetto.py`: relatório, figuras e traces.
- `model.py` e `firmwares.py`: tipos e catálogo de firmwares.
- `renode_start/stop.sh` e `direnv_exec.sh`: debug no VS Code.

## 4. Saídas e conclusões (até agora)

- **Saídas:** `data/fidelity/<campanha>/` com `plan.json`, runs (snapshot +
  `run.json`) e `analysis/`, que reúne CSVs, `report.md`, figuras PNG e traces
  Perfetto validados.
- **Funcional:** o Renode acerta **todo o C1**, **todo o C3** e a maior parte do C2/C4.
  Ele **diverge** em RCC (não há modelo para o F1, então o timer não segue o APB /4), PSC
  aplicado sem preload, UG com URS = 0 sem setar UIF quando UIE = 0, TC da
  USART, paridade e 9 bits.
- **Instrução:** a sequência de PCs foi **idêntica** em 25/25 combinações do C1-timing.
- **Ciclo:** o Renode conta **1 tick por instrução**, enquanto a placa gasta de 1,17 a
  3,56 ciclos por instrução. O erro relativo mediano das cargas fica entre 19% e 72%, os
  intervalos do NVIC saem cerca de 2× menores e as latências de IRQ divergem. Os períodos de
  timer (ARR) e de quadro da USART ficam próximos (erro ≤ 0,3% e ~5%).
- **Calibração (só C1):** com 6 MIPS, o erro médio cai de 28% para 11% no treino e
  de 49% para 32% na avaliação. Melhora a média, mas não torna o modelo ciclo-preciso.
- **Repetibilidade:** placa e Renode foram 100% determinísticos nos runs observados.
- **Pendência:** todos os dados vêm de uma placa **provavelmente clone**. Falta
  rodar a campanha final numa placa **genuína** (README §11).

---

# PARTE 2 — Explicação didática

## 1. Qual problema o projeto resolve

Simuladores como o Renode permitem desenvolver e testar firmware sem a
placa. A pergunta é **o quanto dá para confiar neles**. "Fiel" pode
significar coisas diferentes:

1. **Funcional:** o programa produz os mesmos valores, flags, ordens de
   eventos e contagens?
2. **Instrução:** o processador simulado executa exatamente a mesma
   sequência de instruções?
3. **Ciclo:** as coisas levam o mesmo tempo, medido em ciclos de clock?

O projeto responde a essas três perguntas para o STM32F103, **recurso por
recurso** (ALU, memória, timers, NVIC, USART) e **condição por condição**
(por exemplo, timer com APB /1 × /4). A resposta vale para o exemplar, as versões e
a configuração testados; não é uma afirmação universal.

### A ideia central: o mesmo binário nos dois lados

O mesmo `firmware.elf` é gravado na placa e carregado no Renode. Os dois
lados são controlados por GDB com o **mesmo protocolo**:

```
reset → para em main → host grava um nonce aleatório na RAM
      → continua → firmware executa todos os casos e registra tudo em RAM
      → firmware chama fid_complete() (breakpoint) → host faz dump da RAM
```

Durante a execução o host não lê nada; ele só espera o breakpoint final.
Isso evita que o depurador interfira na medição. O nonce prova que o dump é
**deste** run, já que a SRAM da placa sobrevive ao reset.

## 2. Estrutura de pastas, explicada

### `src/`: os experimentos (firmwares)
Cada subpasta é um cenário do plano de trabalho. Cada firmware é um
programa C independente com um `main` que executa uma lista de **casos**.
Cada caso abre um registro (`fid_case_begin`), grava entradas e saídas
(`fid_put`) e eventos com timestamp (`fid_log`), e fecha com status OK ou
TIMEOUT.

### `lib/` e `inc/`: a "biblioteca de medição"
É o código compartilhado pelos firmwares. Ela padroniza o clock e define
**onde e como** os resultados ficam na RAM para o host coletar.

### `vendor/`: código de terceiros
Contém os headers CMSIS da ARM, os drivers LL da ST, o arquivo de startup, o linker script
e o SVD (descrição dos registradores, usada pelo debugger). Nunca é editado; os hashes
ficam em `vendor/README.md` e a campanha confere antes de rodar.

### `renode/`: a placa virtual
Descreve ao Renode quais periféricos existem e com que frequência
(`.repl`), e como montar a simulação (`.resc`).

### `scripts/`: a automação e a ciência
É onde mora a maior parte da lógica de experimento. Ali ficam a execução nos
dois ambientes, a validação dos dados, os oráculos, a estatística e os relatórios.

### `cmake/`, `CMakeLists.txt`, `CMakePresets.json`
Cuidam do build cruzado para ARM. Um preset gera um firmware, em
`build/<preset>/firmware.elf`. Todos os firmwares usam a mesma otimização (`-O2 -g3`).

### `flake.nix` / `flake.lock`
Descrevem um ambiente reproduzível com versões travadas: GCC Arm 15.3, CMake,
Ninja, OpenOCD, Renode 1.17.0, Python com numpy/matplotlib e o
`trace_processor_shell` do Perfetto. `nix develop` (ou o direnv) entra nesse ambiente.

### `.vscode/`
Tasks como "Build: c2" e configurações de debug "Renode: c2" / "Placa: c2"
via cortex-debug. É só conveniência; o fluxo oficial é pelo terminal.

## 3. Arquivos, explicados

### 3.1 Firmware: infraestrutura comum

**`lib/board.c` / `board.h`.** `board_init()` reescreve explicitamente o
estado de reset: HSI ligado, SYSCLK = HCLK = 8 MHz, prescalers AHB/APB1/APB2
em /1 e flash com latência 0. Mesmo que já seja o padrão, escrever deixa a
premissa documentada e independente do que um bootloader ou debugger tenha
deixado. `board_set_apb()` muda os prescalers APB (usada no C2 para testar
a árvore de clock) e devolve o `RCC->CFGR` lido de volta.

**`inc/fidelity.h`: o contrato ABI v3 "FID3".** Define o objeto global
`fid_snapshot`, que o host copia byte a byte. Ele tem quatro partes:

- **header (40 palavras):** magic `"FID3"`, versão, id do firmware,
  estado (RUNNING/DONE/FAILED), nonce, CYCCNT inicial e final, custo medido
  do observador e do logger, e identidade do chip (CPUID, IDCODE, F_SIZE,
  UID). Guarda também registradores de contexto (RCC, FLASH_ACR, AIRCR), pilha livre e,
  em caso de falha, o PC e o CFSR.
- **cases:** um descritor por caso (`id`, `status` e a posição dos dados).
- **words:** os dados brutos de cada caso, em sequência.
- **4 anéis de eventos**, um por **contexto escritor** (MAIN, IRQ1, IRQ2,
  IRQ3). Cada evento traz ticks, ticket, tipo, caso e argumento.

**`lib/fidelity.c`: a implementação.** Os pontos mais importantes são:

- **Um escritor por anel.** Como cada handler escreve só no seu anel, o
  logger não precisa desabilitar interrupções, o que alteraria justamente o
  que se quer medir.
- **Ordem global por ticket.** Para saber a ordem entre anéis, cada evento
  pega um número de um contador global usando `LDREX/STREX`. O CYCCNT é
  lido **dentro** desse laço. Se uma interrupção acontecer no meio, o
  `STREX` falha e o laço repete, então ticket e tempo ficam sempre coerentes.
- **Detecção de perda.** O `head` de cada anel conta tudo que foi escrito.
  Se passar da capacidade, o host sabe quantos eventos foram sobrescritos e
  invalida as métricas que dependem deles.
- **CYCCNT pré-carregado em `0xFFF00000`.** Isso força o teste da lógica de
  estouro de 32 bits do host logo no início.
- **Pilha pintada** com `0xA5A5A5A5` em `fid_init`. No fim, o firmware mede quanto
  nunca foi usado.
- **HardFault** não trava: publica FAILED com PC/CFSR e para no breakpoint.

**`lib/fidelity_measure.S`: o "cronômetro".** Para medir uma função
C, o GCC poderia reordenar código em volta das leituras do CYCCNT. Em
assembly, a sequência é fixa: `LDR CYCCNT → BLX fn → LDR CYCCNT`. O código empilha 6
registradores para manter o SP alinhado a 8 bytes, como exige a AAPCS.

### 3.2 Firmware: os cenários

**`src/c1/functional.c`: o núcleo calcula certo?** São 30 casos e 629 verificações.
Cada operação fica em uma função `noipa`, para que o compilador não possa calcular o
resultado em tempo de compilação, e cada caso grava **entradas e saídas**.
O conteúdo cobre:
- aritmética `uint32`/`int32`/`uint64`, com wrap, divisão truncada e sem
  comportamento indefinido;
- comparações, lógica, shifts e rotações, campos de bits, CLZ/CTZ/popcount;
- promoções de 8/16 bits, extensão de sinal e truncamento. Os casos que dependem da
  implementação seguem a convenção do GCC e vêm marcados;
- SRAM com acessos de 8/16/32 bits, ordem de bytes (little-endian), vizinhos
  preservados, padrões e "bit caminhante";
- **acesso desalinhado** de 16/32 bits (o Cortex-M3 permite; o gate do ELF
  confere que o GCC realmente gerou LDR/STR/LDRH/STRH);
- leitura da flash (`.rodata`, tabela de `table.h`) via ponteiro `volatile`;
- cópia/preenchimento desalinhados, ordenação, MDC, `switch` e recursão.

**`src/c1/timing.c` + `table.h`: quanto tempo leva?** Mede 9 cargas pequenas:
- `empty` mede só o custo do cronômetro;
- `alu` é um xorshift;
- `mul` usa MLA;
- `div_small` e `div_large` usam UDIV com as **mesmas instruções e operandos
  diferentes**. No hardware a divisão tem latência variável;
- `sram_copy` copia um bloco na SRAM;
- `flash_sum` soma valores lidos da flash;
- `branch` tem desvios que dependem dos dados;
- `crc` é um CRC-32 calculado bit a bit.

Cada carga roda com n = 16, 64 e 256 (para separar custo fixo do custo por
iteração), em 4 repetições com entradas idênticas. A repetição 0 é a primeira
após o reset e revela efeitos de "primeira execução" da flash. O resultado de
cada execução também é conferido, para garantir que o tempo medido é de uma
execução correta. `table.h` define 64 palavras constantes em flash
(`T[i] = i·0x9E3779B9 ^ 0xA5A5A5A5`).

**`src/c2/timers.c`: timers e interrupção periódica.** São 49 casos, sempre com um timer
por vez (TIM2 e TIM3 no APB1, TIM1 no APB2). O cenário testa:
- contagem parada × habilitada e a **taxa de contagem por perfil APB** (/1, /2, /4).
  A regra do manual diz que, se o prescaler APB ≠ 1, o timer recebe 2×PCLK;
- **preload** de PSC (sempre bufferizado) e de ARR (só com ARPE). O firmware
  troca o valor no meio da contagem e mede quando o novo valor passa a valer;
- **UG/URS**, isto é, se o update forçado por software seta UIF;
- UIF × UIE × pending no NVIC;
- IRQ periódica com MAIN ocioso ou ocupado, IRQ atendida com atraso e
  **coalescência** (vários updates enquanto a IRQ está bloqueada viram um só).

A ISR lê o CNT como primeira instrução, o que dá a "fase" desde o update. Há
ainda um caso de contexto, `c2/rcc`, que registra o que o RCC realmente devolve.

**`src/c3/nvic.c`: quem atende primeiro?** São 18 casos com duas IRQs ociosas
(EXTI0 = A e EXTI1 = B) **pendidas por software** (`NVIC->ISPR`). Assim, nenhum periférico
interfere. Usa PRIGROUP = 5 (2 bits de grupo e 2 de subprioridade). Cada handler executa
uma ação definida por MAIN antes do estímulo (nada, pender o outro ou
pender a si mesmo). O cenário testa:
- **arbitragem** entre pendentes (grupo > sub > número);
- **preempção**, que só acontece por grupo;
- **PRIMASK**, **BASEPRI** (prioridade igual ao limiar é mascarada) e **tail-chaining**;
- **re-pend**: um handler que se pende de novo roda outra vez antes de uma IRQ de
  prioridade menor.

O host compara a sequência completa de entradas e saídas, inclusive o IPSR.

**`src/c4/usart.c`: comunicação serial.** São 22 casos com USART1 por polling, usando um
fio físico PA9 (TX) → PA10 (RX). O cenário cobre:
- byte único, stop-and-wait e rajada de 64 bytes em full duplex;
- três valores de BRR (baud), em que o host calcula o baud realizado;
- formatos 7E1, 7O1, 8E1, 9 bits e 2 stop bits, além das flags TXE/TC/RXNE/IDLE;
- **leitura atrasada**: o produtor envia k bytes antes do consumidor ler. Pelo
  manual, isso deve gerar ORE e perder bytes;
- **pressão de TX** (escrever mais rápido do que a linha transmite);
- RE = 0, com o receptor desligado.

O payload tem versão própria (`0x43340002`); layouts antigos são recusados.
É o **único** firmware que pode tocar USART1/PA9/PA10, e o gate verifica isso no ELF.
**Limitação:** com loopback, TX e RX usam o mesmo formato, então não dá para
testar a **detecção** de erro de paridade/enquadramento.

### 3.3 Renode: como a simulação é montada e executada

**`renode/stm32f103_hsi8.repl`** parte da plataforma `stm32f103.repl` do
Renode 1.17.0. Ela foi reduzida aos periféricos do F103 medium-density, com memórias do
tamanho real e `frequency: 8000000` nos periféricos.

**`renode/fidelity.resc`** é **um único script para todos os cenários**; só
a variável `$elf` muda. Ele:
1. cria a máquina e carrega o `.repl`;
2. fixa o **quantum global em 125 ns** (= 1 instrução a 8 MIPS). Com 1 µs, o
   CYCCNT variava ±4 ticks entre repetições idênticas;
3. define `PerformanceInMips 8`, a hipótese "1 instrução = 1 ciclo a 8 MHz";
4. cria um **UARTHub em loopback** ligado à USART1, equivalente ao fio. O
   `AutoUpdateDelay` fica desligado para não contar o tempo do quadro duas vezes;
5. carrega o ELF e abre o **GDB server**.

**Como o Renode é executado** (`targets.py`):
`renode --disable-xwt --plain --port -1 -e '$elf=...; $gdb_port=N; i @renode/fidelity.resc'`.
Há duas armadilhas conhecidas. Com `--port N`, o `-e` só executa quando um cliente
telnet conecta; por isso usa-se `--port -1`. E, se um comando falhar, o Renode **não
termina**, por isso todo passo tem timeout. Cada run usa um **processo novo**
(estado limpo), na porta ≥ 3336. O GDB conecta e roda o mesmo protocolo
da placa.

**Por que o Renode diverge** (lido no fonte 1.17.0):
- não existe modelo de RCC do F1. As escritas são ignoradas, `RCC_CFGR` lê 0 e
  a frequência dos timers e da USART é a fixa do `.repl`;
- no `STM32_Timer`, o PSC vale imediatamente (sem preload), e o UG só seta
  UIF se UIE = 1;
- no `STM32_UART`, TXE é sempre 1, TC é setado na escrita, ORE nunca ocorre, a FIFO de RX
  é ilimitada e não há paridade nem 9 bits;
- no DWT, CYCCNT = tempo virtual × frequência. Não existe pipeline: cada instrução
  custa 1 tick.

### 3.4 Scripts: automação e análise

**`scripts/campaign.sh`** é o ponto de entrada. Se as ferramentas não estiverem
no PATH, reexecuta dentro de `nix develop` e chama `fidelity.py campaign`.
O código de saída é `0` (campanha completa; divergências são resultado, não erro),
`3` (infraestrutura incompleta) ou `1` (erro de pré-condição, build ou plano).

**`scripts/fidelity.py`** é a CLI, com quatro subcomandos:
- `campaign` executa a campanha completa;
- `analyze --name N` refaz só a análise;
- `run --env hw|renode --firmware F` faz um run avulso de diagnóstico;
- `check` faz a pré-verificação, o build e o gate.

**`fidelity/campaign.py`** orquestra a campanha em 8 etapas:
1. **pré-verificação** (ferramentas, porta :3333 livre, disco) e **locks**
   da campanha e da bancada;
2. **build do zero** dos 5 firmwares (zero warnings), verificação dos hashes do `vendor/` e
   **gate do ELF**, que confere símbolos, RAM ≤ 20 KiB, literais da USART1 só no C4, o
   `fid_measure` e as instruções dos acessos desalinhados;
3. **plano congelado** `plan.json`, com hashes dos ELFs e fontes, versões, config do
   Renode e casos esperados. `--resume` só aceita o mesmo plano e o mesmo
   exemplar (CPUID/IDCODE/F_SIZE/UID);
4. **placa**: N runs por firmware;
5. **Renode nominal**: N runs por firmware, em paralelo (`--jobs`);
6. **traço por stepi** do C1-timing;
7. **calibração** (opcional), com a regra pré-registrada `CALIBRATION_RULE`:
   - treino com ALU/SRAM/flash/branch e avaliação com MUL/DIV/CRC;
   - escolhe o MIPS inteiro de 1 a 16 que minimiza o erro médio no treino;
   - confirma o valor com runs reais;
8. **análise**.

Nenhuma tentativa é apagada. Uma falha (timeout, snapshot inválido) fica guardada com o
motivo, e uma nova tentativa é feita, até `N + max(3, N/5)`.

**`fidelity/targets.py`** cuida da execução nos dois ambientes.
- `Bench`: sobe o próprio OpenOCD (:3333) com o ST-Link, identifica o chip,
  grava e verifica o ELF e executa o protocolo GDB.
- `RenodeSession` / `run_renode`: sobe o Renode como descrito acima e executa o
  **mesmo** script GDB.

Nos dois casos, só encerra os processos que ele mesmo criou, e uma porta ocupada é erro
(nunca mata processos alheios).

**`fidelity/abi.py`** é o espelho Python de `fidelity.h`. `decode()` **rejeita**
qualquer snapshot malformado: magic, versão ou tamanho errados, contagens fora da
capacidade, ou tickets duplicados, decrescentes ou faltando. `timeline()`
reconstrói o tempo contínuo somando diferenças módulo 2^32 na ordem dos
tickets, o que trata o estouro do CYCCNT. `run_checks()` confere o nonce, o estado
DONE e o firmware.

**`fidelity/c1.py` … `c4.py`: os oráculos.** Os valores esperados são
calculados **a partir do manual, nunca dos dados da placa**:
- **c1** recalcula cada operação com aritmética de largura explícita e
  confere se as entradas gravadas são as do plano. No timing, confere o resultado e
  extrai os ticks.
- **c2** usa a árvore de clock do RM0008 para prever períodos. No preload, compara a
  medida com duas hipóteses (valor antigo × novo) e marca "ambíguo" se a medida não
  estiver claramente mais perto de uma delas.
- **c3** tem as sequências esperadas escritas à mão (tokens `A.enter[0]`, …).
  A sequência observada precisa ser idêntica, com todas as ocorrências.
- **c4** calcula a duração do quadro a partir de BRR/CR1/CR2, a paridade esperada no MSB e
  o comportamento de ORE do RM0008.

Cada oráculo produz `Check` (funcional, comparação exata), `Metric` (temporal,
em ticks) e `problems` (falha do instrumento). Esses tipos estão em `model.py`.

**`fidelity/firmwares.py`** é o catálogo: preset → id na ABI, oráculo e timeout.

**`fidelity/instr.py`** gera o **traço de instruções**. Um script GDB faz
`stepi` instrução a instrução dentro do bracket do C1-timing (na rep 0), na placa
e no Renode. Comparar as sequências de PCs mostra se o caminho dinâmico é o
mesmo; dividir os ticks da placa pelas instruções dá o **CPI real**.

**`fidelity/analysis.py`** carrega só os runs válidos do ELF congelado e gera
`accounting.csv`, `checks.csv`, `metrics.csv` e `stats.csv` (mediana, média,
desvio, extremos por ambiente). Em seguida **classifica** cada caso:
1. concordância funcional e mesmas medianas;
2. concordância funcional, mas tempo diferente;
3. valores diferentes ou não conformidade com o manual;
4. evidência insuficiente.

Por fim, monta o **mapa por recurso** (funcional × instrução × ciclo × conformidade
da placa e do Renode com a especificação).

**`report.py`, `figures.py` e `perfetto.py`** cuidam das saídas.
- `report.py` gera `analysis/report.md`.
- `figures.py` gera PNGs (barras e ECDF), com placa em azul, Renode em laranja e
  calibrado em verde-água.
- `perfetto.py` exporta cada run como Chrome Trace JSON, com uma trilha por contexto
  (MAIN e cada ISR) e flows de pedido → atendimento. Também gera um comparativo
  placa × Renode do run mediano e **valida a importação** com o
  `trace_processor_shell` oficial.

**Helpers de debug:**
- `renode_start.sh <fw>` faz o build e sobe o Renode com o mesmo `.resc`, com GDB em :3334;
- `renode_stop.sh` encerra só aquele PID;
- `direnv_exec.sh` garante o `nix` no PATH para as tasks do VS Code.

## 4. Saídas e conclusões, explicadas

### O que uma campanha produz
```
data/fidelity/<campanha>/
  plan.json, campaign.log, calibration.json
  hw/<fw>/run-NNN/          snapshot.bin + run.json (+ logs)
  renode-nominal/<fw>/run-NNN/
  instr/{hw,renode}/        sequências de PCs
  analysis/                 CSVs, report.md, figures/, perfetto/
```
Os traces podem ser abertos em <https://ui.perfetto.dev>.

### O que se aprendeu (piloto `pilot-clone3`, código atual, placa provavelmente clone)

**Funcional: o Renode é muito bom.**
- C1 inteiro está correto: aritmética, memória, flash e desalinhado.
- C3 inteiro está correto: ordem de atendimento, preempção, máscaras, encadeamento e
  re-pend são idênticos à placa e ao manual.
- C2 está correto em contagem, ARR, UIF/pending, atrasos e coalescência.
- C4 está correto em integridade, rajada, baud e RE.

**Onde ele erra funcionalmente,** sempre por limitação do modelo:
- RCC do F1 não modelado, então no perfil APB /4 o timer conta no dobro da
  velocidade correta;
- PSC sem preload;
- UG sem UIF quando UIE = 0;
- TC da USART incorreto;
- paridade e 9 bits não implementados.

No overrun da USART, placa e Renode **coincidem**, mas **ambos** divergem do manual:
a placa clone guarda ≥ 8 bytes sem ORE. É coincidência do exemplar, não fidelidade.

**Instrução: idêntico.** As 25/25 combinações do C1-timing executam exatamente a
mesma sequência de PCs. O Renode gasta sempre ticks = instruções + 1.

**Ciclo: aqui está o limite do Renode.** Ele assume 1 ciclo por
instrução; a placa gasta de 1,17 (ALU) a 3,56 (UDIV grande) ciclos por instrução, por causa
de wait states, pipeline e latência variável da divisão. Por isso:
- as cargas do C1 erram de 19% a 72% (mediana por carga);
- as divisões com operandos diferentes custam o mesmo no Renode;
- as latências de IRQ e os intervalos do NVIC saem cerca de 2× menores;
- o produtor da USART fica muito mais rápido, porque TXE é sempre 1.

Já os **períodos gerados por periféricos** (ARR do timer, quadro da USART) ficam
próximos, porque são modelados por tempo e não por instrução.

**Calibração (C1):** baixar para 6 MIPS reduz o erro médio (de 28% para 11% no treino
e de 49% para 32% na avaliação), mas isso só ajusta a média. Não torna o custo por instrução
correto e **nunca** é aplicado a C2–C4.

**Repetibilidade:** em todos os runs, os 2041 observáveis da placa e os 2038 do Renode
foram idênticos. Isso indica que não houve jitter observado, mas não prova que ele não exista.

**Conclusão geral:** o Renode 1.17.0 é **confiável para lógica**: resultados,
ordem de interrupções e protocolos. Ele **não é confiável para tempo de
CPU**: latências, durações de código e corridas que dependem do tempo. Também falha em
detalhes de periféricos não modelados (RCC, preload de PSC, TC, paridade).

### Pendência
A placa usada é muito provavelmente um **clone** (UID zerado, F_SIZE de 128 KiB,
USART sem ORE, ~110 ciclos extras na primeira execução de cada trecho de
flash). A campanha final precisa rodar numa placa **genuína**:
```bash
scripts/campaign.sh --name final-genuino-01 --board "<etiqueta>" --calibration
```
O `analysis/report.md` dessa campanha será a entrada para a monografia.
