# Renode × STM32F103 — fidelidade funcional e temporal (TCC EA019, UNICAMP)

Código, plataforma de simulação e campanha automática do TCC *"Análise
quantitativa da fidelidade funcional e temporal do Renode em relação ao
hardware no STM32F103"* (plano de trabalho de 31/08/2026, orientadora Wu Shin
Ting). A monografia **não** está neste repositório.

O objetivo é **mapear, para este hardware, até onde o Renode é fiel** em três
níveis, por recurso e por condição:

| Nível | Pergunta | Evidência neste repositório |
|---|---|---|
| **Funcional** | O mesmo ELF produz os mesmos resultados, flags, ordens e contagens? | oráculos da especificação (RM0008, PM0056, C17) + comparação placa × Renode em todos os casos C1–C4 |
| **Instrução** | O simulador executa a mesma sequência dinâmica de instruções? | traço por `stepi` (placa e Renode) das cargas do C1-timing: sequência de PCs e contagem |
| **Ciclo** | Os tempos coincidem com os ciclos da placa? | DWT CYCCNT no mesmo código; diferenças por carga e por condição, sem tolerância instrumental presumida |

Tudo roda por terminal (Nix + CMake + Python). O VS Code em `.vscode/` é só
conveniência.

---

## 1. Escopo e recorte

Os quatro cenários seguem a ordem do plano de trabalho:

| Cenário | Preset (`build/<preset>/firmware.elf`) | Fonte | Fenômeno | Não investiga |
|---|---|---|---|---|
| **C1** núcleo e memória | `c1-functional`, `c1-timing` | `src/c1/` | resultados de operações/memória; duração de cargas C; calibração (complemento) | timers, USART |
| **C2** timers e IRQ periférica | `c2` | `src/c2/timers.c` | TIM2/TIM3 (APB1) e TIM1 (APB2): contagem, árvore de clock APB /1 /2 /4, PSC/ARR/UG/URS, UIF × UIE × pending, IRQ periódica, atendimento atrasado e coalescência | matriz de prioridades |
| **C3** NVIC | `c3` | `src/c3/nvic.c` | arbitragem (grupo/sub/número), preempção, PRIMASK, BASEPRI, encadeamento, repetição — IRQs pendidas por software | periodicidade de timers |
| **C4** USART1 | `c4` | `src/c4/usart.c` | integridade, rajada full duplex, divisor de baud, formatos de quadro, TXE/TC/RXNE/IDLE, leitura atrasada (ORE), pressão de TX, RE | preempção de IRQs |

**Recorte conservador (decisão do autor, alinhada ao plano):**

- **C1** mede primeiro núcleo e memória (resultados e tempos com a referência
  nominal); a calibração do Renode é um **complemento** empírico, executado
  separadamente e **nunca** aplicado a C2–C4. O C1 **não** é uma suíte
  exaustiva da ISA: são 30 casos funcionais nomeados (629 verificações) e 8 cargas
  temporais em 3 tamanhos.
- **C4** trata "concorrência" como **transmissão e recepção em andamento
  enquanto o software tem capacidade limitada de atender a recepção** (leitura
  atrasada, produtor mais rápido que o consumidor), por **polling**. A matriz de
  preempção de IRQs fica no C3; o C4 não a repete.
- Extensão HSE/PLL/72 MHz: **não implementada** (opcional na diretiva;
  priorizou-se a base HSI 8 MHz completa).

Conclusões valem para o **exemplar, versões, configuração e operações
examinados**. Repetições numa placa não são uma amostra de placas.

## 2. Bancada e ambiente

**Hardware:** STM32F103 (base conservadora C8: 64 KiB flash, 20 KiB SRAM),
ST-Link/V2 em SWD (PA13/PA14), **fio PA9 (TX) → PA10 (RX) permanentemente
ligado**. Só o C4 configura USART1 e esses pinos; o gate estático recusa
qualquer outro ELF com literal do endereço da USART1. Clock: **HSI 8 MHz,
HCLK 8 MHz, sem HSE/PLL**, flash com 0 wait states (estado de reset
reescrito explicitamente em `lib/board.c`).

**Software** (tudo pelo `flake.nix`, travado em `flake.lock`): GCC Arm 15.3,
CMake 4.x + Ninja, OpenOCD 0.12, Renode 1.17.0, Python 3 com numpy e
matplotlib, `trace_processor_shell` v58.2 (binário oficial do Perfetto, SHA
fixado). Só x86_64-linux (Linux nativo ou WSL2).

Preparação (uma vez por máquina):

1. Instalar Nix com flakes (em WSL2 recomenda-se o instalador da Determinate
   Systems) e, opcionalmente, `direnv` (`direnv allow` na raiz).
2. **WSL2:** anexar o ST-Link ao WSL a cada sessão, no PowerShell do Windows:
   `usbipd bind --busid <id>` (uma vez) e `usbipd attach --wsl --busid <id>`.
3. **Linux nativo:** regras udev do OpenOCD:
   `sudo cp $(nix eval --raw nixpkgs#openocd)/etc/udev/rules.d/*.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger`.
4. Conferir: `nix develop -c openocd -f interface/stlink.cfg -f target/stm32f1x.cfg -c "init; shutdown"`
   deve detectar `Cortex-M3`.

Depois disso nada é editado por cenário (sem `.resc`, offsets, frequências ou
caminhos manuais).

## 3. Campanha: um comando

```bash
scripts/campaign.sh --name final-genuino-01 --board "stm32f103c8-genuino-lab-01" \
    --board-note "marcação do chip: ..." --calibration
```

