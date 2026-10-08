# S2 — Timer → IRQ (firmwares s2a, s2b)

*Relatório intermediário. Metodologia comum: `00-metodologia.md`. Dados:
`data/fidelity/v1/{s2a,s2b}/`, análise `data/fidelity/v1/analysis/s2{a,b}.md`.*

## 1. Pergunta

Para uma interrupção periódica de timer (TIM2, 1 kHz), o Renode reproduz
(a) a **latência** evento → ISR, (b) a **razão entre trabalho da CPU e
tempo dos periféricos**, e (c) a **semântica** de flags/pendência que o
firmware observa?

## 2. Fundamentação

- DDI0337G §5.5, p. 5-13: 12 ciclos do pedido à 1ª instrução da ISR; Tab.
  18-1 nota e: DIV "interruptible (abandoned/restarted)"; §18.3, p. 18-8:
  LDM/STM interrompidas continuam.
- RM0008 §15.3.1, p. 368: PSC "buffered. The new prescaler ratio is taken
  into account at the next update event"; ARR com ARPE idem. §15.4.5,
  pp. 410–411: UIF setado no overflow e "when CNT is reinitialized by
  software using the UG bit … if URS=0".
- PM0056 §4.3.9, pp. 126–127: pendência latched; IRQ de nível re-pende no
  retorno se ainda ativa; ICPR.
- Renode 1.17: TIM conta tempo virtual (CNT por `SyncTime`); PSC aplicado
  na escrita; UG só seta UIF com UIE; CCxIF só com CCxIE
  (`tmp/research/renode-periph-models.md`).

## 3. Desenho

**s2a**: TIM2 com **PSC = 0, ARR = 7999** → update a cada 8000 ciclos e CNT
a 8 MHz; a 1ª leitura da ISR é `TIM2->CNT` = ticks desde o evento =
**latência medida por um periférico** (resolução 1 ciclo; o gate confirma 5
instruções antes da leitura). O MAIN executa, por condição, um laço em asm
(8×ADDS, 8×UDIV lento, 8×LDM — `src/s2/spin.S`), WFI (com DBGMCU_CR como o
depurador deixa e com DBG_SLEEP limpo pelo firmware) ou uma janela PRIMASK
que segura o evento até CNT ≥ 200. 64 IRQs por condição; a ISR também
amostra o contador do laço → **iterações de fundo por período**.

**s2b**: 11 testes de registrador, 2 trials (o 1º sofre o efeito de 1ª
execução em flash), cada um com valor esperado do manual.

## 4. Resultados

### 4.1 Latência (s2a, amostras 1..63; a 1ª à parte)

| condição do MAIN | HW (ciclos) | Renode nominal (ticks) |
|---|---|---|
| 8×ADDS / 8×UDIV / 8×LDM / WFI / WFI sem DBG_SLEEP | **22 constante** (jitter 0) | 1..5 |
| PRIMASK até CNT ≥ 200 | 230..233 (≈ 30 após liberar) | 207..217 (≈ 7..17) |
| 1ª IRQ após reset (ALU) | 466 (efeito de 1ª execução) | 1 |

O HW confirma a DDI0337G: UDIV abandonada e LDM continuada **não** somam
latência; 22 = 12 (entrada) + ~10 (5 instruções do prólogo, incluindo PUSH
de 3 registradores e leitura APB). O Renode cobra só as instruções do
prólogo, e com resolução grosseira dentro do bloco traduzido (1..5).

### 4.2 Razão CPU/periférico (s2a)

| laço de fundo | instr/iter | ciclos/iter (TRM) | HW iter/período | Renode nominal | Renode/HW |
|---|---|---|---|---|---|
| 8×ADDS | 14 | 17 | 467 | 569 | 1,22 |
| 8×UDIV | 14 | 105 | 75 | 569 | **7,59** |
| 8×LDM | 14 | 49 | 162 | 569 | 3,51 |

No Renode, um período de 1 ms comporta **o mesmo trabalho** para qualquer
classe (569 iterações = 8000 ÷ 14 instruções, menos a ISR); no HW o
trabalho segue o CPI. A previsão pela TRM (8000 ÷ ciclos/iter) explica o HW
(470, 76, 163) — e a razão Renode/HW é o CPI do laço. **Consequência
prática:** um firmware cuja carga cabe no período no Renode pode estourar o
período no HW por um fator igual ao seu CPI (até 7,6× com divisões).

### 4.3 Semântica (s2b, trial 2)

| teste | esperado (manual) | HW | Renode |
|---|---|---|---|
| UIF sem UIE; sem pedido ao NVIC | 1 / 0 | 1 / 0 | 1 / 0 |
| coalescência (5 updates com IRQ desabilitada) | 1 entrada | 1 | 1 |
| UIF e ICPR limpos antes de habilitar | 0 entradas | 0 | 0 |
| só UIF limpo (pendência latched) | 1 entrada, UIF = 0 | 1 | 1 |
| ARR com ARPE no meio do período | próximo update (≈500), depois 2000 | 500 / 2001 | 498 / 2006 |
| **PSC no meio do período** | próximo update (≈500) | **500** | **992** (imediato) |
| **UG com UIE = 0 → UIF** | 1 | **1** | **0** |
| **SR na 1ª entrada (CCxIF sem CCxIE)** | 0x1F (CC1..4IF setados) | **0x1F** | **0x01** |
| **APB1 /2 (RCC_CFGR.PPRE1)** | lido de volta = 4 | 4 | **0** (RCC não modelado) |
| limpar UIF como último acesso, APB1 /2 | (corrida) | **15 ISR espúrias / 16** | 0 |
| idem + DSB / + leitura de volta | 0 | 0 / 0 | 0 / 0 |

A "ISR dupla" é um fenômeno físico conhecido: a escrita que limpa a flag
atravessa a ponte APB e a linha de IRQ ainda está alta quando a exceção
retorna; a ISR re-entra com UIF = 0. Ela depende da razão de clock do APB e
do layout exato do código (numa build anterior, até APB1 /1 dobrava e DSB
não bastava) — o Renode nunca a produz, porque a escrita é instantânea.

## 5. Interpretação

1. **Período do timer:** fiel (8000 nos dois; o timer conta tempo virtual).
2. **Latência:** não fiel por construção (0 vs 12 ciclos de entrada); a
   diferença é constante no HW (22, jitter zero) — previsível, mas não
   modelada.
3. **Razão CPU/periférico:** é o efeito de maior impacto prático; segue
   T_HW/T_RN = CPI. Nenhum MIPS único corrige laços com CPI 1,2 e 7,5.
4. **Semântica:** núcleo NVIC fiel; o modelo de timer diverge em PSC
   bufferizado, UG/UIF, CCxIF sem CCxIE; RCC ausente; corridas de bus
   inexistentes.

## 6. Limitações

- Latência medida até a 1ª leitura de CNT (5 instruções de prólogo):
  comparações são relativas a esse ponto fixo, igual nos dois ambientes.
- WFI: o HW não mostrou custo de despertar visível a 8 MHz (22 = 22); não
  se testou STOP/STANDBY.
- A ISR dupla é sensível ao binário; o número exato (15/16) vale para este ELF.
