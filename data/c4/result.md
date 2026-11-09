# C4 — Serial link

| Data | ELF | ELF SHA-256 | Renode | reps | other |
|---|---|---|---|---|---|
| `uh-a/c4_01_link_enable` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-A (default) |
| `uh-a/c4_02_equal_link` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-A (default) |
| `uh-a/c4_03_frame_format` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-A (default) |
| `uh-a/c4_04_slow_consumer` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-A (default) |
| `uh-a/c4_05_receive_interrupt` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-A (default) |
| `uh-a/c4_06_line_mismatch` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-A (default) |
| `uh-e/c4_06_line_mismatch` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | Renode v1.17.0 | 3 | hub: UH-E (StrictMode) |
| `board/c4_06_line_mismatch` | `build/c4/firmware.elf` | `19c173e15a2fecf32a529acd2328af710a8fb2f1d76d9d3778abac487fd968a3` | — | 3 |  |

| Case | Oracle | Verdict |
|---|---|---|
| C4-01 — link enable (`c4_01_link_enable`) | document, Renode UH-A | **DIVERGES** |
| C4-02 — equal link (`c4_02_equal_link`), reception | document, Renode UH-A | **EQUAL** |
| C4-02 — equal link (`c4_02_equal_link`), transmitter | document, Renode UH-A | **DIVERGES** |
| C4-03 — frame format (`c4_03_frame_format`), value and flags | document, Renode UH-A | **DIVERGES** |
| C4-03 — frame format (`c4_03_frame_format`), frame time | document, Renode UH-A | **DIVERGES** |
| C4-04 — slow consumer (`c4_04_slow_consumer`) | document, Renode UH-A | **DIVERGES** |
| C4-05 — receive interrupt (`c4_05_receive_interrupt`) | document, Renode UH-A | **EQUAL** |
| C4-06 — line mismatch (`c4_06_line_mismatch`) | Renode UH-A against the board | **DIVERGES** |
| C4-06 — line mismatch (`c4_06_line_mismatch`) | Renode UH-E against the board | **DIVERGES** |

## C4-01 — link enable (`c4_01_link_enable`), document, Renode UH-A: DIVERGES

- 3 runs in Renode; end at 3062500 ns
- 2/3 items equal
- differences:
-   TE = 0: words read: observed (90, 165), expected ()

## C4-02 — equal link (`c4_02_equal_link`), reception, document, Renode UH-A: EQUAL

- 3 runs in Renode; end at 19004000 ns
- 8/8 items equal
- BRR 832: intervals between writes [50, 50, 50, 50, 50, 50, 50], between RXNE [8320, 8320, 8320, 8320, 8320, 8320, 8320]
- BRR 69: intervals between writes [50, 50, 50, 50, 50, 50, 50], between RXNE [690, 690, 690, 690, 690, 690, 690]

## C4-02 — equal link (`c4_02_equal_link`), transmitter, document, Renode UH-A: DIVERGES

- 3 runs in Renode; end at 19004000 ns
- 0/4 items equal
- differences:
-   BRR 832: span of writes 2–8 over 6 frames: observed 300, expected 49800–50040
-   BRR 832: TC before writes 2–8: observed (True, True, True, True, True, True, True), expected (False, False, False, False, False, False, False)
-   BRR 69: span of writes 2–8 over 6 frames: observed 300, expected 4020–4260
-   BRR 69: TC before writes 2–8: observed (True, True, True, True, True, True, True), expected (False, False, False, False, False, False, False)
- BRR 832: intervals between writes [50, 50, 50, 50, 50, 50, 50], between RXNE [8320, 8320, 8320, 8320, 8320, 8320, 8320]
- BRR 69: intervals between writes [50, 50, 50, 50, 50, 50, 50], between RXNE [690, 690, 690, 690, 690, 690, 690]

## C4-03 — frame format (`c4_03_frame_format`), value and flags, document, Renode UH-A: DIVERGES

- 3 runs in Renode; end at 4533250 ns
- 5/8 items equal
- differences:
-   9N1: words read: observed (165, 165, 90, 90), expected (421, 165, 346, 90)
-   8E1: words read: observed (165, 165, 167, 167), expected (165, 165, 423, 423)
-   7E1: words read: observed (165, 37, 39, 167), expected (165, 165, 39, 39)

## C4-03 — frame format (`c4_03_frame_format`), frame time, document, Renode UH-A: DIVERGES

- 3 runs in Renode; end at 4533250 ns
- 1/4 items equal
- differences:
-   9N1: span of RXNE over 3 frames: observed 2070, expected 2157–2397
-   8E1: span of RXNE over 3 frames: observed 2070, expected 2157–2397
-   8N2: span of RXNE over 3 frames: observed 2070, expected 2157–2397