O script entra no ambiente Nix se necessário e chama
`scripts/fidelity.py campaign`, que executa, nesta ordem:

1. **pré-verificação** (ferramentas, porta :3333 livre, espaço em disco) e
   **locks** (campanha e bancada: duas campanhas nunca usam o mesmo ST-Link);
2. **build** dos 5 firmwares do zero (`--fresh`; zero warnings), **integridade do `vendor/`**
   (SHA-256 de `vendor/README.md`) e **gate do ELF** (símbolos, RAM,
   literais da USART1 fora do C4, `fid_measure` com SP alinhado, flags);
3. **plano congelado** `plan.json` (hashes dos ELFs e fontes, revisão,
   versões, configuração do Renode, casos planejados, regra de calibração);
4. **placa**: OpenOCD próprio, identificação do exemplar (CPUID, IDCODE,
   F_SIZE, UID — metadados, não autenticação), gravação + verificação de cada
   ELF, N runs com reset definido;
5. **Renode nominal** (8 MIPS): mesmo ELF, **processo novo por run**, N runs
   (paralelos, `--jobs`);
6. **traço por stepi** do C1-timing na placa e no Renode;
7. **calibração** do C1 (com `--calibration`): regra pré-registrada, runs
   do Renode com o MIPS escolhido;
8. **análise**: oráculos, estatística, classificação, figuras, traces
   Perfetto e validação da importação, relatório `analysis/report.md`.

| Parâmetro | Efeito |
|---|---|
| `--name`, `--board` | identidade da campanha e do exemplar físico (obrigatórios) |
| `--reps R` | runs por firmware e ambiente: **50** no modo final, 10 com `--pilot`; aceita 100+ |
| `--firmwares`, `--env` | subconjuntos (`c1-functional c1-timing c2 c3 c4`; `hw renode`) |
| `--calibration` | complemento do C1 (seção 7) |
| `--no-instr` | pula o traço por stepi (o nível "instrução" fica sem evidência) |
| `--resume` | retoma: exige **o mesmo plano** (ELFs, exemplar, repetições, configuração) |
| `--jobs J` | processos Renode simultâneos (padrão 4; não afeta o tempo virtual) |

**Código de saída:** `0` campanha completa (divergências Renode × placa são
resultado científico, não erro); `3` infraestrutura incompleta (runs válidos
abaixo do planejado, traço ausente); `1` erro de pré-condição, build, gate ou
plano incompatível.

**Robustez e identidade dos dados:** cada run tem timeout no host; uma
tentativa que falha (timeout, snapshot inválido, nonce errado) é **guardada**
com o motivo e uma nova é feita, até `N + max(3, N/5)` tentativas. Cada
`run.json` registra o SHA-256 do ELF executado e do snapshot; a análise só
usa runs do ELF congelado no plano e os revalida com o código atual. Na
retomada, ELFs, exemplar (CPUID/IDCODE/F_SIZE/UID), repetições e
configuração do Renode precisam ser os mesmos; mudar só a análise ou a
documentação não bloqueia a retomada. Nenhum processo de terceiros é
encerrado (porta ocupada = erro claro): OpenOCD/Renode/GDB rodam num grupo
de processos próprio, encerrado inteiro ao fim. Snapshots e `run.json` ficam
somente-leitura.

Outros comandos: `scripts/fidelity.py analyze --name N` (refaz a análise),
`run --env hw|renode --firmware F` (um run de diagnóstico, fora de
campanha), `check` (pré-verificação + build + gate).

### Build manual e debug

```bash
cmake --workflow --preset c2          # configure + build → build/c2/firmware.elf
scripts/renode_start.sh c2            # Renode com GDB em :3334 (mesmo .resc da campanha)
```

No VS Code: tasks `Build: <fw>` e configurações `Renode: <fw>` / `Placa: <fw>`
(cortex-debug). O `.clangd` é gerado pelo CMake (aponta para o último preset
configurado).

## 4. Plataforma Renode

- `renode/stm32f103_hsi8.repl`: plataforma `stm32f103.repl` do Renode 1.17.0
  reduzida aos periféricos da família medium-density, memórias com o tamanho
  real e `frequency: 8000000` nos periféricos. GPIOE–G permanecem só porque o
  modelo `STM32F1AFIO` exige 7 portas.
- `renode/fidelity.resc`: **um único script** para C1–C4 (só o ELF muda):
  `PerformanceInMips 8`, quantum global **125 ns**, USART1 ligada a um hub em
  loopback (equivalente ao fio PA9→PA10), `AutoUpdateDelay` desligado.

Decisões registradas (o fonte da versão instalada está no pacote Nix em
`lib/renode/src/`):

| Decisão | Fundamento |
|---|---|
| **8 MIPS nominal**, único para C1–C4 | hipótese de 1 instrução por ciclo a 8 MHz; não é modelo ciclo-preciso. `PerformanceInMips` é `uint` (granularidade inteira) |
| **Quantum 125 ns** (= 1 instrução) em vez de 1 µs | piloto: com 1 µs, o mesmo intervalo medido pelo CYCCNT variava ±4 ticks entre repetições idênticas e ganhava deslocamento (carga vazia: 10 ticks vs 4); com 125 ns é determinístico. 100 ns (fração de instrução) derruba o Renode |
| `AutoUpdateDelay` **desligado** | `STM32_UART` já espaça cada caractere recebido pelo tempo de um quadro (thread do receptor); o atraso do `UARTHub` somaria outro quadro (dupla serialização) |
| Renode com `--port -1` | com `--port N` o `-e` só executa quando um cliente telnet conecta; em erro de comando o Renode **não termina** — por isso todo passo tem timeout e o log fica no run |
| Processo novo por run | estado inicial limpo garantido (sem depender de reset do simulador) |

