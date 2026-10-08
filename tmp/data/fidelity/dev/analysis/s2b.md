# S2B — semântica de eventos TIM2 → NVIC

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 1 | sim | `1b072ccb5de2` | uklklnxsvlom 4e891fe91a00 |
| rn-m8-q1us | 1 | sim | `1b072ccb5de2` | uklklnxsvlom 4e891fe91a00 |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| uif_no_uie.uif = 1 | hw | 1/1 |
| uif_no_uie.uif = 1 | rn-m8-q1us | 1/1 |
| uif_no_uie.nvic_pending = 0 | hw | 1/1 |
| uif_no_uie.nvic_pending = 0 | rn-m8-q1us | 1/1 |
| coalesce.pending_after_run = 1 | hw | 1/1 |
| coalesce.pending_after_run = 1 | rn-m8-q1us | 1/1 |
| coalesce.isr_entries = 1 | hw | 1/1 |
| coalesce.isr_entries = 1 | rn-m8-q1us | 1/1 |
| clear_both.isr_entries = 0 | hw | 1/1 |
| clear_both.isr_entries = 0 | rn-m8-q1us | 1/1 |
| stale_pending.isr_entries = 1 | hw | 1/1 |
| stale_pending.isr_entries = 1 | rn-m8-q1us | 1/1 |
| stale_pending.spurious = 1 | hw | 1/1 |
| stale_pending.spurious = 1 | rn-m8-q1us | 1/1 |
| late_clear_dsb.spurious = 0 | hw | 1/1 |
| late_clear_dsb.spurious = 0 | rn-m8-q1us | 1/1 |
| psc_buffered.write_to_update = 500 | hw | 1/1 |
| psc_buffered.write_to_update = 500 | rn-m8-q1us | 0/1 |
| psc_buffered.next_period = 2000 | hw | 1/1 |
| psc_buffered.next_period = 2000 | rn-m8-q1us | 1/1 |
| ug_uif.uif_after_ug = 1 | hw | 1/1 |
| ug_uif.uif_after_ug = 1 | rn-m8-q1us | 0/1 |
| arr_preload.write_to_update = 500 | hw | 1/1 |
| arr_preload.write_to_update = 500 | rn-m8-q1us | 1/1 |
| arr_preload.next_period = 2000 | hw | 1/1 |
| arr_preload.next_period = 2000 | rn-m8-q1us | 1/1 |
| late_clear_rb.spurious = 0 | hw | 1/1 |
| late_clear_rb.spurious = 0 | rn-m8-q1us | 1/1 |

## Semântica TIM2/NVIC (trial 2 — quente)

*Unidade: valores de registrador/contagens; tempos em ciclos/ticks*

| condição | campo | esperado (manual) | referência | hw | hw ✓ | rn-m8-q1us | rn-m8-q1us ✓ |
|---|---|---|---|---|---|---|---|
| uif_no_uie | uif | 1 | RM0008 §15.4.5 UIF setado por overflow independente de UIE | 1 | sim | 1 | sim |
| uif_no_uie | nvic_pending | 0 | sem UIE não há pedido de IRQ | 0 | sim | 0 | sim |
| coalesce | uif | — | observação | 1 | — | 1 | — |
| coalesce | pending_after_run | 1 | PM0056 §4.3 ISPR | 1 | sim | 1 | sim |
| coalesce | pending_at_enable | — | observação | 1 | — | 1 | — |
| coalesce | isr_entries | 1 | NVIC: pendência única (coalescência de 5 eventos) | 1 | sim | 1 | sim |
| coalesce | first_sr | — | observação | 31 | — | 1 | — |
| coalesce | spurious | — | observação | 0 | — | 0 | — |
| clear_both | uif | — | observação | 1 | — | 1 | — |
| clear_both | pending_after_run | — | observação | 1 | — | 1 | — |
| clear_both | pending_at_enable | — | observação | 0 | — | 0 | — |
| clear_both | isr_entries | 0 | UIF e ICPR limpos antes de habilitar | 0 | sim | 0 | sim |
| clear_both | first_sr | — | observação | 65535 | — | 65535 | — |
| clear_both | spurious | — | observação | 0 | — | 0 | — |
| stale_pending | uif | — | observação | 1 | — | 1 | — |
| stale_pending | pending_after_run | — | observação | 1 | — | 1 | — |
| stale_pending | pending_at_enable | — | observação | 1 | — | 1 | — |
| stale_pending | isr_entries | 1 | pendência do NVIC é latched (PM0056 §2.3.9) | 1 | sim | 1 | sim |
| stale_pending | first_sr | — | observação | 0 | — | 0 | — |
| stale_pending | spurious | 1 | entra com UIF já limpo | 1 | sim | 1 | sim |
| late_clear | isr_entries | — | observação | 16 | — | 16 | — |
| late_clear | spurious | — | observação | 0 | — | 0 | — |
| late_clear | ppre1 | — | observação | 0 | — | 0 | — |
| late_clear_apb2 | isr_entries | — | observação | 31 | — | 16 | — |
| late_clear_apb2 | spurious | — | observação | 15 | — | 0 | — |
| late_clear_apb2 | ppre1 | — | observação | 4 | — | 0 | — |
| late_clear_dsb | isr_entries | — | observação | 16 | — | 16 | — |
| late_clear_dsb | spurious | 0 | DSB após a escrita (ARM AN321) | 0 | sim | 0 | sim |
| late_clear_dsb | ppre1 | — | observação | 4 | — | 0 | — |
| psc_buffered | base_period | — | observação | 996 | — | 1000 | — |
| psc_buffered | write_to_update | 500 | RM0008 §15.3.1: PSC bufferizado, vale no próximo update | 500 | sim | 992 | NÃO |
| psc_buffered | next_period | 2000 | PSC=1 → 2× período | 2001 | sim | 2000 | sim |
| psc_buffered | ref_to_write | — | observação | 499 | — | 496 | — |
| ug_uif | uif_before | — | observação | 0 | — | 0 | — |
| ug_uif | uif_after_ug | 1 | RM0008 §15.4.6 EGR.UG gera evento de update (URS=0) | 1 | sim | 0 | NÃO |
| ug_uif | cnt_after_ug | — | observação | 0 | — | 0 | — |
| arr_preload | base_period | — | observação | 996 | — | 1008 | — |
| arr_preload | write_to_update | 500 | RM0008 §15.3.1: ARR com ARPE=1 vale no próximo update | 500 | sim | 498 | sim |
| arr_preload | next_period | 2000 | ARR=1999 | 2001 | sim | 2006 | sim |
| arr_preload | ref_to_write | — | observação | 499 | — | 496 | — |
| late_clear_rb | isr_entries | — | observação | 16 | — | 16 | — |
| late_clear_rb | spurious | 0 | leitura de volta força a escrita pela ponte APB | 0 | sim | 0 | sim |
| late_clear_rb | ppre1 | — | observação | 4 | — | 0 | — |

## Notas

- late_clear*: corrida física entre a escrita no SR pela ponte APB e o retorno de exceção; o resultado no HW depende da razão de clock do APB1 e do layout exato do código.
