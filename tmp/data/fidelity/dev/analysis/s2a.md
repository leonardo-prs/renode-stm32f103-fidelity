# S2A — latência de IRQ periódica e razão CPU/periférico

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `6102427d0ed2` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us | 1 | sim | `6102427d0ed2` | uklklnxsvlom 4e891fe91a00 |

## Latência TIM2 update → 1ª leitura de CNT na ISR (amostras 1..63)

*Unidade: ticks do TIM2 (= ciclos HCLK no HW; tempo virtual no Renode)*

| condição | hw lat. mín/med/máx | hw 1ª IRQ | hw período med (faixa) | rn-m8-q1us lat. mín/med/máx | rn-m8-q1us 1ª IRQ | rn-m8-q1us período med (faixa) |
|---|---|---|---|---|---|---|
| alu | 22/22/22 | 466 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) |
| div | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) |
| ldm | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) |
| wfi | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) |
| masked | 230/233/233 | 233 | 8000 (7997..8003) | 207/211/217 | 209 | 7999 (7993..8008) |
| wfi_nodbg | 22/22/22 | 22 | 8000 (8000..8000) | 1/5/5 | 1 | 8000 (7993..8000) |

## Trabalho do laço de fundo por período de 8000 ciclos

*Unidade: iterações (TRM: ciclos/iteração esperados no HW)*

| condição | TRM ciclos/iter | instr/iter | hw iter/período | rn-m8-q1us iter/período | rn-m8-q1us/HW |
|---|---|---|---|---|---|
| alu | 17 | 14 | 467 | 569 | 1.22 |
| div | 105 | 14 | 75 | 569 | 7.59 |
| ldm | 49 | 14 | 162 | 569 | 3.51 |
| wfi | — | — | — | — | — |
| masked | — | — | — | — | — |
| wfi_nodbg | — | — | — | — | — |
