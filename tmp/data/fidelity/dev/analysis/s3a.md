# S3A — USART1 em loopback: integridade e flags

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `d8f5e8f90db8` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us | 1 | sim | `d8f5e8f90db8` | uklklnxsvlom 4e891fe91a00 |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| ping_pong.received = 32 | hw | 1/1 |
| ping_pong.received = 32 | rn-m8-q1us | 1/1 |
| ping_pong.mismatches = 0 | hw | 1/1 |
| ping_pong.mismatches = 0 | rn-m8-q1us | 1/1 |
| full_duplex.received = 64 | hw | 1/1 |
| full_duplex.received = 64 | rn-m8-q1us | 1/1 |
| full_duplex.mismatches = 0 | hw | 1/1 |
| full_duplex.mismatches = 0 | rn-m8-q1us | 1/1 |
| full_duplex.tx_ahead_max = 2 | hw | 1/1 |
| full_duplex.tx_ahead_max = 2 | rn-m8-q1us | 0/1 |
| overrun.sr_after_burst = 248 | hw | 0/1 |
| overrun.sr_after_burst = 248 | rn-m8-q1us | 0/1 |
| overrun.drained_more = 0 | hw | 0/1 |
| overrun.drained_more = 0 | rn-m8-q1us | 0/1 |
| rxne_irq.received = 32 | hw | 1/1 |
| rxne_irq.received = 32 | rn-m8-q1us | 0/1 |
| rxne_irq.stranded_after = 0 | hw | 1/1 |
| rxne_irq.stranded_after = 0 | rn-m8-q1us | 0/1 |
| txe_irq.received = 32 | hw | 1/1 |
| txe_irq.received = 32 | rn-m8-q1us | 1/1 |
| idle.idle_seen = 1 | hw | 1/1 |
| idle.idle_seen = 1 | rn-m8-q1us | 1/1 |
| tc.tc_right_after_write = 0 | hw | 1/1 |
| tc.tc_right_after_write = 0 | rn-m8-q1us | 0/1 |
| tc.tc_after_2_frames = 1 | hw | 1/1 |
| tc.tc_after_2_frames = 1 | rn-m8-q1us | 1/1 |
| te_off.rx_seen = 0 | hw | 0/1 |
| te_off.rx_seen = 0 | rn-m8-q1us | 0/1 |

## USART1 em loopback: integridade e semântica de flags (trial 2)

*Unidade: contagens / valores de SR (hex em decimal)*

| condição | campo | esperado (manual) | referência | hw | rn-m8-q1us | hw ✓ | rn-m8-q1us ✓ |
|---|---|---|---|---|---|---|---|
| context | brr | — | observação | 69 | 69 | — | — |
| context | cr1 | — | observação | 8204 | 8204 | — | — |
| context | cr2 | — | observação | 0 | 0 | — | — |
| context | cr3 | — | observação | 0 | 0 | — | — |
| ping_pong | received | 32 | loopback | 32 | 32 | sim | sim |
| ping_pong | mismatches | 0 |  | 0 | 0 | sim | sim |
| ping_pong | timeouts | — | observação | 0 | 0 | — | — |
| full_duplex | received | 64 |  | 64 | 64 | sim | sim |
| full_duplex | mismatches | 0 |  | 0 | 0 | sim | sim |
| full_duplex | tx_ahead_max | 2 | RM0008 §27.3.2: TDR + registrador de deslocamento (≤2 + 1 em trânsito) | 3 | 63 | sim | NÃO |
| full_duplex | ore_seen | — | observação | 0 | 0 | — | — |
| full_duplex | sent | — | observação | 64 | 64 | — | — |
| overrun | sr_after_burst | 248 | RM0008 §27.3.3: ORE (bit 3) setado no 2º byte | 240 | 240 | NÃO | NÃO |
| overrun | dr_byte_index | — | observação | 0 | 0 | — | — |
| overrun | sr_after_dr | — | observação | 224 | 224 | — | — |
| overrun | drained_more | 0 | RM0008 §27.3.3: só o RDR antigo sobrevive; bytes seguintes perdidos | 3 | 3 | NÃO | NÃO |
| overrun | dr_value | — | observação | 196 | 196 | — | — |
| overrun | drained_in_order | — | observação | 3 | 3 | — | — |
| rxne_irq | received | 32 |  | 32 | 3 | sim | NÃO |
| rxne_irq | mismatches | — | observação | 0 | 0 | — | — |
| rxne_irq | isr_entries | — | observação | 32 | 3 | — | — |
| rxne_irq | stranded_after | 0 | IRQ de nível re-pende enquanto RXNE=1 | 0 | 29 | sim | NÃO |
| rxne_irq | nvic_pending_after | — | observação | 0 | 0 | — | — |
| txe_irq | received | 32 |  | 32 | 32 | sim | sim |
| txe_irq | mismatches | — | observação | 0 | 0 | — | — |
| txe_irq | isr_entries | — | observação | 32 | 32 | — | — |
| txe_irq | tx_by_isr | — | observação | 32 | 32 | — | — |
| idle | rxne_seen | — | observação | 1 | 1 | — | — |
| idle | idle_seen | 1 | RM0008 §27.6.1 IDLE | 1 | 1 | sim | sim |
| idle | sr_before | — | observação | 208 | 208 | — | — |
| idle | sr_after | — | observação | 192 | 192 | — | — |
| tc | tc_after_clear | — | observação | 0 | 0 | — | — |
| tc | tc_right_after_write | 0 | RM0008 §27.3.2: TC só ao fim do quadro | 0 | 1 | sim | NÃO |
| tc | tc_after_2_frames | 1 |  | 1 | 1 | sim | sim |
| te_off | rx_seen | 0 | RM0008 §27.3.2: sem TE não há transmissão | 1 | 1 | NÃO | NÃO |
| te_off | byte | — | observação | 0 | 65 | — | — |

## Notas

- A coluna 'esperado' é o STM32F103 do RM0008. A placa da bancada diverge em overrun (bufferiza ≥4 bytes sem ORE): evidência de clone — ver relatório S3.
