# C1 — The core

| Data | ELF | ELF SHA-256 | Renode | reps | other |
|---|---|---|---|---|---|
| `renode/c1_01_arithmetic` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | Renode v1.17.0 | 3 |  |
| `board/c1_01_arithmetic` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | — | 3 |  |
| `renode/c1_02_conversions` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | Renode v1.17.0 | 3 |  |
| `board/c1_02_conversions` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | — | 3 |  |
| `renode/c1_03_memory` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | Renode v1.17.0 | 3 |  |
| `board/c1_03_memory` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | — | 3 |  |
| `renode/c1_04_timebase` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | Renode v1.17.0 | 3 |  |
| `board/c1_04_timebase` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | — | 3 |  |
| `renode/c1_05_instruction_cost` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | Renode v1.17.0 | 3 |  |
| `board/c1_05_instruction_cost` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | — | 3 |  |
| `renode/c1_06_exception_frame` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | Renode v1.17.0 | 3 |  |
| `board/c1_06_exception_frame` | `build/c1/firmware.elf` | `b3d25f1181e84183cf2ff7c586b2efdb09ec7b1422a9d30d87c91d354a79d5e4` | — | 3 |  |

| Case | Verdict (board oracle) |
|---|---|
| C1-01 — arithmetic and flags (`c1_01_arithmetic`) | **EQUAL** |
| C1-02 — conversions and comparisons (`c1_02_conversions`) | **EQUAL** |
| C1-03 — memory access and addressing (`c1_03_memory`) | **EQUAL** |
| C1-04 — DWT_CYCCNT timebase (`c1_04_timebase`) | **EQUAL** |
| C1-05 — instruction and bus cycle cost (`c1_05_instruction_cost`) | **DIVERGES** |
| C1-06 — exception frame and return (`c1_06_exception_frame`) | **DIVERGES** |

## C1-01 — arithmetic and flags (`c1_01_arithmetic`): EQUAL

- 3 runs in Renode
- 3 runs on the board
- 124/124 items equal to the board

## C1-02 — conversions and comparisons (`c1_02_conversions`): EQUAL

- 3 runs in Renode
- 3 runs on the board
- 50/50 items equal to the board

## C1-03 — memory access and addressing (`c1_03_memory`): EQUAL

- 3 runs in Renode
- 3 runs on the board
- 32/32 items equal to the board

## C1-04 — DWT_CYCCNT timebase (`c1_04_timebase`): EQUAL

- 3 runs in Renode
- 3 runs on the board
- 7/7 items equal to the board
- Renode (c) wait ≥ 1000: ΔDWT 1011, ΔTIM2_CNT 1011
- Renode (c) wait ≥ 50000: ΔDWT 50011, ΔTIM2_CNT 50011
- board (c) wait ≥ 1000: ΔDWT 1017, ΔTIM2_CNT 1017
- board (c) wait ≥ 50000: ΔDWT 50013, ΔTIM2_CNT 50013

## C1-05 — instruction and bus cycle cost (`c1_05_instruction_cost`): DIVERGES

Ticks per unit, (t32 − t16) / 16 of the 2nd execution: the mean over instructions 17 to 32, free of what the reads of DWT_CYCCNT add at the ends of the window.

| Class | Unit | Renode | Board | Equal |
|---|---|---|---|---|
| NOP | instruction | 1 | 1 | yes |
| taken B | branch | 1 | 2 | no |
| loop SUBS + BNE | iteration | 2 | 3 | no |
| LDR SRAM | instruction | 1 | 1 | yes |
| STR SRAM | instruction | 1 | 1 | yes |
| LDR.W SRAM, word-aligned | instruction | 1 | 1 | yes |
| LDR.W SRAM, halfword-aligned | instruction | 1 | 1.5 | no |
| LDR flash | instruction | 1 | 1.25 | no |
| LDR GPIOA_IDR (APB2) | instruction | 1 | 3 | no |
| STR GPIOA_BSRR (APB2) | instruction | 1 | 2 | no |
| LDR TIM2_CNT (APB1) | instruction | 1 | 3 | no |
| DSB | instruction | 1 | 1 | yes |
| ISB | instruction | 1 | 3 | no |
| UDIV ÷ 0 | instruction | 1 | 2 | no |
| UDIV largest quotient | instruction | 1 | 12 | no |
| UMULL small operands | instruction | 1 | 3 | no |
| UMULL largest operands | instruction | 1 | 5 | no |
| LDM 4 registers | instruction | 1 | 5 | no |
| PUSH + POP 4 registers | pair | 2 | 10 | no |
| LDR unaligned at +1 | instruction | 1 | 3 | no |
| LDR unaligned at +2 | instruction | 1 | 2 | no |