Mecanismos do modelo que explicam divergências (lidos no fonte 1.17.0; são
explicação, não oráculo):

- **Sem modelo de RCC para o F1** (`sysbus` só tem a *tag* `RCC_CR`):
  escritas em RCC são ignoradas, `RCC_CFGR` lê 0, e a frequência dos timers e
  da USART é a estática do `.repl` (não segue o prescaler APB).
- `STM32_Timer`: PSC aplicado imediatamente (sem preload); UG só seta UIF se
  `UIE = 1`.
- `STM32_UART`: TXE sempre 1, TC setado na escrita de DR, ORE nunca, FIFO de
  recepção ilimitada, palavra de 9 bits (M) não implementada, paridade não
  calculada.
- `DWT`: CYCCNT = tempo virtual × `frequency` (não ciclos de pipeline).

## 5. Instrumentação (ABI v3 "FID3")

Contrato em `inc/fidelity.h` (C) e `scripts/fidelity/abi.py` (decodificador).
Inspiração **conceitual** no registro de eventos do SEGGER SystemView (UM08027:
gravação em RAM e coleta pelo probe após a parada); formato próprio, sem
compatibilidade binária com RTT/SystemView, sem J-Link, sem UART de log.

```
fid_snapshot (objeto global único, little-endian, campos de largura fixa)
  header  40 palavras: magic "FID3", versão, tamanho, firmware, estado
          (RUNNING/DONE/FAILED), erros, nonce do host, capacidades e
          contagens, head de cada anel, próximo ticket, CYCCNT inicial/final,
          custo do observador e do logger, HCLK nominal, CPUID, IDCODE,
          F_SIZE, UID, RCC_CR/CFGR, FLASH_ACR, DBGMCU_CR, AIRCR, pilha livre,
          PC/CFSR de falha
  cases   {case_id, status, first_word, word_count}   (só MAIN escreve)
  words   dados dos casos, em sequência               (só MAIN escreve)
  ring    4 anéis circulares {ticks, ticket, event, case_id, arg}
          um por CONTEXTO ESCRITOR fixo: MAIN, IRQ1, IRQ2, IRQ3
```

- **Sem posição global compartilhada:** cada anel tem um único escritor
  (MAIN ou um handler), então o registro não mascara interrupções. O handler
  tem o seu anel mesmo que seu papel/prioridade mude entre casos.
- **Ordem global:** cada evento recebe um *ticket* de um contador global
  incrementado com LDREX/STREX; o CYCCNT é lido **dentro** do laço
  exclusivo. Se uma exceção acontece no meio, o monitor exclusivo é limpo
  (ARMv7-M) e o laço repete: ticket e timestamp são consistentes. O host
  exige tickets únicos, crescentes por escritor e contíguos (sem lacunas).
- **Anéis circulares com detecção de perda:** `head` conta tudo que foi
  escrito; `head − capacidade` registros antigos foram sobrescritos. O
  registro é escrito inteiro antes de o `head` avançar (DMB). Os tamanhos
  foram dimensionados para que nenhum caso obrigatório perca eventos; se
  perder, métricas dependentes do trace são invalidadas e o trace leva aviso.
- **Rollover:** o CYCCNT é pré-carregado em `0xFFF00000`; o primeiro estouro
  ocorre após 2^20 ticks (≈131 ms nominais). Runs mais curtos não cruzam o
  estouro. O host reconstrói o tempo pelos tickets e diferenças módulo 2^32,
  incluindo o trecho final, e rejeita passos ≥ 2^31 ticks (≈268 s nominais).
  A reconstrução exige trace completo e intervalos reais menores que esse
  limite; aritmética modular sozinha não identifica wraps inteiros ocultos.
  Os testes sintéticos incluem mais de um wrap distribuído entre eventos.
- **Prova de run:** o host para em `main`, grava um nonce aleatório em
  `fid_host_nonce`; o firmware o copia para o header. Snapshot de outro run
  (a SRAM sobrevive ao reset) é rejeitado.
- **Finalização:** o firmware para os estímulos, desliga as IRQs, captura
  registradores de contexto, mede a pilha nunca usada (pintura em `fid_init`)
  e publica DONE ou FAILED antes de parar em `fid_complete()` (hbreak do
  host). Falhas (HardFault) publicam FAILED com PC e CFSR em vez de travar.
- **Estados distintos:** DONE (instrumento íntegro), FAILED (instrumento),
  status por caso OK/TIMEOUT (protocolo do caso), e no host: run válido,
  inválido (motivo) ou falha de infraestrutura.
- **Interferência:** o debugger fica conectado (hbreak), sem polling de
  SRAM durante o run; o custo do observador (2 leituras do CYCCNT) e do
  logger é medido e gravado em cada run.
- **Bracket do C1** (`lib/fidelity_measure.S`): `LDR CYCCNT → BLX fn → LDR
  CYCCNT` em assembly (o GCC não consegue mover a chamada), empilhando 6
  registros para manter o SP alinhado a 8 bytes no `BLX` (AAPCS).

Orçamento de SRAM (20 KiB), conferido pelo gate e pela pilha livre medida
em cada run:

| Firmware | `.data + .bss` | pilha/heap reservados | pilha nunca usada (placa) |
|---|---|---|---|
| c1-functional | 15 452 B | 1 536 B | ≈ 4,6 KiB |
| c1-timing | 15 060 B | 1 536 B | ≈ 5,2 KiB |
| c2 | 12 516 B | 1 536 B | ≈ 7,6 KiB |
| c3 | 10 980 B | 1 536 B | ≈ 9 KiB |
| c4 | 9 528 B | 1 536 B | ≈ 10,5 KiB |

