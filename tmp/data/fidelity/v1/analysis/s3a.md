# S3A — USART1 em loopback: integridade e flags

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | NÃO (4 conjuntos) | `ec482f9df6dc` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `ec482f9df6dc` | upkzpxpvszmy cc5508a3a25c |
| rn-m8-q1us-nodelay | 2 | sim | `ec482f9df6dc` | upkzpxpvszmy cc5508a3a25c |
| rn-m100-q1us | 2 | sim | `ec482f9df6dc` | upkzpxpvszmy cc5508a3a25c |
| rn-m7-q1us | 2 | sim | `ec482f9df6dc` | upkzpxpvszmy cc5508a3a25c |
| rn-m7-q1us-nodelay | 2 | sim | `ec482f9df6dc` | upkzpxpvszmy cc5508a3a25c |
| rn-m8-q125ns | 2 | sim | `ec482f9df6dc` | upkzpxpvszmy cc5508a3a25c |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| ping_pong.received = 32 | hw | 1/1 |
| ping_pong.received = 32 | rn-m8-q1us | 1/1 |
| ping_pong.received = 32 | rn-m8-q1us-nodelay | 1/1 |
| ping_pong.received = 32 | rn-m100-q1us | 1/1 |
| ping_pong.received = 32 | rn-m7-q1us | 1/1 |
| ping_pong.received = 32 | rn-m7-q1us-nodelay | 1/1 |
| ping_pong.received = 32 | rn-m8-q125ns | 1/1 |
| ping_pong.mismatches = 0 | hw | 1/1 |
| ping_pong.mismatches = 0 | rn-m8-q1us | 1/1 |
| ping_pong.mismatches = 0 | rn-m8-q1us-nodelay | 1/1 |
| ping_pong.mismatches = 0 | rn-m100-q1us | 1/1 |
| ping_pong.mismatches = 0 | rn-m7-q1us | 1/1 |
| ping_pong.mismatches = 0 | rn-m7-q1us-nodelay | 1/1 |
| ping_pong.mismatches = 0 | rn-m8-q125ns | 1/1 |
| full_duplex.received = 64 | hw | 1/1 |
| full_duplex.received = 64 | rn-m8-q1us | 1/1 |
| full_duplex.received = 64 | rn-m8-q1us-nodelay | 1/1 |
| full_duplex.received = 64 | rn-m100-q1us | 1/1 |
| full_duplex.received = 64 | rn-m7-q1us | 1/1 |
| full_duplex.received = 64 | rn-m7-q1us-nodelay | 1/1 |
| full_duplex.received = 64 | rn-m8-q125ns | 1/1 |
| full_duplex.mismatches = 0 | hw | 1/1 |
| full_duplex.mismatches = 0 | rn-m8-q1us | 1/1 |
| full_duplex.mismatches = 0 | rn-m8-q1us-nodelay | 1/1 |
| full_duplex.mismatches = 0 | rn-m100-q1us | 1/1 |
| full_duplex.mismatches = 0 | rn-m7-q1us | 1/1 |
| full_duplex.mismatches = 0 | rn-m7-q1us-nodelay | 1/1 |
| full_duplex.mismatches = 0 | rn-m8-q125ns | 1/1 |
| full_duplex.tx_ahead_max = 2 | hw | 1/1 |
| full_duplex.tx_ahead_max = 2 | rn-m8-q1us | 0/1 |
| full_duplex.tx_ahead_max = 2 | rn-m8-q1us-nodelay | 0/1 |
| full_duplex.tx_ahead_max = 2 | rn-m100-q1us | 0/1 |
| full_duplex.tx_ahead_max = 2 | rn-m7-q1us | 0/1 |
| full_duplex.tx_ahead_max = 2 | rn-m7-q1us-nodelay | 0/1 |
| full_duplex.tx_ahead_max = 2 | rn-m8-q125ns | 0/1 |
| overrun.sr_after_burst = 248 | hw | 0/1 |
| overrun.sr_after_burst = 248 | rn-m8-q1us | 0/1 |
| overrun.sr_after_burst = 248 | rn-m8-q1us-nodelay | 0/1 |
| overrun.sr_after_burst = 248 | rn-m100-q1us | 0/1 |
| overrun.sr_after_burst = 248 | rn-m7-q1us | 0/1 |
| overrun.sr_after_burst = 248 | rn-m7-q1us-nodelay | 0/1 |
| overrun.sr_after_burst = 248 | rn-m8-q125ns | 0/1 |
| overrun.drained_more = 0 | hw | 0/1 |
| overrun.drained_more = 0 | rn-m8-q1us | 0/1 |
| overrun.drained_more = 0 | rn-m8-q1us-nodelay | 0/1 |
| overrun.drained_more = 0 | rn-m100-q1us | 0/1 |
| overrun.drained_more = 0 | rn-m7-q1us | 0/1 |
| overrun.drained_more = 0 | rn-m7-q1us-nodelay | 0/1 |
| overrun.drained_more = 0 | rn-m8-q125ns | 0/1 |
| rxne_irq.received = 32 | hw | 1/1 |
| rxne_irq.received = 32 | rn-m8-q1us | 0/1 |
| rxne_irq.received = 32 | rn-m8-q1us-nodelay | 0/1 |
| rxne_irq.received = 32 | rn-m100-q1us | 0/1 |
| rxne_irq.received = 32 | rn-m7-q1us | 0/1 |
| rxne_irq.received = 32 | rn-m7-q1us-nodelay | 0/1 |
| rxne_irq.received = 32 | rn-m8-q125ns | 0/1 |
| rxne_irq.stranded_after = 0 | hw | 1/1 |
| rxne_irq.stranded_after = 0 | rn-m8-q1us | 0/1 |
| rxne_irq.stranded_after = 0 | rn-m8-q1us-nodelay | 0/1 |
| rxne_irq.stranded_after = 0 | rn-m100-q1us | 0/1 |
| rxne_irq.stranded_after = 0 | rn-m7-q1us | 0/1 |
| rxne_irq.stranded_after = 0 | rn-m7-q1us-nodelay | 0/1 |
| rxne_irq.stranded_after = 0 | rn-m8-q125ns | 0/1 |
| txe_irq.received = 32 | hw | 1/1 |
| txe_irq.received = 32 | rn-m8-q1us | 1/1 |
| txe_irq.received = 32 | rn-m8-q1us-nodelay | 1/1 |
| txe_irq.received = 32 | rn-m100-q1us | 1/1 |
| txe_irq.received = 32 | rn-m7-q1us | 1/1 |
| txe_irq.received = 32 | rn-m7-q1us-nodelay | 1/1 |
| txe_irq.received = 32 | rn-m8-q125ns | 1/1 |
| idle.idle_seen = 1 | hw | 1/1 |
| idle.idle_seen = 1 | rn-m8-q1us | 1/1 |
| idle.idle_seen = 1 | rn-m8-q1us-nodelay | 1/1 |
| idle.idle_seen = 1 | rn-m100-q1us | 1/1 |
| idle.idle_seen = 1 | rn-m7-q1us | 1/1 |
| idle.idle_seen = 1 | rn-m7-q1us-nodelay | 1/1 |
| idle.idle_seen = 1 | rn-m8-q125ns | 1/1 |
| tc.tc_right_after_write = 0 | hw | 1/1 |
| tc.tc_right_after_write = 0 | rn-m8-q1us | 0/1 |
| tc.tc_right_after_write = 0 | rn-m8-q1us-nodelay | 0/1 |
| tc.tc_right_after_write = 0 | rn-m100-q1us | 0/1 |
| tc.tc_right_after_write = 0 | rn-m7-q1us | 0/1 |
| tc.tc_right_after_write = 0 | rn-m7-q1us-nodelay | 0/1 |
| tc.tc_right_after_write = 0 | rn-m8-q125ns | 0/1 |
| tc.tc_after_2_frames = 1 | hw | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m8-q1us | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m8-q1us-nodelay | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m100-q1us | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m7-q1us | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m7-q1us-nodelay | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m8-q125ns | 1/1 |
| te_off.data_transmitted = 0 | hw | 1/1 |
| te_off.data_transmitted = 0 | rn-m8-q1us | 0/1 |
| te_off.data_transmitted = 0 | rn-m8-q1us-nodelay | 0/1 |
| te_off.data_transmitted = 0 | rn-m100-q1us | 0/1 |
| te_off.data_transmitted = 0 | rn-m7-q1us | 0/1 |
| te_off.data_transmitted = 0 | rn-m7-q1us-nodelay | 0/1 |
| te_off.data_transmitted = 0 | rn-m8-q125ns | 0/1 |

