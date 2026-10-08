# Síntese — fidelidade do Renode 1.17 frente à bancada (campanha v1)

*Sessão autônoma 2026-10-07/08. Relatórios: [metodologia](00-metodologia.md),
[S1 núcleo](S1-nucleo.md), [S2 timer→IRQ](S2-timer-irq.md),
[S3 USART](S3-usart.md), [S4 NVIC](S4-nvic.md). Dados e tabelas geradas:
`data/fidelity/v1/analysis/` (`index.md`, `*.md`, `*.json`, `*.perfetto.json`).*

## Resposta à pergunta central

> Em quais cenários, e até que nível, o Renode é funcional e temporalmente
> equivalente à bancada?

**Funcionalmente**, o Renode é fiel no **núcleo** (todas as instruções
testadas, 100 % das assinaturas = oráculo) e nas **regras do NVIC** (ordem de
preempção/arbitragem idêntica em 11/11 casos). É **infiel em detalhes de
periféricos** que o firmware observa: flags do transmissor da USART (TXE, TC,
TE), re-pendência de IRQ de nível (recepção por interrupção perde 29 de 32
bytes), PSC bufferizado, UG→UIF, CCxIF sem CCxIE, compare com CCR = 0, RCC.

**Temporalmente**, o Renode é um modelo de **contagem de instruções**:
T_RN = IC / MIPS, para qualquer instrução e com entrada de exceção gratuita. O
HW segue a TRM da ARM ciclo a ciclo (CPI de 1,06 a 10,8 por classe). A
divergência é **sistemática e explicável** — razão HW/RN = CPI da carga — mas
**não é corrigível por um parâmetro global**: o melhor MIPS único possível
ainda erra ±23 % em seis cargas C reais; a política calibrada pré-declarada
(7 MIPS) erra −11 % a −45 %. Fenômenos que dependem da duração da entrada de
exceção (late-arrival, latência, janelas de corrida, ISR dupla por latência
de barramento) **não existem** no simulador. O que é fiel no tempo: o
**período dos timers** (tempo virtual exato) e o **ritmo de recepção** da
USART (≈ 690 ciclos/quadro) — desde que sem `AutoUpdateDelay`.

## Matriz de veredito

| cenário | aspecto | veredito | evidência-chave (HW × Renode 8 MIPS) |
|---|---|---|---|
| S1 núcleo | resultado das instruções | **fiel** | 126/126 e 63/63 assinaturas = oráculo |
| S1 núcleo | tempo por classe | **não fiel, previsível** | HW = TRM (19, 20, 35, 83, 195…); RN = 18 p/ todas |
| S1 núcleo | tempo de cargas reais | **não fiel, previsível** | CPI 1,28–2,06; erro −22 % a −52 % (7 MIPS: −11 % a −45 %) |
| S1 núcleo | 1ª execução em flash | **ausente no RN** | HW +110..+440 ciclos (placa) |
| S2 timer | período | **fiel** | 8000 × 8000 |
| S2 timer | latência | **não fiel (sem mecanismo)** | 22 constante × 1..5 |
| S2 timer | trabalho por período | **não fiel, = CPI** | razão 1,22 / 3,51 / 7,59 (ADDS/LDM/UDIV) |
| S2 timer | coalescência, pendência, ARPE | **fiel** | iguais |
| S2 timer | PSC, UG, CCxIF, RCC | **infiel (modelo)** | 500×992; 1×0; 0x1F×0x01; 4×0 |
| S2 timer | ISR dupla (APB1 /2) | **ausente no RN** | 15 espúrias × 0 |
| S3 USART | integridade (polling) | **fiel** | 32/32, 64/64 |
| S3 USART | recepção por IRQ | **defeito funcional** | 32 × 3 (29 presos) — PM0056 p. 126 |
| S3 USART | TXE/TC/TE | **infiel (modelo)** | adiant. 3×63; TC 0×1; TE=0 transmite |
| S3 USART | tempo de recepção | **fiel sem AutoUpdateDelay** | 768 × 704 (com o atraso: 1390) |
| S3 USART | tempo do transmissor | **ausente** | TC de 8 B: 5585 × 78 |
| S3 USART | overrun | **ambos ≠ RM0008** | placa bufferiza ≥4 B (clone); RN fila infinita |
| S4 NVIC | regras de prioridade | **fiel** | 11/11 ordens = PM0056 |
| S4 NVIC | tempos de entrada/encadeamento | **não fiel** | 37×16; 38×~21 |
| S4 NVIC | late-arrival | **ausente no RN** | HW Δ 0..8 × nenhum |
| S4 NVIC | compare CCR = 0 | **defeito funcional** | dispara × nunca |

## Defeitos/limitações do modelo Renode 1.17 identificados

1. `STM32_UART` + NVIC: IRQ de nível não re-pende (recepção por RXNEIE trava).
2. `STM32_UART`: TXE sempre 1; TC imediato; TE ignorado com UE = 1; RX em
   fila ilimitada (sem ORE).
3. `STM32_Timer`: PSC aplicado na escrita (sem buffer); UG só seta UIF com
   UIE; CCxIF só com CCxIE; compare em CCR = 0 não dispara.
4. RCC do F1 ausente (escritas em CFGR ignoradas).
5. tlib: sem custo de entrada/saída de exceção; empilhamento atômico (sem
   late-arrival); IRQ só em fronteira de bloco (jitter dependente do quantum).
6. `PerformanceInMips` truncado para inteiro.
7. CPUID 0x410FC231 (r0p1) — o Cortex-M3 da bancada é r2p0.

(Candidatos a *issues* upstream; ver código-fonte fixado em
`tmp/research/renode-*.md`.)

## Recomendações de configuração (para o texto do TCC)

- MIPS = 8 (hipótese nominal 1 instr./ciclo) e reportar o erro por CPI; não
  usar o padrão 100 para qualquer afirmação temporal.
- Quantum 125 ns reduz o jitter de leitura (latência RN constante = 5) sem
  mudar o tempo de CPU; custa ~4× em tempo de simulação.
- USART: `AutoUpdateDelay false` (o receptor já ritma 1 quadro/caractere).

## Pendências para o autor

1. **Conferir a marcação do chip da Blue Pill** (evidência forte de clone
   CKS32/CS32F103: UID zero, CPUID r2p0, USART com FIFO, efeito de 1ª
   execução). Se for clone, decidir: (a) manter e declarar a referência como
   "Blue Pill CKS32F103 com núcleo Cortex-M3 r2p0", ou (b) repetir a campanha
   numa placa com STM32F103 genuíno (o código roda sem mudança:
   `scripts/fidelity.py campaign --name v2`).
2. Anexar ao item Zotero `7WLXBF6T` o PDF da DDI0337G
   (`tmp/research/src/ddi0337g_cortex_m3_r2p0_trm.pdf`) e importar Sargent
   (2013), hoje fora do Zotero.
3. Mover a síntese e os relatórios para `tcc/` quando decidir (hoje em `tmp/`
   por decisão anterior).