## 6. Casos, oráculos e critérios

Os oráculos são escritos à mão a partir do manual, **não** a partir de
resultados da placa ou do Renode (`scripts/fidelity/c1.py` … `c4.py`):

- **C1-functional** (30 casos, 629 verificações): `uint32`/`int32`/`uint64`
  (wrap, divisão truncada, sem UB), comparações, lógica, deslocamentos
  (≥ 0 e ≤ 31), rotações, campos de bits, CLZ/CTZ/popcount, promoções de 8/16
  bits, extensão de sinal/zero e truncamento, SRAM por 8/16/32 bits (ordem de
  bytes, vizinhos preservados, padrões 0/1/alternados, bit caminhante), flash
  `.rodata` por 8/16/32 bits (leituras por ponteiro `volatile`, endereço
  conferido), cópia desalinhada e preenchimento (bloco inteiro conferido),
  ordenação, MDC, `switch` e recursão. O `switch` testa o resultado do
  despacho: neste ELF o GCC o reduz a seleção aritmética/condicional, não a
  tabela de salto. O caso adicional usa acessos desalinhados de 16/32 bits
  em SRAM (offsets 1/2/3, `UNALIGN_TRP=0`) e verifica os bytes vizinhos; o
  gate exige LDR/LDRH/STR/STRH nos quatro helpers. Acessos de 16 bits à
  representação de objetos de 32 bits usam `may_alias`, e os helpers
  desalinhados usam `packed` + `may_alias`, extensões GNU documentadas.
  `volatile` sozinho não torna aliasing incompatível válido. Cada caso grava
  ENTRADAS e SAÍDAS; o host confere as entradas com o plano. Conversões
  dependentes da implementação seguem a convenção do GCC (módulo 2^N,
  `>>` aritmético) e estão marcadas.
- **C1-timing**: cargas C `noipa` — vazia, ALU (xorshift), MUL, UDIV com
  quociente pequeno e grande (mesmas instruções, operandos diferentes), cópia
  SRAM, soma em flash, desvios dependentes de dados, CRC-32 bit a bit — em
  n = 16, 64, 256 (linearidade e custo fixo), 4 repetições com entradas
  idênticas (rep 0 = primeira após o reset). O resultado de toda execução é
  conferido. Na cópia SRAM, todas as palavras do destino são coletadas e
  verificadas em cada repetição, fora do bracket temporal; o retorno da
  função por si só não comprova a cópia inteira.
  Corpo do laço de cada carga conferido no ELF (`arm-none-eabi-objdump -d`,
  GCC 15.3 `-O2`; o traço por stepi confirma o caminho dinâmico):

  | Carga | Laço interno (por iteração) |
  |---|---|
  | `empty` | `EORS; BX LR` (sem laço) |
  | `alu` | `EOR.W lsl#13; ADDS; EOR.W lsr#17; CMP; EOR.W lsl#5; BNE` (6) |
  | `mul` | `MLA; ADDS; CMP; BNE` (4) |
  | `div_small` / `div_large` | `LDR [r2],#4; UDIV; CMP; ADD; BNE` (5) — mesmas instruções, operandos diferentes |
  | `sram_copy` | `LDR [r2],#4; ADDS; CMP; STR [r1],#4; BNE` (5) |
  | `flash_sum` | `AND #63; LDR [flash]; ADDS; CMP; ADD; BNE` (6); o GCC propagou T[0] como imediato, os demais vêm da flash |
  | `branch` | `LDR; TST #1; BNE` → (`CMP; ADD; BEQ`) ou (`TST #2; ITE; EORNE/SUBEQ; CMP; BNE`) |
  | `crc` | por byte `LDRB; EORS; MOVS #8` + por bit `SBFX; ANDS; SUBS; EOR lsr#1; BNE` (5) |

- **C2**: RM0008 §7.2 (TIMxCLK = PCLK se APB /1, senão 2×PCLK), §15.3–15.4
  (PSC sempre bufferizado; ARR bufferizado só com ARPE; UG reinicia CNT e,
  com URS = 0, seta UIF), PM0056 §4.3 (pending registrado até entrar no
  handler ou ICPR). Preload: o firmware escreve o novo PSC/ARR com CNT ≥ 500
  e mede o tempo até o próximo update; as duas hipóteses (antigo × novo,
  imediato × no próximo update) diferem em milhares de ticks, e o resultado
  é "ambíguo" se a medida não estiver claramente mais perto de uma delas.
  CNT lido no início da ISR é a **fase** desde o update (inclui entrada,
  prólogo e acesso ao barramento; não é custo puro de exceção). Nos casos
  atrasado/coalescido o timer é parado antes de liberar a IRQ e o número de
  updates no intervalo é **inferido** da configuração. Os registradores do
  RCC lidos de volta (`RCC_CFGR` por perfil APB, `RCC_APBxENR` por timer)
  formam um caso de contexto próprio, `c2/rcc`: o Renode não modela o RCC do
  F1, e essa lacuna não é repetida em cada caso de timer — seus efeitos
  aparecem onde existem (ex.: razão TIMCLK/HCLK no perfil /4). A leitura de
  CNT imediatamente após o UG fica como dado sem oráculo (o manual não diz
  quando o reinício fica visível).
