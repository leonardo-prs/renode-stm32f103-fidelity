# S3B — temporização de quadro da USART1

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `41649238d2e6` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us | 1 | sim | `41649238d2e6` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us-nodelay | 1 | sim | `41649238d2e6` | uklklnxsvlom 4e891fe91a00 |

## Byte isolado: instante de cada flag após escrever DR (amostras 1..31)

*Unidade: ciclos/ticks; 1 quadro 8N1 @ BRR 69 = 690*

| métrica | teórico | hw | rn-m8-q1us | rn-m8-q1us-nodelay |
|---|---|---|---|---|
| t_txe | ≤ 69 (1 bit) | 66 (37..66) | 0 (0..8) | 0 (0..0) |
| t_tc | 690 | 743 (738..743) | 0 (0..8) | 0 (0..0) |
| t_rxne | ≈ 690 − ½ bit | 768 (738..768) | 1390 (1390..1397) | 704 (704..704) |
| t_idle | ≈ 1380 | 1405 (1379..1406) | 2080 (2080..2088) | 1398 (1398..1398) |

## Rajada de 16 bytes e vazão

*Unidade: ciclos/ticks*

| ambiente | intervalo RXNE med (faixa) | TC final 8 bytes (med) | teórico TC 8 bytes | bytes corretos |
|---|---|---|---|---|
| hw | 685 (673..714) | 5585 | 5520 | 64/64 |
| rn-m8-q1us | 690 (680..699) | 78 | 5520 | 64/64 |
| rn-m8-q1us-nodelay | 694 (679..700) | 78 | 5520 | 64/64 |
