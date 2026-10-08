# S4B — late-arrival × preempção × sequencial (TIM1 UP/CC1)

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | sim | `176ba97a1c0f` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `176ba97a1c0f` | upkzpxpvszmy cc5508a3a25c |
| hw-free | 3 | sim | `176ba97a1c0f` | upkzpxpvszmy 5c51a3cc973a |
| rn-m100-q1us | 2 | sim | `176ba97a1c0f` | upkzpxpvszmy cc5508a3a25c |
| rn-m7-q1us | 2 | sim | `176ba97a1c0f` | upkzpxpvszmy cc5508a3a25c |
| rn-m8-q125ns | 2 | sim | `176ba97a1c0f` | upkzpxpvszmy cc5508a3a25c |

## Regiões da corrida UP(L) × CC1(H) com defasagem Δ

*Unidade: ciclos/ticks*

| ambiente | regiões | encadeamento H→L (late) | latência H (CNT−Δ) na preempção |
|---|---|---|---|
| hw | Δ≥0: late-arrival/arbitragem → Δ≥9: preempção → Δ≥200: sequencial | 30 | 18..21 |
| rn-m8-q1us | Δ≥0: H não entrou → Δ≥1: preempção → Δ≥175: sequencial | — | 0..3 |
| hw-free | Δ≥0: late-arrival/arbitragem → Δ≥9: preempção → Δ≥200: sequencial | 30 | 18..21 |
| rn-m100-q1us | Δ≥0: H não entrou → Δ≥1: preempção → Δ≥175: sequencial | — | 0..0 |
| rn-m7-q1us | Δ≥0: H não entrou → Δ≥1: preempção → Δ≥175: sequencial | — | 0..7 |
| rn-m8-q125ns | Δ≥0: H não entrou → Δ≥1: preempção → Δ≥175: sequencial | — | 3..3 |

## Classificação por Δ



| Δ | hw | rn-m8-q1us | hw-free | rn-m100-q1us | rn-m7-q1us | rn-m8-q125ns |
|---|---|---|---|---|---|---|
| 0 | late-arrival/arbitragem | H não entrou | late-arrival/arbitragem | H não entrou | H não entrou | H não entrou |
| 1 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 2 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 3 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 4 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 5 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 6 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 7 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 8 | late-arrival/arbitragem | preempção | late-arrival/arbitragem | preempção | preempção | preempção |
| 9 | preempção | preempção | preempção | preempção | preempção | preempção |
| 10 | preempção | preempção | preempção | preempção | preempção | preempção |
| 11 | preempção | preempção | preempção | preempção | preempção | preempção |
| 12 | preempção | preempção | preempção | preempção | preempção | preempção |
| 13 | preempção | preempção | preempção | preempção | preempção | preempção |
| 14 | preempção | preempção | preempção | preempção | preempção | preempção |
| 15 | preempção | preempção | preempção | preempção | preempção | preempção |
| 16 | preempção | preempção | preempção | preempção | preempção | preempção |
| 17 | preempção | preempção | preempção | preempção | preempção | preempção |
| 18 | preempção | preempção | preempção | preempção | preempção | preempção |
| 19 | preempção | preempção | preempção | preempção | preempção | preempção |
| 20 | preempção | preempção | preempção | preempção | preempção | preempção |
| 21 | preempção | preempção | preempção | preempção | preempção | preempção |
| 22 | preempção | preempção | preempção | preempção | preempção | preempção |
| 23 | preempção | preempção | preempção | preempção | preempção | preempção |
| 24 | preempção | preempção | preempção | preempção | preempção | preempção |
| 25 | preempção | preempção | preempção | preempção | preempção | preempção |
| 26 | preempção | preempção | preempção | preempção | preempção | preempção |
| 27 | preempção | preempção | preempção | preempção | preempção | preempção |
| 28 | preempção | preempção | preempção | preempção | preempção | preempção |
| 29 | preempção | preempção | preempção | preempção | preempção | preempção |
| 30 | preempção | preempção | preempção | preempção | preempção | preempção |
| 31 | preempção | preempção | preempção | preempção | preempção | preempção |
| 32 | preempção | preempção | preempção | preempção | preempção | preempção |
| 33 | preempção | preempção | preempção | preempção | preempção | preempção |
| 34 | preempção | preempção | preempção | preempção | preempção | preempção |
| 35 | preempção | preempção | preempção | preempção | preempção | preempção |
| 36 | preempção | preempção | preempção | preempção | preempção | preempção |
| 37 | preempção | preempção | preempção | preempção | preempção | preempção |
| 38 | preempção | preempção | preempção | preempção | preempção | preempção |
| 39 | preempção | preempção | preempção | preempção | preempção | preempção |
| 40 | preempção | preempção | preempção | preempção | preempção | preempção |
| 50 | preempção | preempção | preempção | preempção | preempção | preempção |
| 75 | preempção | preempção | preempção | preempção | preempção | preempção |
| 100 | preempção | preempção | preempção | preempção | preempção | preempção |
| 125 | preempção | preempção | preempção | preempção | preempção | preempção |
| 150 | preempção | preempção | preempção | preempção | preempção | preempção |
| 175 | preempção | sequencial | preempção | sequencial | sequencial | sequencial |
| 200 | sequencial | sequencial | sequencial | sequencial | sequencial | sequencial |
| 250 | sequencial | sequencial | sequencial | sequencial | sequencial | sequencial |
| 300 | sequencial | sequencial | sequencial | sequencial | sequencial | sequencial |
| 400 | sequencial | sequencial | sequencial | sequencial | sequencial | sequencial |

## Notas

- Discriminante: L ativo (IABR) na entrada de H. DDI0337G §5.7: late-arrival só enquanto a 1ª instrução de L não entrou em Execute.