- **C3**: sequências completas esperadas escritas à mão a partir do PM0056 e
  do ARMv7-M ARM (grupo > sub > número; preempção só por grupo; PRIMASK;
  BASEPRI com prioridade igual mascarada; repetição roda antes de prioridade
  menor), com TODAS as ocorrências (inclusive a 2ª entrada de quem se repende)
  e o IPSR em cada entrada. PRIGROUP = 5 (2 bits de grupo, 2 de sub).
- **C4**: RM0008 cap. 27 (baud = PCLK2/BRR; paridade no MSB da palavra; ORE
  com RXNE = 1 perde o byte novo e mantém o anterior; SR → DR limpa
  RXNE/IDLE/ORE). Bytes sempre em sequência indexada; espera por recepção
  completa ou timeout; produtor da leitura atrasada espaçado por 1,5 quadro no
  DWT (não por TXE), seguido de guardas temporais e registro das escritas e
  leituras para distinguir retenção em RX de entrega tardia. O payload local
  `0x43340002` registra BRR/CR1/CR2/CR3, erros acumulados antes de DR, SR
  final e confirmação de TC; layouts anteriores são recusados. **Limitação:** o loopback não testa detecção de erro de
  paridade/enquadramento (exigiria estímulo divergente).

**Critérios (declarados antes da campanha):**

| Observável | Critério |
|---|---|
| funcional (valor, flag, ordem, contagem) | todos os valores observados e todas as falhas; concordância exige valores constantes iguais, e conformidade com o oráculo é um eixo separado |
| temporal | diferenças de medianas, média, desvio padrão amostral, extremos e valores distintos por reset; igualdade de medianas é somente igualdade observada |
| **instrução** (C1) | sequência de PCs por stepi idêntica no intervalo; evidencia o caminho dinâmico, sem validar o estado após toda instrução |

Classes por caso: **1** concordância funcional e mesmas medianas temporais
observadas; **2** concordância funcional com diferença temporal; **3** valores
funcionais diferentes ou não conformidade com a especificação; **4** evidência
insuficiente. A classe 3 distingue explicitamente diferença HW×Renode de
coincidência entre dois comportamentos contrários ao manual. Casos sem
observável temporal não ganham conclusão temporal. Falhas de instrumento
ficam na contabilidade e impedem a completude; não viram divergência física.

**Nível de ciclo:** só há concordância temporal quando as medianas por reset
são **iguais** (tick a tick); qualquer diferença é reportada com valor
absoluto e relativo, sem margem de aceitação (nenhum prazo de aplicação foi
definido). Repetições internas (bytes, IRQs) são agregadas por reset e não
contam como amostras independentes. A conversão para µs
usa HSI **nominal**: não mede a frequência física nem calibra o tempo de
parede do hardware.

## 7. Complemento de calibração (só C1)

Regra pré-registrada em `scripts/fidelity/campaign.py` (`CALIBRATION_RULE`),
gravada no plano antes da coleta: treino = ALU, cópia SRAM, soma em flash e
desvios (n = 256); avaliação = MUL, UDIV pequeno/grande e CRC; objetivo =
menor erro relativo absoluto **médio, pesos iguais**, no treino; previsão
ticks(m) = ticks(8)·8/m; busca em inteiros 1–16 (o Renode só aceita
inteiros); verificação com runs reais (`renode-calibrated`). O quantum dos
runs calibrados é o menor múltiplo inteiro de instruções representável em
ns (ex.: 7 MIPS → 1 µs). O valor é derivado dos dados de cada campanha; o
relatório mostra o erro por carga e agregado, nominal × calibrado.

Como o quantum pode mudar junto com MIPS (nesta revisão: 8 MIPS/125 ns →
6 MIPS/500 ns), o complemento compara **configurações**. Não isola o efeito
causal de MIPS. Para atribuí-lo isoladamente, seria necessário um controle
adicional a 8 MIPS com o mesmo quantum do calibrado; esse controle fica fora
da matriz principal. A melhoria de média não prova precisão de ciclo.

## 8. Dados e traces

```
data/fidelity/<campanha>/
  plan.json  campaign.log  calibration.json
  build/<fw>.log
  hw/sessions/run-NNN/{openocd.log, identify.json, flash-<fw>.log}
  hw/<fw>/run-NNN/{snapshot.bin, run.json, gdb.log, gdb.gdb}
  renode-nominal/<fw>/run-NNN/{snapshot.bin, run.json, renode.log, gdb.log}
  renode-calibrated/c1-timing/run-NNN/...
  instr/{hw,renode}/{instructions.json, stepi.log}
  analysis/{report.md, *.csv, figures/, perfetto/}
```

`run.json` guarda status, motivos, nonce, SHA-256 do snapshot, header
decodificado, tempo de host (separado dos ticks do alvo) e, no Renode,
instruções executadas, MIPS efetivo, tempo virtual e acessos a endereços não
modelados. `data/` não é versionado; `data/exploratory/` guarda as coletas
antigas (ABIs v1/v2), fora da análise.

**Perfetto:** `analysis/perfetto/runs/<ambiente>/<fw>/run-NNN.json` (um por
run) e `compare-<fw>.json` (run de duração total **mediana** de cada
ambiente, ambos com ts = 0 no início do run — alinhamento declarado, sem
reescalar durações). Formato Chrome Trace Event JSON (µs); abrir em
<https://ui.perfetto.dev> (*Open trace file*). Trilhas por contexto escritor
(MAIN, cada ISR) — trilhas paralelas não significam execução simultânea;
eventos previstos/inferidos ficam na categoria `inferido`; handlers do C3 têm
duração inclusiva no slice e exclusiva nos args; pedido → atendimento por
*flow*. A importação é conferida com `trace_processor_shell` (contagem de
slices, counters e flows por trilha; nomes, tempos e durações de todos os
slices importados), em
`perfetto/validation.json`. Estatística vem dos dados brutos, não do Perfetto.

