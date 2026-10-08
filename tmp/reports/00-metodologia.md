# Fidelidade Renode × bancada — metodologia comum aos quatro cenários

*Relatório intermediário (tmp/, não versionado) — sessão autônoma 2026-10-07/08.
Código: `src/s{1..4}/`, `lib/fidelity*.{c,S}`, `scripts/fidelity/`. Dados:
`data/fidelity/v1/`. Fontes com página verificada no PDF (Zotero) salvo
indicação contrária.*

## 1. Pergunta e unidade de análise

> Em quais cenários, e até que nível de recurso de hardware, o Renode produz
> resultados funcional e temporalmente equivalentes à bancada?

A validação de um modelo de simulação só tem sentido **relativa a um
propósito e a um domínio de condições**, com a precisão requerida declarada
antes da coleta (SARGENT, 2013, §1, p. 321; §4, passos 2 e 6, p. 326 — PDF
externo). Por isso cada cenário separa:

1. **Fidelidade funcional** — valores, ordens de eventos e estados de
   registrador; julgada contra um *oráculo independente* (host, manual) e,
   depois, HW × Renode. Diferença funcional = falha do modelo (ou da placa).
2. **Fidelidade temporal** — durações, latências e razões; reportadas com
   valor e unidade **sem margem de aceitação arbitrária**. O que se testa é se
   a discrepância é **explicada por um mecanismo identificado** (fonte do
   Renode, manual ARM/ST) e se é **previsível**.

## 2. Modelo temporal explícito (o "furo" do tempo virtual)

Pela equação de desempenho do processador (HENNESSY; PATTERSON, 2019, 6. ed.,
§1.9, pp. 52–54):

    T = IC × CPI × T_clk,   CPI = Σ_i IC_i·CPI_i / IC

- **HW (Cortex-M3 r2p0 a 8 MHz, 0 wait states):** CPI_i por classe, dado pela
  ARM DDI 0337G (Tab. 18-1, pp. 18-3..18-5; §18.3, pp. 18-7..18-8) e *medido*
  — H&P p. 54: "CPI_i should be measured and not just calculated from a table
  in the back of a reference manual".
- **Renode 1.17:** o tempo virtual avança `instruções ÷ PerformanceInMips`
  (`BaseCPU.cs` L508–520, `renode-infrastructure@066a7f13`); periféricos
  (TIM, DWT, UART) contam esse tempo virtual. Logo, com MIPS = M e o DWT
  modelado a f = 8 MHz, **todo tipo de instrução custa f/M ticks** — um CPI
  uniforme imposto. Com M = 8, CPI_RN ≡ 1.
- **Consequência:** T_HW / T_RN = CPI_HW(carga) × M / f. Nenhum M único
  iguala cargas de CPI diferente; e a entrada/saída de exceção, que custa 12/6
  ciclos no HW (DDI0337G §5.5 p. 5-13, §5.6 p. 5-14), custa 0 no tlib.

Configurações do Renode (pré-declaradas em `scripts/fidelity/campaign.py`):

| rótulo | MIPS | quantum | papel |
|---|---|---|---|
| `rn-m8-q1us` (nominal) | 8 | 1 µs | hipótese "1 instrução por ciclo de HCLK" |
| `rn-m100-q1us` (controle) | 100 | 1 µs | padrão do Renode |
| `rn-m8-q125ns` | 8 | 125 ns | sensibilidade à sincronização |
| `rn-m7-q1us` (calibrada) | 7 | 1 µs | **único** valor global = inteiro mais próximo de 8/CPI(mix S1A) |
| `…-nodelay` (só S3) | 8/7 | 1 µs | UART sem `AutoUpdateDelay` |

O Renode **trunca `PerformanceInMips` para inteiro** (6,545 → 6, observado em
S1A: 18 instruções = 24 ticks). A calibração tem, portanto, granularidade de
~13 % a 8 MHz. O valor calibrado é derivado de um único kernel designado (mix
congelado do S1A) e **validado fora da amostra** (S1B, S2A, S4); nunca por
cenário, nunca depois de ver o resultado.

## 3. Ambiente experimental

| item | valor |
|---|---|
| Placa | "Blue Pill" vendida como STM32F103C8T6 — **ver §5 (provável clone)** |
| Núcleo | CPUID 0x412FC230 = Arm Cortex-M3 **r2p0** |
| Clock | HSI 8 MHz, AHB/APB /1, FLASH_ACR = 0x30 (0 WS, prefetch on) |
| Depurador | ST-Link V2 (V2J37S7), OpenOCD 0.12.0 próprio por lote |
| Loopback | PA9 (TX) → PA10 (RX) **permanente** em todos os cenários |
| Toolchain | gcc-arm-embedded 15.3.1, `-O2 -g3` nos firmwares finais |
| Simulador | Renode 1.17.0 (`renode-infrastructure@066a7f13`, `tlib@167decf9`) |
| Plataforma | `renode/stm32f103_hsi8.repl` (timers/UART/DWT a 8 MHz) |

## 4. Protocolo comum

- **Mesmo ELF** nos dois ambientes (sha256 no manifesto de cada run).
- **ABI v2** (`inc/fidelity.h`): o firmware é um experimento finito que grava
  resultados num único objeto, congela-o (`fidelity_finish`) e para em
  `fidelity_complete`; o coletor (GDB) faz o dump **depois** do congelamento —
  nenhuma amostragem pelo depurador durante a medição.
