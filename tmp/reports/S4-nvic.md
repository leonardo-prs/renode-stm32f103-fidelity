# S4 — Preempção × arbitragem no NVIC (firmwares s4a, s4b)

*Relatório intermediário. Metodologia comum: `00-metodologia.md`. Dados:
`data/fidelity/v1/{s4a,s4b}/`, análise `data/fidelity/v1/analysis/s4{a,b}.md`.*

## 1. Pergunta

O Renode reproduz (a) **as regras arquiteturais** de prioridade do NVIC
Cortex-M3 — quem preempta quem, em que ordem pendentes são atendidas — e
(b) **a dinâmica temporal** que decide entre *late-arrival*, preempção e
execução sequencial?

## 2. Fundamentação

- PM0056 §2.3.6, p. 36: "Only the group priority determines preemption of
  interrupt exceptions"; mesma prioridade de grupo não preempta; entre
  pendentes de mesmo grupo decide a subprioridade, depois "the lowest IRQ
  number". §2.1.3, p. 21: BASEPRI impede a ativação de exceções de
  prioridade ≥ BASEPRI.
- PM0056 §2.3.7, p. 37: tail-chaining ("the stack pop is skipped") e
  late-arriving ("can accept a late arriving exception until the first
  instruction of the exception handler of the original exception enters the
  execute stage").
- ARM DDI0337G: entrada 12 ciclos (§5.5, Fig. 5-2, p. 5-13); tail-chain
  6 ciclos (§5.6, p. 5-14); late-arriving (§5.7, p. 5-15).
- Renode 1.17 (fonte fixada): `NVIC.cs` implementa PRIGROUP
  (`ApplyPriorityGrouping`), preempção só por prioridade de grupo
  (`FindPendingInterrupt`), desempate por número; o tlib reconhece IRQ apenas
  em fronteira de bloco traduzido, **não cobra ciclos de entrada/saída** e
  empilha atomicamente (`tmp/research/renode-nvic-tlib.md`). Predição: regras
  idênticas; tempos sem os 12/6 ciclos; **sem late-arrival**.

## 3. Desenho

**s4a** — IRQs TIM2 (nº 28) e TIM3 (nº 29) disparadas por software (ISPR),
sem periférico, para isolar o NVIC. AIRCR.PRIGROUP = 4 (3 bits de grupo + 1
de sub nos 4 bits do F1 — necessário para expressar "mesmo grupo, sub
diferente"). A ORDEM dos eventos vem de um contador de sequência atômico
(LDREX/STREX, `src/s4/seq.h`), não de timestamps — no Renode o DWT empata
dentro de um bloco traduzido. 11 condições × 2 trials; oráculo = regras do
PM0056 codificadas em `scripts/fidelity/oracles.py::s4a_expected`.
Observáveis extra: IPSR, ICSR, IABR (quem está ativo), ΔMSP (um quadro de
exceção a mais quando aninha).

**s4b** — Um timer (TIM1, PSC = 0) gera UPDATE (IRQ 25, L, baixa
prioridade) e COMPARE CC1 (IRQ 27, H, alta) separados por **Δ ciclos**
exatos (CCR1 = Δ). L fica 150 ciclos ocupado. Varredura Δ = 0..40, 50..400;
2 repetições + aquecimento. Discriminante: **L ativo (IABR) quando H entra**
— ativo → preempção; inativo e H antes de L → late-arrival/arbitragem; L
saiu antes → sequencial. Nenhuma saída de canal habilitada (o `.repl` liga
TIM1 CH2/CH3 a PA9/PA10, os pinos do loopback físico).

## 4. Resultados

### 4.1 Regras arquiteturais (s4a) — **concordância total**

| condição | esperado (PM0056) | HW | Renode |
|---|---|---|---|
| preempt (L g3 pende H g1) | L_ENTER L_REQ **H_ENTER H_EXIT** L_RESUME L_EXIT | = | = |
| same_group_sub (g1s1 → g1s0) | sem preempção, H após L | = | = |
| equal | sem preempção | = | = |
| preempt_swapped (L = TIM3) | aninha (prioridade, não nº) | = | = |
| lower_requested | H após L | = | = |
| arb_group (TIM2 g3, TIM3 g1) | TIM3 primeiro | = | = |
| arb_sub (g1s1 × g1s0) | TIM3 primeiro (sub ordena pendentes) | = | = |
| arb_number / _rev | TIM2 primeiro (menor nº), independe da ordem de pend | = | = |
| basepri (BASEPRI = g2) | TIM3 roda, TIM2 fica pendente até BASEPRI = 0 | = | = |
| self_repend | TIM2 roda 2× antes de TIM3 | = | = |

IPSR (44/45), IABR (bits 28/29) e ΔMSP = 40 B no aninhamento (quadro de 32 B
+ 8 B do prólogo do handler) idênticos. **O modelo de prioridades do NVIC do
Renode é fiel às regras do PM0056 em todos os casos testados.**

Tempo (mesmo s4a, campanha v1):

| intervalo | HW (ciclos) | Renode 8 MIPS | Renode 7 MIPS | Renode 100 MIPS | Renode 8 MIPS q125 ns |
|---|---|---|---|---|---|
| pedido (ISPR) → entrada de H aninhado | 37 | 16 | 24 | 1 | 17 |
| saída do 1º → entrada do 2º (arbitragem, tail-chain) | 38 | 19–23 | 24 | 2–5 | 22 |
| pedido → H após L (sem preempção) | 74 | 42 | 48 | 4 | 44 |

A diferença HW − Renode(8) (≈ 15–30 ciclos) é da ordem dos 12/6 ciclos de
entrada/tail-chain que o tlib não cobra, somados ao CPI > 1 dos
prólogos/epílogos. A ordem é idêntica em todas as configurações.

### 4.2 Corrida temporal (s4b) — **divergência qualitativa**

| região | HW (ciclos) | Renode nominal (ticks) |
|---|---|---|
| late-arrival / arbitragem (H entra com L inativo) | **Δ = 0..8** | **inexistente** |
| preempção (H aninha em L) | Δ = 9..175 | Δ = 1..150 |
| sequencial | Δ ≥ 200 | Δ ≥ 175 |
| Δ = 0 (CCR1 = 0, compare simultâneo ao update) | arbitragem: H primeiro | **compare nunca dispara** |
| encadeamento H→L no late-arrival | 30 ciclos | — |
| latência de H (CNT − Δ) na preempção | 18–21 ciclos | 0–3 ticks (7 MIPS: 0–7; 100 MIPS: 0; q125 ns: 3) |

O padrão é o mesmo em **todas** as configurações do Renode (8/7/100 MIPS,
quantum 1 µs/125 ns): nenhuma produz late-arrival, todas falham em Δ = 0.

A janela de late-arrival do HW (Δ ≤ 8, i.e. H chegando nos ~8 primeiros
ciclos dos 12 de entrada de L) é exatamente a prevista pela DDI0337G §5.7 /
PM0056 p. 37. No Renode, L já está ativo quando H é reconhecido mesmo com
Δ = 1: o empilhamento é instantâneo e não há janela.

O caso Δ = 0 expõe um defeito do modelo de timer: com CCR1 = 0 o
compare-match coincide com o update e o `STM32_Timer` não sinaliza CC1IF
(o HW sinaliza).

## 5. Interpretação

1. **Funcional (regras): fidelidade plena.** Firmware cuja correção depende
   de *quem preempta quem* e da *ordem de atendimento de pendentes* pode ser
   validado no Renode.
2. **Temporal: o Renode é um modelo de ordem, não de tempo de exceção.**
   Toda propriedade que depende da duração da entrada/saída de exceção (late-
   arrival, janelas de corrida entre IRQs próximas, latência) diverge — não
   por "imprecisão", mas por ausência de mecanismo (custo zero + empilhamento
   atômico). Isso não se corrige com MIPS: a janela é estrutural.
3. Testes que dependem de eventos coincidentes de timer (CCRx = 0) podem
   falhar *funcionalmente* no Renode.

## 6. Limitações

- IRQs software-pended (s4a) não exercitam o caminho periférico→NVIC; o s4b
  exercita, mas só para o TIM1.
- A fronteira exata (8/9) depende do caminho de sincronização timer→NVIC da
  placa (possível clone; o núcleo é Cortex-M3 r2p0 legítimo).
- Prioridades de grupo testadas: g1/g3 (3 bits de grupo); PRIGROUP só 4 em
  s4a e 3 (4:0) em s4b.