## 9. Validações realizadas

### 9.1 Histórico anterior a este refinamento

As validações e números desta subseção pertencem à implementação anterior
à revisão adicional. Os layouts atuais de C1/C2/C4 e os critérios de análise
mudaram; estes resultados não validam automaticamente os fontes atuais.
Relatórios históricos são preservados e layouts incompatíveis não são
reinterpretados pelos oráculos atuais.

Executadas em 2026-10-09 nesta máquina (WSL2, x86_64), com Renode 1.17.0
(build `1.17.0+gitab721d88`), GCC Arm 15.3.1, OpenOCD 0.12.0, Python 3.14,
`trace_processor_shell` v58.2 e a placa atual (provável clone; ver §10–11).

| O quê | Como | Resultado |
|---|---|---|
| Build dos 5 presets | `cmake --workflow --preset <fw>` a partir de árvore limpa | ok, **0 warnings** (`-Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes`) |
| Reprodutibilidade do ELF | dois builds do zero; build da campanha com `cmake --preset <fw> --fresh` | hashes idênticos. Os ELFs de `prelim-clone-50` vieram de árvores incrementais e diferem do build limpo **só na informação de debug**: o traço por stepi do ELF limpo reproduz as 25 sequências de PCs da campanha. Desde então a campanha sempre reconfigura do zero |
| Integridade do `vendor/` | SHA-256 contra `vendor/README.md` (na campanha) | ok |
| Gate do ELF | símbolos, RAM ≤ 20 KiB, literais da USART1 só no C4, `fid_measure` com 6 registros | ok nos 5 |
| Pilha | pintura em `fid_init`, medida em cada run | ≥ 4,6 KiB nunca usados (pior caso: c1-functional) |
| Smoke na placa | 1 run de cada firmware (gravação verificada) | DONE, todos os casos, nonce confere |
| Smoke no Renode | 1 run de cada firmware | DONE, todos os casos, nonce confere |
| Quantum | C1-timing com 1 µs e 125 ns | 1 µs: ±4 ticks entre repetições idênticas; 125 ns: determinístico → **congelado em 125 ns** |
| Decodificador (testes de desenvolvimento) | snapshots sintéticos válidos e corrompidos: magic, versão, tamanho, estado, capacidade, palavras fora de ordem, status, truncado, tickets duplicados/decrescentes/faltando, anel sobrescrito, rollover de 32 bits com eventos repetidos, tempo andando para trás, nonce/plano/estado/falha | todos rejeitados/detectados como esperado |
| Oráculos (testes negativos) | saída errada, entrada fora do plano, byte vizinho alterado em SRAM, sequência do C3 reduzida (2ª entrada de quem se repende removida) | todos detectados |
| Campanha (testes) | lock duplo; plano congelado (ELF/exemplar diferente na retomada); porta :3333 ocupada; OpenOCD que não sobe; run do Renode com timeout (filho encerrado); campanha cujos runs nunca terminam (tentativas guardadas como falha, limitadas, saída 3) | todos com erro claro / contabilidade correta |
| Traço por stepi | C1-timing, 25 combinações carga × tamanho, placa e Renode | **sequências de PCs idênticas** nas 25; Renode: ticks = instruções + 1; placa: 24 min, Renode: 3 min |
| Perfetto | importação com `trace_processor_shell` v58.2: contagem de slices, counters, flows, slices **por trilha** e tempo/duração de um slice vs. ticks | 16/16 arquivos conferidos no piloto. A conferência por trilha pegou um defeito real (tid 0 e tids repetidos misturavam trilhas no comparativo), corrigido antes da campanha |
| Piloto `pilot-clone2` | `--pilot --calibration`, 10 runs × 5 firmwares × 2 ambientes + calibrado | completo: 110/110 runs válidos, 0 tentativas falhas, 32,6 min, 13 MiB |
| Repetibilidade | observáveis idênticos em todos os runs | placa 1420/1420, Renode 1419/1419 (determinismo observado) |
| Campanha preliminar `prelim-clone-50` | `scripts/campaign.sh` (ponto de entrada real), 50 runs, `--calibration` | completa (exit 0): 550/550 runs válidos sem tentativa falha (placa 250, Renode nominal 250, Renode calibrado 50), 52 min, 42 MiB, 550 traces Perfetto, 16/16 importações conferidas; `--resume` sobre ela não recoleta nada e só reanalisa (12 s) |

Os testes de desenvolvimento (`tests/test_fidelity.py`, 20 testes) existiram
durante a implementação e estão no histórico do repositório; por decisão do
autor não fazem parte da árvore final.

**Por que 50 repetições:** no piloto, todo observável da placa e do Renode
foi idêntico nos 10 runs (sem dispersão observada). Isso não demonstra ausência
de jitter ou falhas raras. As 50 repetições são um orçamento de coleta para
registrar repetibilidade e aumentar a oportunidade de observar falhas, sem
justificativa universal de suficiência nem intervalo de confiança implícito.
Se a placa genuína mostrar dispersão, definir o número a partir da precisão
ou taxa de falhas que se pretende estudar (`--reps 100` disponível).


### 9.2 Refinamento adicional (revisão de 2026-10-09)

