# C2 — Interrupts and timer

| Data | ELF | ELF SHA-256 | Renode | reps | other |
|---|---|---|---|---|---|
| `renode/c2_01_pending_and_enable` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_02_priority_and_tie` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_03_nested_preemption` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_04_masks` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_05_wfi_and_primask` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_06_tail_chaining` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_07_exception_cost` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `board/c2_07_exception_cost` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | — | 3 |  |
| `renode/c2_08_timer_period` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_09_repeated_request` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `renode/c2_10_timer_tie` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `board/c2_10_timer_tie` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | — | 3 |  |
| `renode/c2_11_coalescence` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `board/c2_11_coalescence` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | — | 3 |  |
| `renode/c2_12_timer_count_at_entry` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `board/c2_12_timer_count_at_entry` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | — | 3 |  |
| `renode/c2_13_flag_clear_before_return` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | Renode v1.17.0 | 3 |  |
| `board/c2_13_flag_clear_before_return` | `build/c2/firmware.elf` | `2a6154534ff8f804c4e0e6b727cf7b37ec7645b18b0d93e9b5b49aead061b23c` | — | 3 |  |

| Case | Oracle | Verdict |
|---|---|---|
| C2-01 — pending and enable (`c2_01_pending_and_enable`) | document | **EQUAL** |
| C2-02 — priority and tie (`c2_02_priority_and_tie`) | document | **EQUAL** |
| C2-03 — nested preemption (`c2_03_nested_preemption`) | document | **EQUAL** |
| C2-04 — masks, effect (`c2_04_masks`) | document | **EQUAL** |
| C2-04 — masks, value read (`c2_04_masks`) | document | **DIVERGES** |
| C2-05 — WFI and PRIMASK (`c2_05_wfi_and_primask`) | document | **EQUAL** |
| C2-06 — tail-chaining (`c2_06_tail_chaining`) | document | **EQUAL** |
| C2-07 — cost of an exception, entry (`c2_07_exception_cost`) | board | **DIVERGES** |
| C2-07 — cost of an exception, return (`c2_07_exception_cost`) | board | **DIVERGES** |
| C2-07 — cost of an exception, chaining (`c2_07_exception_cost`) | board | **DIVERGES** |
| C2-08 — timer period (`c2_08_timer_period`) | document | **DIVERGES** |
| C2-09 — request during the service, by software (`c2_09_repeated_request`) | document | **EQUAL** |
| C2-09 — request during the service, level of the flag (`c2_09_repeated_request`) | document | **EQUAL** |
| C2-10 — tie between two timers, pending together (`c2_10_timer_tie`) | board | **EQUAL** |
| C2-10 — tie between two timers, synchronized start (`c2_10_timer_tie`) | board | **DIVERGES** |
| C2-11 — coalescence during a mask (`c2_11_coalescence`) | board | **EQUAL** |
| C2-12 — timer count at the entry (`c2_12_timer_count_at_entry`) | board | **DIVERGES** |
| C2-13 — flag clear before the return (`c2_13_flag_clear_before_return`) | board | **DIVERGES** |

## C2-01 — pending and enable (`c2_01_pending_and_enable`): EQUAL

- 3 runs in Renode; end at 418125 ns
- 6/6 items equal

## C2-02 — priority and tie (`c2_02_priority_and_tie`): EQUAL

- 3 runs in Renode; end at 640625 ns
- 17/17 items equal

## C2-03 — nested preemption (`c2_03_nested_preemption`): EQUAL

- 3 runs in Renode; end at 805000 ns
- 46/46 items equal

## C2-04 — masks (`c2_04_masks`): effect: EQUAL; value read: DIVERGES

- 3 runs in Renode; end at 2365625 ns
- effect: 23/23 items equal
- value read: 14/20 items equal
- value read: differences:
-   BASEPRI = 0x0f: observed 15, expected 0
-   BASEPRI = 0x1f: observed 31, expected 16
-   BASEPRI = 0x8f: observed 143, expected 128
-   BASEPRI = 0xff: observed 255, expected 240
-   BASEPRI = 0x00, BASEPRI_MAX = 0x8f: observed 143, expected 128
-   BASEPRI = 0x80, BASEPRI_MAX = 0x7f: observed 127, expected 112

## C2-05 — WFI and PRIMASK (`c2_05_wfi_and_primask`): EQUAL

- 3 runs in Renode; end at 425375 ns
- 3/3 items equal
- instructions while asleep: PRIMASK = 0: 0; PRIMASK = 1: 0

## C2-06 — tail-chaining (`c2_06_tail_chaining`): EQUAL

- 3 runs in Renode; end at 194000 ns
- 7/7 items equal

## C2-07 — cost of an exception (`c2_07_exception_cost`): entry: DIVERGES; return: DIVERGES; chaining: DIVERGES

- 3 runs in Renode
- 3 runs on the board
- entry: 0/3 items equal
- entry: differences:
-   point 0: observed 3, expected 16–16
-   point 1: observed 3, expected 16–16
-   point 2: observed 3, expected 16–16
- return: 0/3 items equal
- return: differences:
-   point 0: observed 3, expected 13–13
-   point 1: observed 3, expected 13–13
-   point 2: observed 3, expected 13–13
- chaining: 0/3 items equal
- chaining: differences:
-   point 0: observed 4, expected 11–11
-   point 1: observed 4, expected 11–11
-   point 2: observed 4, expected 11–11
- entry: board [16, 16, 16], Renode [3, 3, 3] (ticks)
- return: board [13, 13, 13], Renode [3, 3, 3] (ticks)
- chaining: board [11, 11, 11], Renode [4, 4, 4] (ticks)

## C2-08 — timer period (`c2_08_timer_period`): DIVERGES

- 3 runs in Renode; end at 7147125 ns
- 0/18 items equal
- differences:
-   PSC = 0, ARR = 999, period 1: observed 999, expected 1000
-   PSC = 0, ARR = 999, period 2: observed 999, expected 1000
-   PSC = 0, ARR = 999, period 3: observed 999, expected 1000
-   PSC = 9, ARR = 99, period 1: observed 990, expected 1000
-   PSC = 9, ARR = 99, period 2: observed 990, expected 1000
-   PSC = 9, ARR = 99, period 3: observed 990, expected 1000
-   PSC = 99, ARR = 9, period 1: observed 900, expected 1000
-   PSC = 99, ARR = 9, period 2: observed 900, expected 1000
-   PSC = 99, ARR = 9, period 3: observed 900, expected 1000
-   PSC = 99, ARR = 3, period 1: observed 300, expected 400
-   PSC = 99, ARR = 3, period 2: observed 300, expected 400
-   PSC = 99, ARR = 3, period 3: observed 300, expected 400
-   PSC = 99, ARR = 1, period 1: observed 100, expected 200
-   PSC = 99, ARR = 1, period 2: observed 100, expected 200
-   PSC = 99, ARR = 1, period 3: observed 100, expected 200
-   PSC = 7, ARR = 999, period 1: observed 7992, expected 8000
-   PSC = 7, ARR = 999, period 2: observed 7992, expected 8000
-   PSC = 7, ARR = 999, period 3: observed 7992, expected 8000
- observed periods by (PSC, ARR): [[999], [990], [900], [300], [100], [7992]]

## C2-09 — request during the service (`c2_09_repeated_request`): by software: EQUAL; level of the flag: EQUAL

- 3 runs in Renode; end at 545875 ns
- by software: 3/3 items equal
- level of the flag: 5/5 items equal

## C2-10 — tie between two timers (`c2_10_timer_tie`): pending together: EQUAL; synchronized start: DIVERGES

- 3 runs in Renode
- 3 runs on the board
- pending together: 2/2 items equal
- synchronized start: 0/2 items equal
- synchronized start: differences:
-   TIM2 master: observed (44,), expected (44, 45)
-   TIM3 master: observed (45,), expected (44, 45)

## C2-11 — coalescence during a mask (`c2_11_coalescence`): EQUAL

- 3 runs in Renode
- 3 runs on the board
- 4/4 items equal
- board [0, 0, 1, 2], Renode [0, 0, 1, 2] by ('window 500', 'window 1500', 'window 2500', 'window 3500')
- board context: period 1000
- Renode context: period 999

## C2-12 — timer count at the entry (`c2_12_timer_count_at_entry`): DIVERGES

- 3 runs in Renode
- 3 runs on the board
- 0/8 items equal
- differences:
-   point 0: observed 1, expected 17–17
-   point 1: observed 1, expected 17–17
-   point 2: observed 1, expected 17–17
-   point 3: observed 1, expected 17–17
-   point 4: observed 1, expected 17–17
-   point 5: observed 1, expected 17–17
-   point 6: observed 1, expected 17–17
-   point 7: observed 1, expected 17–17
- board [17, 17, 17, 17, 17, 17, 17, 17], Renode [1, 1, 1, 1, 1, 1, 1, 1] (ticks)
- board context: period 1000
- Renode context: period 999

## C2-13 — flag clear before the return (`c2_13_flag_clear_before_return`): DIVERGES

- 3 runs in Renode
- 3 runs on the board
- 3/5 items equal
- differences:
-   k = 0: observed 0, expected 8
-   k = 1: observed 0, expected 8
- boundary absent in the range (never re-enters)
- board [8, 8, 0, 0, 0], Renode [0, 0, 0, 0, 0] by ('k = 0', 'k = 1', 'k = 2', 'DSB', 'read back')
- board context: period 1000
- Renode context: period 999
