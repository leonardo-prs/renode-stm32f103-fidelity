# S1B — cargas de aplicação em C (-O2)

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | sim | `5a74a8463e8d` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `5a74a8463e8d` | upkzpxpvszmy 5c51a3cc973a |
| rn-m100-q1us | 2 | sim | `5a74a8463e8d` | upkzpxpvszmy 5c51a3cc973a |
| rn-m7-q1us | 2 | sim | `5a74a8463e8d` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q125ns | 2 | sim | `5a74a8463e8d` | upkzpxpvszmy 5c51a3cc973a |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| assinatura das cargas = oráculo do host | hw | 630/630 |
| assinatura das cargas = oráculo do host | rn-m8-q1us | 189/189 |
| assinatura das cargas = oráculo do host | rn-m100-q1us | 126/126 |
| assinatura das cargas = oráculo do host | rn-m7-q1us | 126/126 |
| assinatura das cargas = oráculo do host | rn-m8-q125ns | 126/126 |

## Tempo por carga (trials quentes 1..8; mesmo dado de entrada por trial)

*Unidade: HW: ciclos; Renode: ticks DWT; erro = (RN − HW)/HW*

| carga | hw mediana | rn-m8-q1us mediana | rn-m100-q1us mediana | rn-m7-q1us mediana | rn-m8-q125ns mediana | erro rn-m8-q1us % | erro rn-m100-q1us % | erro rn-m7-q1us % | erro rn-m8-q125ns % | CPI efetivo (HW/RN8) |
|---|---|---|---|---|---|---|---|---|---|---|
| crc32 | 15639 | 11534.5 | 923 | 13180 | 11533 | -26.25 | -94.1 | -15.72 | -26.25 | 1.36 |
| isort | 11697 | 9153.5 | 732 | 10456 | 9150 | -21.74 | -93.74 | -10.59 | -21.77 | 1.28 |
| matmul | 5873 | 3795.5 | 304 | 4332 | 3791 | -35.37 | -94.82 | -26.24 | -35.45 | 1.55 |
| fir | 19872 | 11536.5 | 923 | 13184 | 11534 | -41.95 | -95.36 | -33.66 | -41.96 | 1.72 |
| memcpy | 1823 | 1047.5 | 84 | 1192 | 1045 | -42.54 | -95.39 | -34.61 | -42.68 | 1.74 |
| isqrt | 16172.5 | 7853 | 628 | 8972 | 7850 | -51.45 | -96.12 | -44.53 | -51.47 | 2.06 |
| empty | 8 | 9 | 0.5 | 8 | 4 | 12.5 | -93.75 | 0 | -50 | 0.9 |