Uma revisão independente corrigiu aliasing no C1 (`may_alias`/`memcpy`),
acrescentou o caso de acesso desalinhado (LDR/STR/LDRH/STRH conferidos no
ELF pelo gate), passou a conferir a cópia SRAM inteira, registrou a
configuração realmente aplicada em C2–C4 (PSC/ARR/CR1, prioridades, BRR/CR),
parou o timer antes de liberar a IRQ atrasada, isolou a EXTI no C3,
acumulou erros da USART antes de ler DR e versionou o payload do C4. A
análise passou a mostrar todas as observações (não só o valor mais comum) e
a separar "placa × Renode" de "conformidade com o manual". Isso corrigiu
também uma descrição errada da versão anterior (o `switch` do C1 vira
aritmética condicional, não tabela de salto).

Na sequência, três ajustes desta entrega: (1) os registradores do RCC
saíram de cada caso do C2 para o caso de contexto `c2/rcc` — antes, uma
única lacuna do modelo marcava todos os recursos de timer como divergentes;
(2) PSC/ARR preload voltaram a ter oráculo do RM0008, com regra explícita de
ambiguidade; (3) camadas redundantes de proteção no coletor e na análise
foram removidas (publicação atômica por hardlink, revalidação completa a
cada contagem, cadeia de hashes do traço, varredura de `/proc` para "dono"
de socket), mantendo o que identifica os dados: plano congelado, hash do
ELF e do snapshot por run, nonce e identidade do exemplar.

Validação desta rodada (código e firmwares atuais), na placa atual (provável
clone) e no Renode 1.17.0, pelo ponto de entrada real `scripts/campaign.sh`:

| O quê | Resultado |
|---|---|
| Build + gate dos 5 presets (`fidelity.py check`) | 0 warnings; gate confere LDR/LDRH/STR/STRH dos acessos desalinhados no ELF |
| Piloto `pilot-clone3` (`--pilot --reps 5 --calibration`, placa + Renode + stepi) | **completo (exit 0)**: 5 runs válidos por firmware e ambiente, sem tentativa falha; 55 traces Perfetto, 16/16 importações conferidas |
| Traço por stepi do `c1-timing` atual | **25/25 combinações com a mesma sequência de PCs** na placa e no Renode; Renode: ticks = instruções + 1 em todas |
| Repetibilidade | placa 2041/2041 e Renode 2038/2038 observáveis idênticos nos 5 resets |
| Retomada real | a sessão caiu durante o traço da placa (o WSL perdeu o ST-Link); `--resume` não recoletou nada; sem a placa terminou com **exit 3** (incompleta); com a placa de volta refez só o traço e terminou com exit 0 |
| Proteções do coletor (verificação avulsa) | plano existente sem `--resume` recusado; retomada com exemplar, repetições ou ELF diferentes recusada; mudança só de ferramentas/análise aceita; contagem só de runs válidos do ELF congelado; lock duplo recusado; timeout do Renode vira falha de infraestrutura sem deixar processo |

O mapa por recurso do piloto (`data/fidelity/pilot-clone3/analysis/report.md`)
separa agora a lacuna do RCC (`c2/rcc`) dos comportamentos de timer: o
Renode diverge do manual em RCC, PSC preload, UG/URS (UIF com UIE = 0),
árvore de clock no perfil APB /4, TC e paridade/9 bits da USART; concorda em
ARR (com e sem preload), UIF × UIE × pending, IRQ periódica, atendimento
atrasado, coalescência, todo o C3 e todo o C1. No overrun da USART, placa
atual e Renode coincidem e ambos divergem do RM0008.


## 10. Resultados preliminares (placa atual — provável clone)

Resumo histórico (firmwares anteriores à revisão; os do código atual estão no
piloto `pilot-clone3`, §9.2) de `data/fidelity/prelim-clone-50/analysis/report.md` (50
runs, implementação e critérios anteriores ao refinamento). Não deve ser
transcrito como resultado dos fontes atuais. Vale para este exemplar e para
a versão então coletada; a resposta final exige nova coleta na placa genuína
com a implementação atual (§11).

| Nível | Onde o Renode 8 MIPS acompanha a placa | Onde diverge (e mecanismo no fonte do modelo) |
|---|---|---|
| **Funcional** | C1 inteiro (29 casos, 595 valores); C3 inteiro (18 sequências completas, inclusive repetição, IPSR, PRIMASK/BASEPRI); C2: contagem parada, ARR com/sem preload, UIF × UIE × pending, atendimento atrasado, coalescência; C4: integridade, rajada, divisor de baud, RE | C2: `RCC_CFGR` lê 0 e o timer **não segue o prescaler APB /4** (sem RCC F1); PSC aplicado na hora (sem preload); UG com URS = 0 não seta UIF quando UIE = 0. C4: TC nunca cai; paridade e palavra de 9 bits não modelados |
| **Instrução** | C1-timing: **mesma sequência de PCs nas 25 combinações** carga × tamanho (stepi) | — (não avaliado em C2–C4) |
| **Ciclo** | período do timer com ARR preload; período de quadro da USART (±10 ticks: a serialização é modelada) | tempo = 1 tick por instrução: placa com 1,17 (ALU) a 3,56 (UDIV de quociente grande) ciclos por instrução; UDIV com operandos diferentes custa o mesmo no Renode; latência da IRQ do timer 18 × 3 ticks; intervalos do NVIC ~2× menores no Renode; produtor da USART 25× mais rápido (TXE sempre 1) |

Observações históricas sobre o exemplar: houve **repetibilidade observada**
(todos os observáveis então considerados idênticos nos 50 runs); a placa paga ~110 ciclos na 1ª execução
de cada trecho de código em flash; e a USART desta placa guarda ≥ 8 bytes sem
ORE — divergindo do RM0008 **e coincidindo** com o Renode, que tem FIFO
ilimitada. Essa concordância é coincidência do exemplar, não fidelidade ao
STM32F103 especificado. Calibração (C1): o MIPS escolhido pela regra foi 6;
o erro médio caiu de 28% para 11% no treino e de 48% para 31% na avaliação,
o que melhora a média sem tornar o custo por instrução correto.