- 3 runs in Renode
- 3 runs on the board
- 6/86 items equal to the board
- differences:
-   taken B, N = 16, 1st execution (ticks): Renode 17, board 34
-   taken B, N = 16, 2nd execution (ticks): Renode 17, board 34
-   taken B, N = 32, 1st execution (ticks): Renode 33, board 66
-   taken B, N = 32, 2nd execution (ticks): Renode 33, board 66
-   loop SUBS + BNE, N = 16, 1st execution (ticks): Renode 33, board 49
-   loop SUBS + BNE, N = 16, 2nd execution (ticks): Renode 33, board 49
-   loop SUBS + BNE, N = 32, 1st execution (ticks): Renode 65, board 97
-   loop SUBS + BNE, N = 32, 2nd execution (ticks): Renode 65, board 97
-   LDR SRAM, N = 16, 1st execution (ticks): Renode 17, board 19
-   LDR SRAM, N = 16, 2nd execution (ticks): Renode 17, board 19
-   LDR SRAM, N = 32, 1st execution (ticks): Renode 33, board 35
-   LDR SRAM, N = 32, 2nd execution (ticks): Renode 33, board 35
-   STR SRAM, N = 16, 1st execution (ticks): Renode 17, board 19
-   STR SRAM, N = 16, 2nd execution (ticks): Renode 17, board 19
-   STR SRAM, N = 32, 1st execution (ticks): Renode 33, board 35
-   STR SRAM, N = 32, 2nd execution (ticks): Renode 33, board 35
-   LDR.W SRAM, word-aligned, N = 16, 1st execution (ticks): Renode 17, board 19
-   LDR.W SRAM, word-aligned, N = 16, 2nd execution (ticks): Renode 17, board 19
-   LDR.W SRAM, word-aligned, N = 32, 1st execution (ticks): Renode 33, board 35
-   LDR.W SRAM, word-aligned, N = 32, 2nd execution (ticks): Renode 33, board 35
-   LDR.W SRAM, halfword-aligned, N = 16, 1st execution (ticks): Renode 17, board 26
-   LDR.W SRAM, halfword-aligned, N = 16, 2nd execution (ticks): Renode 17, board 26
-   LDR.W SRAM, halfword-aligned, N = 32, 1st execution (ticks): Renode 33, board 50
-   LDR.W SRAM, halfword-aligned, N = 32, 2nd execution (ticks): Renode 33, board 50
-   LDR flash, N = 16, 1st execution (ticks): Renode 17, board 23
-   LDR flash, N = 16, 2nd execution (ticks): Renode 17, board 23
-   LDR flash, N = 32, 1st execution (ticks): Renode 33, board 43
-   LDR flash, N = 32, 2nd execution (ticks): Renode 33, board 43
-   LDR GPIOA_IDR (APB2), N = 16, 1st execution (ticks): Renode 17, board 52
-   LDR GPIOA_IDR (APB2), N = 16, 2nd execution (ticks): Renode 17, board 52
-   LDR GPIOA_IDR (APB2), N = 32, 1st execution (ticks): Renode 33, board 100
-   LDR GPIOA_IDR (APB2), N = 32, 2nd execution (ticks): Renode 33, board 100
-   STR GPIOA_BSRR (APB2), N = 16, 1st execution (ticks): Renode 17, board 36
-   STR GPIOA_BSRR (APB2), N = 16, 2nd execution (ticks): Renode 17, board 36
-   STR GPIOA_BSRR (APB2), N = 32, 1st execution (ticks): Renode 33, board 68
-   STR GPIOA_BSRR (APB2), N = 32, 2nd execution (ticks): Renode 33, board 68
-   LDR TIM2_CNT (APB1), N = 16, 1st execution (ticks): Renode 17, board 52
-   LDR TIM2_CNT (APB1), N = 16, 2nd execution (ticks): Renode 17, board 52
-   LDR TIM2_CNT (APB1), N = 32, 1st execution (ticks): Renode 33, board 100
-   LDR TIM2_CNT (APB1), N = 32, 2nd execution (ticks): Renode 33, board 100
-   DSB, N = 16, 1st execution (ticks): Renode 17, board 18
-   DSB, N = 16, 2nd execution (ticks): Renode 17, board 18
-   DSB, N = 32, 1st execution (ticks): Renode 33, board 34
-   DSB, N = 32, 2nd execution (ticks): Renode 33, board 34
-   ISB, N = 16, 1st execution (ticks): Renode 17, board 50
-   ISB, N = 16, 2nd execution (ticks): Renode 17, board 50
-   ISB, N = 32, 1st execution (ticks): Renode 33, board 98
-   ISB, N = 32, 2nd execution (ticks): Renode 33, board 98
-   UDIV ÷ 0, N = 16, 1st execution (ticks): Renode 17, board 34
-   UDIV ÷ 0, N = 16, 2nd execution (ticks): Renode 17, board 34
-   UDIV ÷ 0, N = 32, 1st execution (ticks): Renode 33, board 66
-   UDIV ÷ 0, N = 32, 2nd execution (ticks): Renode 33, board 66
-   UDIV largest quotient, N = 16, 1st execution (ticks): Renode 17, board 194
-   UDIV largest quotient, N = 16, 2nd execution (ticks): Renode 17, board 194
-   UDIV largest quotient, N = 32, 1st execution (ticks): Renode 33, board 386
-   UDIV largest quotient, N = 32, 2nd execution (ticks): Renode 33, board 386
-   UMULL small operands, N = 16, 1st execution (ticks): Renode 17, board 50
-   UMULL small operands, N = 16, 2nd execution (ticks): Renode 17, board 50
-   UMULL small operands, N = 32, 1st execution (ticks): Renode 33, board 98
-   UMULL small operands, N = 32, 2nd execution (ticks): Renode 33, board 98
-   UMULL largest operands, N = 16, 1st execution (ticks): Renode 17, board 82
-   UMULL largest operands, N = 16, 2nd execution (ticks): Renode 17, board 82
-   UMULL largest operands, N = 32, 1st execution (ticks): Renode 33, board 162
-   UMULL largest operands, N = 32, 2nd execution (ticks): Renode 33, board 162
-   LDM 4 registers, N = 16, 1st execution (ticks): Renode 17, board 82
-   LDM 4 registers, N = 16, 2nd execution (ticks): Renode 17, board 82
-   LDM 4 registers, N = 32, 1st execution (ticks): Renode 33, board 162
-   LDM 4 registers, N = 32, 2nd execution (ticks): Renode 33, board 162
-   PUSH + POP 4 registers, N = 16, 1st execution (ticks): Renode 33, board 162
-   PUSH + POP 4 registers, N = 16, 2nd execution (ticks): Renode 33, board 162
-   PUSH + POP 4 registers, N = 32, 1st execution (ticks): Renode 65, board 322
-   PUSH + POP 4 registers, N = 32, 2nd execution (ticks): Renode 65, board 322
-   LDR unaligned at +1, N = 16, 1st execution (ticks): Renode 17, board 51
-   LDR unaligned at +1, N = 16, 2nd execution (ticks): Renode 17, board 51
-   LDR unaligned at +1, N = 32, 1st execution (ticks): Renode 33, board 99
-   LDR unaligned at +1, N = 32, 2nd execution (ticks): Renode 33, board 99
-   LDR unaligned at +2, N = 16, 1st execution (ticks): Renode 17, board 35
-   LDR unaligned at +2, N = 16, 2nd execution (ticks): Renode 17, board 35
-   LDR unaligned at +2, N = 32, 1st execution (ticks): Renode 33, board 67
-   LDR unaligned at +2, N = 32, 2nd execution (ticks): Renode 33, board 67

## C1-06 — exception frame and return (`c1_06_exception_frame`): DIVERGES

- 3 runs in Renode
- 3 runs on the board
- 133/137 items equal to the board
- differences:
-   MSP, SP misaligned, STKALIGN 0: frame address below SP (bytes): Renode 36, board 32
-   MSP, SP misaligned, STKALIGN 0: stacked xPSR: Renode 0x61000200, board 0x61000000
-   PSP, SP misaligned, STKALIGN 0: frame address below SP (bytes): Renode 36, board 32
-   PSP, SP misaligned, STKALIGN 0: stacked xPSR: Renode 0x61000200, board 0x61000000