- Cada run = reset completo → execução → dump. HW: 10 runs por firmware;
  "free-run" (sem depurador conectado, *polling* do OpenOCD desligado) em
  S1A/S2A/S4B para medir o efeito do observador.
- **Gate estático** antes de cada campanha (`scripts/fidelity.py gate`): no
  ELF, conta as instruções de cada corpo de kernel, confere o bracket de
  medição, a posição flash/SRAM, o orçamento de RAM e a **ausência de acesso à
  USART1 fora do S3** (loopback físico).
- **Bracket de medição em assembly** (`lib/fidelity_measure.S`): LDR CYCCNT ·
  BLX · LDR CYCCNT. Motivo: em C, o GCC -O2 inferiu as cargas "pure" e moveu a
  chamada para fora de duas leituras `volatile` do DWT (observado: crc32 =
  1 tick).
- **Primeira execução**: no HW, a 1ª execução de cada função em flash custa
  ciclos extras (§5); os firmwares registram uma linha COLD separada; as
  estatísticas "quentes" excluem-na explicitamente.

## 5. Ameaça à validade: identidade da placa

Evidências, todas lidas pelo depurador ou medidas:

| traço | esperado (STM32F103 genuíno) | observado |
|---|---|---|
| CPUID | r1p1 (0x411FC231) segundo relatos de identificação de clones | r2p0 (0x412FC230) |
| UID 96 bits (0x1FFFF7E8) | único de fábrica | **todo zero** |
| Overrun da USART | ORE no 2º byte sem leitura; RDR único (RM0008 §27.3.3, pp. 795–796; §27.6.1, p. 819) | **≥4 bytes bufferizados, ORE nunca** |
| Execução em flash | sem cache (RM0008 §3.3.3, p. 54: só *prefetch buffer* 2×64 bits) | 1ª execução de cada função +110..+440 ciclos, depois exata |
| DBGMCU_IDCODE / flash | 0x410 / 64 KB (C8) | 0x20030410 / 128 KB |

A família mais provável é **CKS32F103/CS32F103** (tabela do *Bluepill
Diagnostics*; ver `tmp/research/board-identity.md`). **Ação pendente do
autor: conferir a marcação do chip.** Consequência metodológica: a "bancada"
é *esta placa*; onde ela diverge do manual, o relatório compara o Renode com
**as duas referências** (manual ST e placa) e diz qual é qual. O núcleo é um
Cortex-M3 legítimo — os tempos de CPU batem com a TRM da ARM ciclo a ciclo —
então as conclusões de S1/S2/S4 sobre o núcleo valem para qualquer Cortex-M3
r2p0 a 0 WS; as de periféricos (S3, partes do S2) são da placa.

## 6. Reprodutibilidade

    nix develop
    scripts/fidelity.py build s1a s1b s2a s2b s3a s3b s4a s4b
    scripts/fidelity.py gate
    scripts/fidelity.py campaign --name v1        # HW + Renode + análise
    python3 -m unittest discover -s tests -p 'test_fidelity_v2.py'

Cada run guarda `manifest.json` (sha256 do ELF, digest das fontes, revisão
jj, configuração, tempos), `snapshot.bin` (somente leitura) e os logs. A
análise (`data/fidelity/v1/analysis/*.md|json`) e os traces do Perfetto
(`*.perfetto.json`, abrir em ui.perfetto.dev) são regeneráveis a partir dos
snapshots.

## 7. Referências (verificadas nesta sessão)

- ARM. *Cortex-M3 Technical Reference Manual*, r2p0, DDI 0337G, 2008. Tab.
  18-1 (pp. 18-3..18-5), §18.3 (pp. 18-7..18-8), §5.5–5.7 (pp. 5-13..5-15).
  PDF em `tmp/research/src/` (Zotero `7WLXBF6T` está **sem anexo** — sugerido
  anexar).
- STMICROELECTRONICS. *RM0008* rev. 21, 2021 (Zotero `N7JVRKFW`): §3.3.3
  p. 54; §15.3.1 p. 368; §15.4.5 pp. 410–411; §27.3.2 pp. 791–793; §27.3.3
  pp. 794–796; §27.6.1 pp. 818–819.
- STMICROELECTRONICS. *PM0056* rev. 7, 2024 (Zotero `IZMAAGNW`): §2.1.3
  (BASEPRI) p. 21; §2.3.6 p. 36; §2.3.7 p. 37; §4.3.9 pp. 126–127.
- HENNESSY, J. L.; PATTERSON, D. A. *Computer Architecture: A Quantitative
  Approach*. 6. ed. Morgan Kaufmann, 2019 (Zotero `7KNR6VY7`), §1.9 pp. 52–54.
- SARGENT, R. G. An Introduction to Verification and Validation of
  Simulation Models. *WSC 2013*, pp. 321–327, doi:10.1109/WSC.2013.6721430
  (PDF externo; **não está no Zotero**).
- Renode 1.17.0 — código-fonte fixado: `renode-infrastructure@066a7f13`
  (`BaseCPU.cs`, `NVIC.cs`, `STM32_Timer.cs`, `STM32_UART.cs`, `UARTHub.cs`,
  `DWT.cs`) e `tlib@167decf9`; notas em `tmp/research/renode-*.md`.
- YIU, J. *A Beginner's Guide on Interrupt Latency…* Arm Community, 2016
  (Zotero `9AEDRTIS`) — contexto; o número primário é o da DDI0337G.