## C4-04 — slow consumer (`c4_04_slow_consumer`), document, Renode UH-A: DIVERGES

- 3 runs in Renode; end at 3928250 ns
- 2/6 items equal
- differences:
-   read deferred 1035 cycles: words read: observed (97, 98, 99, 100, 101, 102), expected (97, 99, 100, 101, 102)
-   read deferred 1035 cycles: error flags of each read: observed (0, 0, 0, 0, 0, 0), expected (8, 0, 0, 0, 0)
-   read deferred 2415 cycles: words read: observed (97, 98, 99, 100, 101, 102), expected (97, 101, 102)
-   read deferred 2415 cycles: error flags of each read: observed (0, 0, 0, 0, 0, 0), expected (8, 0, 0)

## C4-05 — receive interrupt (`c4_05_receive_interrupt`), document, Renode UH-A: EQUAL

- 3 runs in Renode; end at 2374500 ns
- 6/6 items equal

## C4-06 — line mismatch (`c4_06_line_mismatch`), Renode UH-A against the board: DIVERGES

- 3 runs in Renode; end at 175474875 ns
- 3 runs on the board
- 5/10 items equal
- differences:
-   Δ -3.85 % (BRR 800): observed ok, expected flags
-   Δ -7.45 % (BRR 770): observed ok, expected data
-   Δ +8.65 % (BRR 904): observed ok, expected data
-   7E1 → 7O1: observed ok, expected flags
-   PA2 not alternate function: observed ok, expected none
- Δ +0.00 % (BRR 832): Renode ok (8 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ -0.12 % (BRR 831): Renode ok (8 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ -2.88 % (BRR 808): Renode ok (8 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ +3.12 % (BRR 858): Renode ok (8 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ -3.85 % (BRR 800): Renode ok (8 reads, 0 wrong); board flags (8 reads, 0 wrong, NE 1)
- Δ -7.45 % (BRR 770): Renode ok (8 reads, 0 wrong); board data (8 reads, 8 wrong, FE 7, NE 8)
- Δ +8.65 % (BRR 904): Renode ok (8 reads, 0 wrong); board data (8 reads, 8 wrong, FE 8, NE 8)
- 8N2 → 8N1: Renode ok (8 reads, 0 wrong); board ok (8 reads, 0 wrong)
- 7E1 → 7O1: Renode ok (8 reads, 0 wrong); board flags (8 reads, 0 wrong, PE 8)
- PA2 not alternate function: Renode ok (8 reads, 0 wrong); board none (0 reads, 0 wrong)

## C4-06 — line mismatch (`c4_06_line_mismatch`), Renode UH-E against the board: DIVERGES

- 3 runs in Renode; end at 109244875 ns
- 3 runs on the board
- 1/10 items equal
- differences:
-   Δ -0.12 % (BRR 831): observed none, expected ok
-   Δ -2.88 % (BRR 808): observed none, expected ok
-   Δ +3.12 % (BRR 858): observed none, expected ok
-   Δ -3.85 % (BRR 800): observed none, expected flags
-   Δ -7.45 % (BRR 770): observed none, expected data
-   Δ +8.65 % (BRR 904): observed none, expected data
-   8N2 → 8N1: observed none, expected ok
-   7E1 → 7O1: observed none, expected flags
-   PA2 not alternate function: observed ok, expected none
- Δ +0.00 % (BRR 832): Renode ok (8 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ -0.12 % (BRR 831): Renode none (0 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ -2.88 % (BRR 808): Renode none (0 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ +3.12 % (BRR 858): Renode none (0 reads, 0 wrong); board ok (8 reads, 0 wrong)
- Δ -3.85 % (BRR 800): Renode none (0 reads, 0 wrong); board flags (8 reads, 0 wrong, NE 1)
- Δ -7.45 % (BRR 770): Renode none (0 reads, 0 wrong); board data (8 reads, 8 wrong, FE 7, NE 8)
- Δ +8.65 % (BRR 904): Renode none (0 reads, 0 wrong); board data (8 reads, 8 wrong, FE 8, NE 8)
- 8N2 → 8N1: Renode none (0 reads, 0 wrong); board ok (8 reads, 0 wrong)
- 7E1 → 7O1: Renode none (0 reads, 0 wrong); board flags (8 reads, 0 wrong, PE 8)
- PA2 not alternate function: Renode ok (8 reads, 0 wrong); board none (0 reads, 0 wrong)
