# S1B — cargas de aplicação em C (-O2)

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `3b31a2ebb9bd` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us | 1 | sim | `3b31a2ebb9bd` | uklklnxsvlom 4e891fe91a00 |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| assinatura das cargas = oráculo do host | hw | 63/63 |
| assinatura das cargas = oráculo do host | rn-m8-q1us | 63/63 |

## Tempo por carga (trials quentes 1..8; mesmo dado de entrada por trial)

*Unidade: HW: ciclos; Renode: ticks DWT; erro = (RN − HW)/HW*

| carga | hw mediana | rn-m8-q1us mediana | erro rn-m8-q1us % | CPI efetivo (HW/RN8) |
|---|---|---|---|---|
| crc32 | 15634 | 11532 | -26.24 | 1.36 |
| isort | 11694 | 9151 | -21.75 | 1.28 |
| matmul | 5868 | 3791 | -35.4 | 1.55 |
| fir | 19867 | 11536 | -41.93 | 1.72 |
| memcpy | 1819 | 1045.5 | -42.52 | 1.74 |
| isqrt | 16169.5 | 7851.5 | -51.45 | 2.06 |
| empty | 5 | 4 | -20 | 1.25 |
