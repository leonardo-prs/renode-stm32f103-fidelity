# S4A — preempção × arbitragem no NVIC

| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |
|---|---|---|---|---|
| hw | 10 | sim | `a1184e021011` | upkzpxpvszmy 5c51a3cc973a |
| rn-m8-q1us | 3 | sim | `a1184e021011` | upkzpxpvszmy cc5508a3a25c |
| rn-m100-q1us | 2 | sim | `a1184e021011` | upkzpxpvszmy cc5508a3a25c |
| rn-m7-q1us | 2 | sim | `a1184e021011` | upkzpxpvszmy cc5508a3a25c |
| rn-m8-q125ns | 2 | sim | `a1184e021011` | upkzpxpvszmy cc5508a3a25c |

## Verificações funcionais

| verificação | ambiente | resultado |
|---|---|---|
| ordem preempt | hw | 1/1 |
| ordem preempt | rn-m8-q1us | 1/1 |
| ordem preempt | rn-m100-q1us | 1/1 |
| ordem preempt | rn-m7-q1us | 1/1 |
| ordem preempt | rn-m8-q125ns | 1/1 |
| ordem same_group_sub | hw | 1/1 |
| ordem same_group_sub | rn-m8-q1us | 1/1 |
| ordem same_group_sub | rn-m100-q1us | 1/1 |
| ordem same_group_sub | rn-m7-q1us | 1/1 |
| ordem same_group_sub | rn-m8-q125ns | 1/1 |
| ordem equal | hw | 1/1 |
| ordem equal | rn-m8-q1us | 1/1 |
| ordem equal | rn-m100-q1us | 1/1 |
| ordem equal | rn-m7-q1us | 1/1 |
| ordem equal | rn-m8-q125ns | 1/1 |
| ordem preempt_swapped | hw | 1/1 |
| ordem preempt_swapped | rn-m8-q1us | 1/1 |
| ordem preempt_swapped | rn-m100-q1us | 1/1 |
| ordem preempt_swapped | rn-m7-q1us | 1/1 |
| ordem preempt_swapped | rn-m8-q125ns | 1/1 |
| ordem lower_requested | hw | 1/1 |
| ordem lower_requested | rn-m8-q1us | 1/1 |
| ordem lower_requested | rn-m100-q1us | 1/1 |
| ordem lower_requested | rn-m7-q1us | 1/1 |
| ordem lower_requested | rn-m8-q125ns | 1/1 |
| ordem arb_group | hw | 1/1 |
| ordem arb_group | rn-m8-q1us | 1/1 |
| ordem arb_group | rn-m100-q1us | 1/1 |
| ordem arb_group | rn-m7-q1us | 1/1 |
| ordem arb_group | rn-m8-q125ns | 1/1 |
| ordem arb_sub | hw | 1/1 |
| ordem arb_sub | rn-m8-q1us | 1/1 |
| ordem arb_sub | rn-m100-q1us | 1/1 |
| ordem arb_sub | rn-m7-q1us | 1/1 |
| ordem arb_sub | rn-m8-q125ns | 1/1 |
| ordem arb_number | hw | 1/1 |
| ordem arb_number | rn-m8-q1us | 1/1 |
| ordem arb_number | rn-m100-q1us | 1/1 |
| ordem arb_number | rn-m7-q1us | 1/1 |
| ordem arb_number | rn-m8-q125ns | 1/1 |
| ordem arb_number_rev | hw | 1/1 |
| ordem arb_number_rev | rn-m8-q1us | 1/1 |
| ordem arb_number_rev | rn-m100-q1us | 1/1 |
| ordem arb_number_rev | rn-m7-q1us | 1/1 |
| ordem arb_number_rev | rn-m8-q125ns | 1/1 |
| ordem basepri | hw | 1/1 |
| ordem basepri | rn-m8-q1us | 1/1 |
| ordem basepri | rn-m100-q1us | 1/1 |
| ordem basepri | rn-m7-q1us | 1/1 |
| ordem basepri | rn-m8-q125ns | 1/1 |
| ordem self_repend | hw | 1/1 |
| ordem self_repend | rn-m8-q1us | 1/1 |
| ordem self_repend | rn-m100-q1us | 1/1 |
| ordem self_repend | rn-m7-q1us | 1/1 |
| ordem self_repend | rn-m8-q125ns | 1/1 |

## Ordem de eventos (contador de sequência atômico) e Δticks

*Unidade: Δticks: 1–5 pedido→H_ENTER; 6–9 saída do 1º → entrada do 2º; 10 TIM2 pendente sob BASEPRI; 11 nº de entradas TIM2*

| condição | esperado (PM0056) | hw ✓ | hw Δticks | rn-m8-q1us ✓ | rn-m8-q1us Δticks | rn-m100-q1us ✓ | rn-m100-q1us Δticks | rn-m7-q1us ✓ | rn-m7-q1us Δticks | rn-m8-q125ns ✓ | rn-m8-q125ns Δticks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| preempt | L_ENTER L_REQ H_ENTER H_EXIT L_RESUME L_EXIT | sim | 37 | sim | 16 | sim | 1 | sim | 24 | sim | 17 |
| same_group_sub | L_ENTER L_REQ L_RESUME L_EXIT H_ENTER H_EXIT | sim | 74 | sim | 42 | sim | 4 | sim | 48 | sim | 44 |
| equal | L_ENTER L_REQ L_RESUME L_EXIT H_ENTER H_EXIT | sim | 74 | sim | 42 | sim | 4 | sim | 48 | sim | 44 |
| preempt_swapped | L_ENTER L_REQ H_ENTER H_EXIT L_RESUME L_EXIT | sim | 37 | sim | 16 | sim | 2 | sim | 16 | sim | 17 |
| lower_requested | L_ENTER L_REQ L_RESUME L_EXIT H_ENTER H_EXIT | sim | 74 | sim | 42 | sim | 4 | sim | 48 | sim | 44 |
| arb_group | T3_ENTER T3_EXIT T2_ENTER T2_EXIT | sim | 38 | sim | 23 | sim | 5 | sim | 24 | sim | 22 |
| arb_sub | T3_ENTER T3_EXIT T2_ENTER T2_EXIT | sim | 38 | sim | 21 | sim | 2 | sim | 24 | sim | 22 |
| arb_number | T2_ENTER T2_EXIT T3_ENTER T3_EXIT | sim | 38 | sim | 23 | sim | 2 | sim | 24 | sim | 22 |
| arb_number_rev | T2_ENTER T2_EXIT T3_ENTER T3_EXIT | sim | 38 | sim | 19 | sim | 2 | sim | 24 | sim | 22 |
| basepri | T3_ENTER T3_EXIT BASEPRI_CLEARED T2_ENTER T2_EXIT | sim | 1 | sim | 1 | sim | 1 | sim | 1 | sim | 1 |
| self_repend | T2_ENTER T2_EXIT T3_ENTER T3_EXIT | sim | 2 | sim | 2 | sim | 2 | sim | 2 | sim | 2 |
