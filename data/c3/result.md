# C3 — GPIO and EXTI

| Data | ELF | ELF SHA-256 | Renode | reps | other |
|---|---|---|---|---|---|
| `renode/c3_01_output_registers` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `renode/c3_02_input_pull` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `renode/c3_03_driven_line` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `renode/c3_04_exti_routing` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `renode/c3_05_exti_pending` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `renode/c3_06_input_capture` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `board/c3_06_input_capture` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | — | 3 |  |
| `renode/c3_07_event_response` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | Renode v1.17.0 | 3 |  |
| `board/c3_07_event_response` | `build/c3/firmware.elf` | `9e321ec3a0d5891bfbd554b86e05f138ee2691167488ffa5c192675959edc2c1` | — | 3 |  |

| Case | Oracle / part | Verdict |
|---|---|---|
| C3-01 — output registers and input isolation (`c3_01_output_registers`) | document | **DIVERGES** |
| C3-02 — internal pull on a free pin (`c3_02_input_pull`) | document | **DIVERGES** |
| C3-03 — driven line between pins (`c3_03_driven_line`) | document | **EQUAL** |
| C3-04 — AFIO routing and EXTI0 edges (`c3_04_exti_routing`) | document | **EQUAL** |
| C3-05 — EXTI pending and lost events (`c3_05_exti_pending`) | document | **EQUAL** |
| C3-06 — input capture and filter (`c3_06_input_capture`) | (a) capture, board | **EQUAL** |
| C3-06 — input capture and filter (`c3_06_input_capture`) | (b) filter, board | **DIVERGES** |
| C3-07 — response time to an event (`c3_07_event_response`) | event to handler, by the compare interrupt, board | **DIVERGES** |
| C3-07 — response time to an event (`c3_07_event_response`) | event to handler, by the pin, board | **DIVERGES** |
| C3-07 — response time to an event (`c3_07_event_response`) | pin to pin, board | **DIVERGES** |

## C3-01 — output registers and input isolation (`c3_01_output_registers`), document: DIVERGES

- 8/11 items equal to the document
- ODR = PA3 | PA4: ODR read back: observed 24, document 24
- ODR = PA3: ODR read back: observed 8, document 8
- BSRR sets PA4: PA3 stays: ODR read back: observed 24, document 24
- BRR resets PA3: PA4 stays: ODR read back: observed 16, document 16
- BSRR sets and resets PA4: BS has priority: ODR read back: observed 16, document 16
- PA4 output, 0 → 1 via ODR: IDR4 before, after: observed (0, 0), document (0, 1)  ← differs
- PA4 output, 1 → 0 via ODR: IDR4 before, after: observed (1, 1), document (1, 0)  ← differs
- PA4 output, 0 → 1 via BSRR: IDR4 before, after: observed (0, 1), document (0, 1)
- PA4 output, 1 → 0 via BRR: IDR4 before, after: observed (1, 0), document (1, 0)
- PA6 input, writing 1 by ODR: IDR0 before, after: observed (0, 1), document (0, 0)  ← differs
- PA6 input, writing 1 by BSRR/BRR: IDR0 before, after: observed (0, 0), document (0, 0)

## C3-02 — internal pull on a free pin (`c3_02_input_pull`), document: DIVERGES

- 0/4 items equal to the document
- pull-down → pull-up via ODR: IDR4 before, after: observed (0, 0), document (0, 1)  ← differs
- pull-up → pull-down via ODR: IDR4 before, after: observed (0, 0), document (1, 0)  ← differs
- pull-down → pull-up via BSRR: IDR4 before, after: observed (0, 0), document (0, 1)  ← differs
- pull-up → pull-down via BRR: IDR4 before, after: observed (0, 0), document (1, 0)  ← differs

## C3-03 — driven line between pins (`c3_03_driven_line`), document: EQUAL

- 6/6 items equal to the document
- L2 PA6 → PA0, rise: (source, destination) before, after: observed ((0, 0), (1, 1)), document ((0, 0), (1, 1))
- L2 PA6 → PA0, fall: (source, destination) before, after: observed ((1, 1), (0, 0)), document ((1, 1), (0, 0))
- L3 PA7 → PA1, rise: (source, destination) before, after: observed ((0, 0), (1, 1)), document ((0, 0), (1, 1))
- L3 PA7 → PA1, fall: (source, destination) before, after: observed ((1, 1), (0, 0)), document ((1, 1), (0, 0))
- L4 PA5 → PB0, rise: (source, destination) before, after: observed ((0, 0), (1, 1)), document ((0, 0), (1, 1))
- L4 PA5 → PB0, fall: (source, destination) before, after: observed ((1, 1), (0, 0)), document ((1, 1), (0, 0))

