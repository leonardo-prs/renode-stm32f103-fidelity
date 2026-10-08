# S3B — temporização de quadro da USART1

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | sim | `f5e034831df6` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `f5e034831df6` | upkzpxpvszmy cc5508a3a25c |
| rn-m8-q1us-nodelay | 2 | sim | `f5e034831df6` | upkzpxpvszmy cc5508a3a25c |
| rn-m100-q1us | 2 | sim | `f5e034831df6` | upkzpxpvszmy cc5508a3a25c |
| rn-m7-q1us | 2 | sim | `f5e034831df6` | upkzpxpvszmy cc5508a3a25c |
| rn-m7-q1us-nodelay | 2 | sim | `f5e034831df6` | upkzpxpvszmy cc5508a3a25c |
| rn-m8-q125ns | 2 | sim | `f5e034831df6` | upkzpxpvszmy cc5508a3a25c |

## Byte isolado: instante de cada flag após escrever DR (amostras 1..31)

*Unidade: ciclos/ticks; 1 quadro 8N1 @ BRR 69 = 690*

| métrica | teórico | hw | rn-m8-q1us | rn-m8-q1us-nodelay | rn-m100-q1us | rn-m7-q1us | rn-m7-q1us-nodelay | rn-m8-q125ns |
|---|---|---|---|---|---|---|---|---|
| t_txe | ≤ 69 (1 bit) | 66 (37..66) | 0 (0..8) | 0 (0..0) | 0 (0..0) | 0 (0..8) | 0 (0..8) | 3 (3..3) |
| t_tc | 690 | 743 (738..743) | 0 (0..8) | 0 (0..0) | 0 (0..0) | 0 (0..8) | 0 (0..8) | 3 (3..3) |
| t_rxne | ≈ 690 − ½ bit | 768 (738..768) | 1390 (1390..1397) | 704 (704..704) | 1382 (1382..1384) | 1392 (1392..1400) | 712 (712..712) | 1391 (1391..1391) |
| t_idle | ≈ 1380 | 1405 (1379..1406) | 2080 (2080..2088) | 1398 (1398..1398) | 2072 (2072..2074) | 2080 (2080..2088) | 1392 (1392..1400) | 2078 (2078..2078) |

## Rajada de 16 bytes e vazão

*Unidade: ciclos/ticks*

| ambiente | intervalo RXNE med (faixa) | TC final 8 bytes (med) | teórico TC 8 bytes | bytes corretos |
|---|---|---|---|---|
| hw | 685 (673..714) | 5585 | 5520 | 640/640 |
| rn-m8-q1us | 690 (680..699) | 78 | 5520 | 192/192 |
| rn-m8-q1us-nodelay | 694 (679..700) | 78 | 5520 | 128/128 |
| rn-m100-q1us | 690 (689..691) | 7 | 5520 | 128/128 |
| rn-m7-q1us | 688 (680..704) | 88 | 5520 | 128/128 |
| rn-m7-q1us-nodelay | 688 (688..696) | 88 | 5520 | 128/128 |
| rn-m8-q125ns | 694 (685..694) | 78 | 5520 | 128/128 |