## USART1 em loopback: integridade e semântica de flags (trial 2)

*Unidade: contagens / valores de SR (hex em decimal)*

| condição | campo | esperado (manual) | referência | hw | rn-m8-q1us | rn-m8-q1us-nodelay | rn-m100-q1us | rn-m7-q1us | rn-m7-q1us-nodelay | rn-m8-q125ns | hw ✓ | rn-m8-q1us ✓ | rn-m8-q1us-nodelay ✓ | rn-m100-q1us ✓ | rn-m7-q1us ✓ | rn-m7-q1us-nodelay ✓ | rn-m8-q125ns ✓ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| context | brr | — | observação | 69 | 69 | 69 | 69 | 69 | 69 | 69 | — | — | — | — | — | — | — |
| context | cr1 | — | observação | 8204 | 8204 | 8204 | 8204 | 8204 | 8204 | 8204 | — | — | — | — | — | — | — |
| context | cr2 | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| context | cr3 | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| ping_pong | received | 32 | loopback | 32 | 32 | 32 | 32 | 32 | 32 | 32 | sim | sim | sim | sim | sim | sim | sim |
| ping_pong | mismatches | 0 |  | 0 | 0 | 0 | 0 | 0 | 0 | 0 | sim | sim | sim | sim | sim | sim | sim |
| ping_pong | timeouts | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| full_duplex | received | 64 |  | 64 | 64 | 64 | 64 | 64 | 64 | 64 | sim | sim | sim | sim | sim | sim | sim |
| full_duplex | mismatches | 0 |  | 0 | 0 | 0 | 0 | 0 | 0 | 0 | sim | sim | sim | sim | sim | sim | sim |
| full_duplex | tx_ahead_max | 2 | RM0008 §27.3.2: TDR + registrador de deslocamento (≤2 + 1 em trânsito) | 3 | 63 | 62 | 64 | 63 | 62 | 63 | sim | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| full_duplex | ore_seen | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| full_duplex | sent | — | observação | 64 | 64 | 64 | 64 | 64 | 64 | 64 | — | — | — | — | — | — | — |
| overrun | sr_after_burst | 248 | RM0008 §27.3.3: ORE (bit 3) setado no 2º byte | 240/496 | 240 | 240 | 240 | 240 | 240 | 240 | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| overrun | dr_byte_index | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| overrun | sr_after_dr | — | observação | 224/480 | 224 | 224 | 224 | 224 | 224 | 224 | — | — | — | — | — | — | — |
| overrun | drained_more | 0 | RM0008 §27.3.3: só o RDR antigo sobrevive; bytes seguintes perdidos | 3 | 3 | 3 | 3 | 3 | 3 | 3 | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| overrun | dr_value | — | observação | 196 | 196 | 196 | 196 | 196 | 196 | 196 | — | — | — | — | — | — | — |
| overrun | drained_in_order | — | observação | 3 | 3 | 3 | 3 | 3 | 3 | 3 | — | — | — | — | — | — | — |
| rxne_irq | received | 32 |  | 32 | 3 | 4 | 3 | 3 | 4 | 3 | sim | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| rxne_irq | mismatches | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| rxne_irq | isr_entries | — | observação | 32 | 3 | 4 | 3 | 3 | 4 | 3 | — | — | — | — | — | — | — |
| rxne_irq | stranded_after | 0 | IRQ de nível re-pende enquanto RXNE=1 | 0 | 29 | 28 | 29 | 29 | 28 | 29 | sim | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| rxne_irq | nvic_pending_after | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| txe_irq | received | 32 |  | 32 | 32 | 32 | 32 | 32 | 32 | 32 | sim | sim | sim | sim | sim | sim | sim |
| txe_irq | mismatches | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| txe_irq | isr_entries | — | observação | 32 | 32 | 32 | 32 | 32 | 32 | 32 | — | — | — | — | — | — | — |
| txe_irq | tx_by_isr | — | observação | 32 | 32 | 32 | 32 | 32 | 32 | 32 | — | — | — | — | — | — | — |
| idle | rxne_seen | — | observação | 1 | 1 | 1 | 1 | 1 | 1 | 1 | — | — | — | — | — | — | — |
| idle | idle_seen | 1 | RM0008 §27.6.1 IDLE | 1 | 1 | 1 | 1 | 1 | 1 | 1 | sim | sim | sim | sim | sim | sim | sim |
| idle | sr_before | — | observação | 208/464 | 208 | 208 | 208 | 208 | 208 | 208 | — | — | — | — | — | — | — |
| idle | sr_after | — | observação | 192/448 | 192 | 192 | 192 | 192 | 192 | 192 | — | — | — | — | — | — | — |
| tc | tc_after_clear | — | observação | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — | — | — | — | — | — |
| tc | tc_right_after_write | 0 | RM0008 §27.3.2: TC só ao fim do quadro | 0 | 1 | 1 | 1 | 1 | 1 | 1 | sim | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| tc | tc_after_2_frames | 1 |  | 1 | 1 | 1 | 1 | 1 | 1 | 1 | sim | sim | sim | sim | sim | sim | sim |
| te_off | data_transmitted | 0 | RM0008 §27.3.2: sem TE o dado não é transmitido | 0 | 1 | 1 | 1 | 1 | 1 | 1 | sim | NÃO | NÃO | NÃO | NÃO | NÃO | NÃO |
| te_off | rx_seen | — | observação | 0/1 | 1 | 1 | 1 | 1 | 1 | 1 | — | — | — | — | — | — | — |
| te_off | byte | — | observação | 0/256 | 65 | 65 | 65 | 65 | 65 | 65 | — | — | — | — | — | — | — |
| te_off | sr | — | observação | 0..290 | 224 | 224 | 224 | 224 | 224 | 224 | — | — | — | — | — | — | — |

## Notas

- A coluna 'esperado' é o STM32F103 do RM0008. A placa da bancada diverge em overrun (bufferiza ≥4 bytes sem ORE): evidência de clone — ver relatório S3.