## 11. Pendência: campanha final na placa genuína

**A validação final em STM32F103 genuíno NÃO foi realizada nesta entrega.**
A única placa disponível durante o desenvolvimento é, muito provavelmente, um
compatível/clone: UID de 96 bits todo zero, F_SIZE = 128 KiB num "C8",
CPUID r2p0, USART que guarda ≥ 8 bytes sem sinalizar ORE e ~110 ciclos extras
na primeira execução de cada trecho de código em flash. Os dados dessa placa
(`pilot-clone*`, `prelim-clone*`) servem para desenvolver e diagnosticar e
têm identidade própria; **não substituem** a campanha final.

Com a placa genuína do laboratório na bancada (fio PA9→PA10, ST-Link):

```bash
scripts/campaign.sh --pilot --name piloto-genuino-01 --board "<etiqueta da placa>" \
    --board-note "<marcação do chip>"            # ~45 min: confere dispersão e duração
scripts/campaign.sh --name final-genuino-01 --board "<etiqueta da placa>" \
    --board-note "<marcação do chip>" --calibration   # 50 runs por firmware e ambiente
```

O resultado (`data/fidelity/final-genuino-01/analysis/report.md`) é a
entrada para a monografia. Se a placa genuína tiver outra revisão de núcleo,
outra densidade de flash ou outro comportamento de USART, isso aparece na
identificação e nas colunas "placa × especificação"; nenhum oráculo depende
dos resultados da placa atual.

## 12. Estrutura

```
src/c1..c4/      firmwares (um main por preset)
lib/             board.c (clock HSI 8 MHz), fidelity.c + fidelity_measure.S (ABI)
inc/fidelity.h   contrato da ABI FID3
vendor/          ST/CMSIS/LL congelados (SHA-256 em vendor/README.md) — nunca editar
renode/          plataforma .repl + script único fidelity.resc
scripts/         campaign.sh (entrada), fidelity.py (CLI), fidelity/ (pacote),
                 renode_start.sh / renode_stop.sh / direnv_exec.sh (VS Code)
cmake/           toolchain + modelo do .clangd
tmp/REQUISITOS-ENTREGA-FINAL-TCC.md   diretiva desta entrega (mantida)
```

## 13. Fundamentos e limites de cobertura

Referências que definem os contratos dos casos (a biblioteca acadêmica está
no Zotero e em `D:\tcc`, fora do repositório):

- [ST RM0008, Rev. 21](https://www.st.com/resource/en/reference_manual/rm0008-stm32f101xx-stm32f102xx-stm32f103xx-stm32f105xx-and-stm32f107xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf):
  árvore de clock, PSC/ARR/update e USART. Zotero: `N7JVRKFW`.
- [ST PM0056, Rev. 7](https://www.st.com/resource/en/programming_manual/pm0056-stm32f10xxx20xxx21xxxl1xxxx-cortexm3-programming-manual-stmicroelectronics.pdf):
  exclusividade e exceções (§2.2.7–2.3.7), alinhamento (§3.3.5), NVIC e
  máscaras. Zotero: `IZMAAGNW`.
- [GCC: atributos de tipos](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Common-Type-Attributes.html),
  [conversões de inteiros](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Integers-implementation.html)
  e [otimização/strict aliasing](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Optimize-Options.html):
  extensões GNU e escolhas da implementação usadas pelo C1. O executável
  é ARM32 em ambos os ambientes; o tamanho de `int` no host x86 não define
  o resultado do alvo.
- [Renode: framework de tempo](https://renode.readthedocs.io/en/latest/advanced/time_framework.html):
  MIPS e tempo virtual. Mecanismos particulares do STM32 são conferidos no
  fonte da versão instalada, não presumidos a partir da documentação latest.
- [SEGGER SystemView UM08027](https://www.segger.com/downloads/jlink/UM08027_SystemView.pdf)
  e [Perfetto: formatos externos](https://perfetto.dev/docs/getting-started/other-formats):
  inspiração conceitual do registro em RAM e contrato do JSON importado.
  O trace deste projeto não implementa o protocolo RTT/SystemView.

A cobertura atende ao recorte das quatro áreas, com limites explícitos:

- C1 não cobre toda a ISA, bit-banding, acessos que devem provocar faults,
  exclusividade como experimento dedicado, ou flash sob HSE/PLL/wait states.
- C2 caracteriza três timers e alguns perfis APB; não cobre toda a árvore
  RCC, todos os modos de captura/compare/PWM nem um estímulo imprevisível.
  A IRQ é assíncrona à execução da thread, mas o timer é determinístico.
- C3 cobre seleção, preempção, encadeamento e máscaras configuráveis. Não
  isola os ciclos de stacking/tail-chaining, nem late arrival, FAULTMASK,
  NMI ou prioridade de faults.
- C4 testa sobrecarga e formatos em loopback. PE/FE por estímulo divergente,
  baud físico, tolerância a clocks independentes e forma de onda exigem
  instrumentação ou outra fonte serial. Um limite inferior de retenção
  observado não demonstra capacidade infinita.

Esses limites delimitam as conclusões, sem ampliar a matriz obrigatória
para além do plano. HSE/PLL/72 MHz é uma extensão posterior útil para
flash e clock, condicionada a um modelo RCC/flash e a medição independente;
não corrige por si só o modelo temporal de instruções do Renode.