## C3-04 — AFIO routing and EXTI0 edges (`c3_04_exti_routing`), document: EQUAL

- 6/6 items equal to the document
- port A, rising, edge on PA0: entries (rise, fall): observed (1, 0), document (1, 0)
- port A, falling, edge on PA0: entries (rise, fall): observed (0, 1), document (0, 1)
- port A, both, edge on PA0: entries (rise, fall): observed (1, 1), document (1, 1)
- port A, both, edge on PB0: entries (rise, fall): observed (0, 0), document (0, 0)
- port B, both, edge on PB0: entries (rise, fall): observed (1, 1), document (1, 1)
- port B, both, edge on PA0: entries (rise, fall): observed (0, 0), document (0, 0)

## C3-05 — EXTI pending and lost events (`c3_05_exti_pending`), document: EQUAL

- 12/12 items equal to the document
- masked line: EXTI_PR after the rise: observed 0, document 0
- masked line: entries once unmasked: observed 0, document 0
- NVIC disabled: EXTI_PR after the rise: observed 1, document 1
- NVIC disabled: entries before the enable: observed 0, document 0
- NVIC disabled: entries after the enable: observed 1, document 1
- pulse over: EXTI_PR: observed 1, document 1
- pulse over: IDR0: observed 0, document 0
- pulse over: entries after the enable: observed 1, document 1
- two rises with the NVIC disabled: entries after the enable: observed 1, document 1
- rise in the handler before the clear: entries: observed 1, document 1
- rise in the handler after the clear: entries: observed 2, document 2
- edge with the core in WFI: entries at each wake-up: observed [1, 1, 1, 1, 1, 1, 1, 1], document [1, 1, 1, 1, 1, 1, 1, 1]
- compare to the first read, core in WFI (observed, not judged): [1] ticks

## C3-06 — input capture and filter (`c3_06_input_capture`), (a) capture, board: EQUAL

- 8/8 items equal to the board
- TI1 by L2, rise → fall, near: CC1IF | CC2IF: Renode 0x6, board 0x6
- TI1 by L2, rise → fall, near: (CCR2 − CCR1) − DWT difference (ticks): Renode 0, board 0
- TI1 by L2, rise → fall, far: CC1IF | CC2IF: Renode 0x6, board 0x6
- TI1 by L2, rise → fall, far: (CCR2 − CCR1) − DWT difference (ticks): Renode 0, board 0
- TI1 by L2 → TI2 by L3, rise → rise, near: CC1IF | CC2IF: Renode 0x6, board 0x6
- TI1 by L2 → TI2 by L3, rise → rise, near: (CCR2 − CCR1) − DWT difference (ticks): Renode 0, board 0
- TI1 by L2 → TI2 by L3, rise → rise, far: CC1IF | CC2IF: Renode 0x6, board 0x6
- TI1 by L2 → TI2 by L3, rise → rise, far: (CCR2 − CCR1) − DWT difference (ticks): Renode 0, board 0

## C3-06 — input capture and filter (`c3_06_input_capture`), (b) filter, board: DIVERGES

- 3/4 items equal to the board
- IC1F = 0, short (2 stores): CC1IF: Renode 1, board 1
- IC1F = 0, long (24 NOPs): CC1IF: Renode 1, board 1
- IC1F = 3, short (2 stores): CC1IF: Renode 1, board 0  ← differs
- IC1F = 3, long (24 NOPs): CC1IF: Renode 1, board 1

## C3-07 — response time to an event (`c3_07_event_response`), event to handler, by the compare interrupt, board: DIVERGES

- board 18–18 ticks; Renode ['1']

## C3-07 — response time to an event (`c3_07_event_response`), event to handler, by the pin, board: DIVERGES

- board 21–21 ticks; Renode ['1']
- the path through the pin adds: board 3 ticks; Renode 0 ticks

## C3-07 — response time to an event (`c3_07_event_response`), pin to pin, board: DIVERGES

- board 24–24 ticks; Renode ['2']
