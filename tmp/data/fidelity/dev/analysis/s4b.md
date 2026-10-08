# S4B — late-arrival × preempção × sequencial (TIM1 UP/CC1)

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `b44c07782b04` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us | 1 | sim | `b44c07782b04` | uklklnxsvlom 4e891fe91a00 |

## Regiões da corrida UP(L) × CC1(H) com defasagem Δ

*Unidade: ciclos/ticks*

| ambiente | regiões | encadeamento H→L (late) | latência H (CNT−Δ) na preempção |
|---|---|---|---|
| hw | Δ≥0: late-arrival/arbitragem → Δ≥9: preempção → Δ≥200: sequencial | 30 | 18..21 |
| rn-m8-q1us | Δ≥0: H não entrou → Δ≥1: preempção → Δ≥175: sequencial | — | 0..3 |

## Classificação por Δ



| Δ | hw | rn-m8-q1us |
|---|---|---|
| 0 | late-arrival/arbitragem | H não entrou |
| 1 | late-arrival/arbitragem | preempção |
| 2 | late-arrival/arbitragem | preempção |
| 3 | late-arrival/arbitragem | preempção |
| 4 | late-arrival/arbitragem | preempção |
| 5 | late-arrival/arbitragem | preempção |
| 6 | late-arrival/arbitragem | preempção |
| 7 | late-arrival/arbitragem | preempção |
| 8 | late-arrival/arbitragem | preempção |
| 9 | preempção | preempção |
| 10 | preempção | preempção |
| 11 | preempção | preempção |
| 12 | preempção | preempção |
| 13 | preempção | preempção |
| 14 | preempção | preempção |
| 15 | preempção | preempção |
| 16 | preempção | preempção |
| 17 | preempção | preempção |
| 18 | preempção | preempção |
| 19 | preempção | preempção |
| 20 | preempção | preempção |
| 21 | preempção | preempção |
| 22 | preempção | preempção |
| 23 | preempção | preempção |
| 24 | preempção | preempção |
| 25 | preempção | preempção |
| 26 | preempção | preempção |
| 27 | preempção | preempção |
| 28 | preempção | preempção |
| 29 | preempção | preempção |
| 30 | preempção | preempção |
| 31 | preempção | preempção |
| 32 | preempção | preempção |
| 33 | preempção | preempção |
| 34 | preempção | preempção |
| 35 | preempção | preempção |
| 36 | preempção | preempção |
| 37 | preempção | preempção |
| 38 | preempção | preempção |
| 39 | preempção | preempção |
| 40 | preempção | preempção |
| 50 | preempção | preempção |
| 75 | preempção | preempção |
| 100 | preempção | preempção |
| 125 | preempção | preempção |
| 150 | preempção | preempção |
| 175 | preempção | sequencial |
| 200 | sequencial | sequencial |
| 250 | sequencial | sequencial |
| 300 | sequencial | sequencial |
| 400 | sequencial | sequencial |

## Notas

- Discriminante: L ativo (IABR) na entrada de H. DDI0337G §5.7: late-arrival só enquanto a 1ª instrução de L não entrou em Execute.
