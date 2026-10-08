# S2A — latência de IRQ periódica e razão CPU/periférico

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | sim | `1f64dbb9fade` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `1f64dbb9fade` | upkzpxpvszmy 5c51a3cc973a |
| hw-free | 3 | sim | `1f64dbb9fade` | upkzpxpvszmy 5c51a3cc973a |
| rn-m100-q1us | 2 | sim | `1f64dbb9fade` | upkzpxpvszmy 5c51a3cc973a |
| rn-m7-q1us | 2 | sim | `1f64dbb9fade` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q125ns | 2 | sim | `1f64dbb9fade` | upkzpxpvszmy 5c51a3cc973a |

## Latência TIM2 update → 1ª leitura de CNT na ISR (amostras 1..63)

*Unidade: ticks do TIM2 (= ciclos HCLK no HW; tempo virtual no Renode)*

| condição | hw lat. mín/med/máx | hw 1ª IRQ | hw período med (faixa) | rn-m8-q1us lat. mín/med/máx | rn-m8-q1us 1ª IRQ | rn-m8-q1us período med (faixa) | hw-free lat. mín/med/máx | hw-free 1ª IRQ | hw-free período med (faixa) | rn-m100-q1us lat. mín/med/máx | rn-m100-q1us 1ª IRQ | rn-m100-q1us período med (faixa) | rn-m7-q1us lat. mín/med/máx | rn-m7-q1us 1ª IRQ | rn-m7-q1us período med (faixa) | rn-m8-q125ns lat. mín/med/máx | rn-m8-q125ns 1ª IRQ | rn-m8-q125ns período med (faixa) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alu | 22/22/22 | 466 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) | 22/22/22 | 466 | 8000 (8000..8000) | 0/0/0 | 0 | 7999 (7999..7999) | 0/4/7 | 1 | 8000 (7992..8000) | 5/5/5 | 5 | 7999 (7999..7999) |
| div | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) | 22/22/22 | 22 | 8000 (8000..8000) | 0/0/0 | 0 | 7999 (7998..8000) | 0/4/7 | 1 | 8000 (7992..8000) | 5/5/5 | 5 | 7999 (7999..7999) |
| ldm | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) | 22/22/22 | 22 | 8000 (8000..8000) | 0/0/0 | 0 | 7999 (7999..7999) | 0/4/7 | 1 | 8000 (7992..8000) | 5/5/5 | 5 | 7999 (7999..7999) |
| wfi | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) | 22/22/22 | 22 | 8000 (8000..8000) | 0/0/0 | 0 | 7999 (7999..7999) | 0/4/7 | 1 | 8000 (7992..8000) | 5/5/5 | 5 | 7999 (7999..7999) |
| masked | 230/233/233 | 233 | 8000 (7997..8003) | 207/211/217 | 209 | 7999 (7993..8008) | 230/233/233 | 233 | 8000 (7997..8003) | 200/200/200 | 200 | 7999 (7998..8000) | 208/212/215 | 209 | 8000 (7984..8000) | 211/211/211 | 211 | 7999 (7999..7999) |
| wfi_nodbg | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) | 22/22/22 | 22 | 8000 (8000..8000) | 0/0/0 | 0 | 7999 (7998..8000) | 0/4/7 | 1 | 8000 (7992..8000) | 5/5/5 | 5 | 7999 (7999..7999) |

## Trabalho do laço de fundo por período de 8000 ciclos

*Unidade: iterações (TRM: ciclos/iteração esperados no HW)*

| condição | TRM ciclos/iter | instr/iter | hw iter/período | rn-m8-q1us iter/período | hw-free iter/período | rn-m100-q1us iter/período | rn-m7-q1us iter/período | rn-m8-q125ns iter/período | rn-m8-q1us/HW | hw-free/HW | rn-m100-q1us/HW | rn-m7-q1us/HW | rn-m8-q125ns/HW |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alu | 17 | 14 | 467 | 569 | 467 | 7140 | 498 | 569 | 1.22 | 1 | 15.29 | 1.07 | 1.22 |
| div | 105 | 14 | 75 | 569 | 75 | 7140 | 498 | 569 | 7.59 | 1 | 95.2 | 6.64 | 7.59 |
| ldm | 49 | 14 | 162 | 569 | 162 | 7140 | 498 | 569 | 3.51 | 1 | 44.07 | 3.07 | 3.51 |
| wfi | — | — | — | — | — | — | — | — | — | — | — | — | — |
| masked | — | — | — | — | — | — | — | — | — | — | — | — | — |
| wfi_nodbg | — | — | — | — | — | — | — | — | — | — | — | — | — |
