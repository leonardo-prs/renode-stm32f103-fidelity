# Blue Pill identity: candidate STM32F103 clone families

Scope: match observed probe traits against known clone families. Sources are
listed per row. Items marked SPECULATION are inference, not sourced.

## Observed traits (from user probe)

| # | Trait | Value |
|---|---|---|
| T1 | SCB CPUID | 0x412FC230 (Cortex-M3 r2p0) |
| T2 | DBGMCU_IDCODE | 0x20030410 (DEV_ID 0x410, REV_ID 0x2003) |
| T3 | Flash size reg 0x1FFFF7E0 | 0x0080 (128 KB) |
| T4 | Unique ID 0x1FFFF7E8..F0 | all zeros |
| T5 | ROM table PIDs / CIDs / entries | PID 0x10 0x04 0x0A 0x00; CID 0x0D 0x10 0x05 0xB1; entries fff0f003 fff02003 fff03003 fff01003 |
| T6 | System memory first words | 20002000 1fffcc5d 9020d002 0000a003 |
| T7 | USART1 RX buffers >= 4 bytes, no ORE | observed |
| T8 | Flash first-execution penalty (~100-450 cycles at 0 WS) | observed |
| T9 | OpenOCD SW-DP IDCODE | not stated by user (see row for CS32 below) |

## Reference traits (what genuine and clone parts are documented to show)

- **Genuine STM32F103 CPUID is r1p1.** The f103id source states: "STM32 uses
  Cortex-M3 r1p1 and the right JEP106 ID" and "Clones use Cortex-M3 r2p1 where
  genuine STM parts use r1p1."
  Source: https://git.cuvoodoo.info/kingkevin/f103id/src/branch/master/identifier.c
- **Genuine STM32F103 DBGMCU_IDCODE** on C8: DEV_ID 0x410, REV_ID 0x2003.
  Clones CKS and GD share 0x410 / 0x2003 in the table below, so this value does
  not discriminate by itself.
  Source: https://mecrisp-stellaris-folkdoc.sourceforge.io/bluepill-diagnostics-v1.6.html
- **Genuine STM32F103C8 flash size register** is checked by the authenticity
  test to declare 64 KB; the same test checks a hidden second 64 KB block.
  Source: same bluepill-diagnostics page.
- **STM32F1 USART** (RM0008 §27.3.3): single RDR, ORE set on the second byte
  when RXNE is not cleared. No FIFO exists in the STM32F1 USART. Clone USART
  receive FIFO: **no source found in this research**.
- **Unique ID** at 0x1FFFF7E8, 96 bit, factory programmed: source
  https://www.alldatasheet.net/ (STM32F103 datasheet pages); no clone UID
  contents were found in any source.

## Candidate families vs observed traits

Legend: MATCH = consistent with a source; MISMATCH = contradicts a source;
UNKNOWN = no source found; SPEC = speculation.

| Family | T1 CPUID r2p0 | T2 DEV 0x410 / REV 0x2003 | T3 flash 128 KB | T4 UID zero | T5 ROM/PID | T7 USART 4-byte RX | T8 flash penalty | SWD IDCODE 0x2ba01477 |
|---|---|---|---|---|---|---|---|---|
| **CKS32F103 / CS32F103 (China Key Systems)** | MATCH (variant 2 = clone side; r2p0 is not r2p1, so partial) — f103id | MATCH — Mecrisp table: CKS32F103C8T6 0x410 / 0x2003 | MATCH — Mecrisp table: CKS32F103CBT6 declares 128 KB; EEVblog Reply #17 reports 128k writable on CS32 | UNKNOWN | UNKNOWN (generic CoreSight ROM entries are ST/ARM-generic) | UNKNOWN | UNKNOWN | MATCH — EEVblog "unexpected idcode" thread: SW-DP reports 0x2ba01477 on a Blue Pill clone; tsman says it "isn't identifying the uC itself" |
| GigaDevice GD32F103 | partial — f103id: "GD32 uses Cortex-M3 r2p1" (variant 2, but r2p1) | partial — DEV 0x410 is listed for GD32F130 with REV 0x1303 (different REV) | UNKNOWN for F103 (gnuk list: zero-wait claims contradicted by its own correction) | UNKNOWN | f103id GD JEP106 cont 7 / id 0x51 — observed PID does not decode to 0x51 (see note) | UNKNOWN | UNKNOWN | UNKNOWN |
| Geehy APM32F103 | UNKNOWN | MISMATCH-leaning — Mecrisp row: APM32F103CBT6 0x410 / 0x2003 (same as CKS); f103id: APM DBGMCU dev_id NOT readable | UNKNOWN | UNKNOWN (APM datasheets list a 96-bit UID; nonzero not verified) | f103id: APM JEP106 0x3B cont 4 (same as CKS) | UNKNOWN | UNKNOWN | UNKNOWN |
| WCH CH32F103 | MISMATCH (SPEC: CH32F103 uses a RISC-V core, not Cortex-M3, from general knowledge; not checked in this run) | UNKNOWN (Mecrisp: DEV-ID/RevID unknown) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN. Hackaday notes Blue Pill boards carrying CH32F103C8T6 |
| HK32F103 (Hangshun) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | MISMATCH — f103id: HK JEP106 cont 5 / id 0x55 | UNKNOWN | UNKNOWN | UNKNOWN |
| MindMotion MM32F103 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Genuine STM32F103C8T6 (reference) | MISMATCH for r2p0 (f103id: STM is r1p1) | MATCH | MISMATCH (genuine C8 declares 64 KB per Mecrisp authenticity test) | MISMATCH (genuine UID is nonzero — ST datasheet, not re-fetched here) | MATCH on generic CoreSight entries | MISMATCH (RM0008: single RDR, ORE on 2nd byte) | MISMATCH (SPEC: genuine 0-WS flash with prefetch buffer should show no first-run penalty) | MISMATCH |

## Notes

1. **CS32 and CKS32 are the same company line.** The STM32duino forum snippet
   cited by the search identifies CKS (中科芯微) as the maker of CS32F103.
   Source: https://www.cnx-software.com/2019/02/10/cs32-mcu-stm32-clone-bluepill-board/
   Hence the "CS32" and "CKS32" names in the sources refer to the same chip
   family. This report uses "CKS32/CS32" for both.

2. **The OpenOCD 0x2ba01477 IDCODE is the strongest single discriminator in
   the sources.** The EEVblog thread (https://www.eevblog.com/forum/beginners/unexpected-idcode-flashing-bluepill-clone/msg2143567)
   attributes it to the SW-DP revision field. Only the CS32/CKS clone is
   linked to this value in the material reviewed. Other families were not
   checked against this value.

3. **Bluepill Diagnostics (Porter, V1.631/V1.632)** is the only source found
   with explicit per-family values for DEV_ID, REV_ID, flash, hidden-block and
   JEDEC. Its table: CKS32F103C8T6 declares 64 KB and has no hidden block;
   CKS32F103CBT6 declares 128 KB. Our observed 128 KB is consistent with the
   CBT6 row, not the C8 row.
   Source: https://mecrisp-stellaris-folkdoc.sourceforge.io/bluepill-diagnostics-v1.6.html
   The same page notes its JEDEC rows for CS32 and APM32 are identical (0x3B / 0x04),
   so JEDEC cannot separate them.

4. **Our decoding of the ROM-table PIDs (SPECULATION).** Standard CoreSight
   layout: PID1[3:0] = JEP106 ID[3:0], PID2[2:0] = JEP106 ID[6:4]. With
   PID1 = 0x04 and PID2 = 0x0A this gives ID 0x24, not 0x20 (ST), 0x3B (CS/APM)
   or 0x51 (GD). f103id's own comment for this field is ambiguous (it names
   PID0/PID1 as the JEP106 source), so this decode is not confirmed against
   a source. Treat T5 as unresolved.

5. **The 4-byte USART RX observation has no source in this research.** No family
   document found documents a receive FIFO on the F1 USART. The probe result
   could be a clone-specific USART difference, a simulator artefact on the
   user's side, or a probe artefact. Verify by reading USART1->SR (ORE) and
   DR state directly, not by inference.

6. **The flash first-run penalty has no source in this research.** The GD32F103
   zero-wait claim is contested: gnuk mailing list (2018-08) retracted an
   earlier "only first 32 KB zero-wait" claim, and says the GD32F103 is
   zero-wait across flash. No source found for a clone instruction cache
   or flash cache on CKS/CS/GD/APM. The forum post mentioning a cache on
   a GD32 is anecdotal.
   Source: https://lists.gnupg.org/pipermail/gnuk-users/2018-August/000066.html

7. **UID all zeros** has no source found for any clone family. The UID
   address 0x1FFFF7E8 is documented for STM32F103 (ST RM0008 96-bit UID).
   f103id reads UID via libopencm3 macros, so the all-zero result can be
   checked by running f103id on the board.

## Most likely family (SPECULATION, ranked)

1. **CKS32F103 / CS32F103 (China Key Systems)** — best fit on T1 (variant 2),
   T2 (0x410 / 0x2003 in the CKS row), T3 (128 KB matches CBT6 row and CS32
   forum report), and the 0x2ba01477 SW-DP IDCODE. Open items: T4, T5, T7, T8.
2. GigaDevice GD32F103 — partial on T1 and T2; no source matches T3 or the
   SW-DP ID. Less likely.
3. APM32F103 — same DEV/REV and JEP as CKS, but f103id says APM DBGMCU dev_id
   is not readable, and the probe read it. Mismatch on that point.
4. CH32F103 — likely excluded by core type (SPEC: RISC-V, not Cortex-M3).
   Not verified in this run.
5. HK32F103 — excluded by JEP106 (cont 5 / id 0x55) if the observed PIDs are
   read as in f103id.

## How the user can confirm physically

1. **Read the chip marking under magnification.** STM32F103C8T6 (ST) is
   marked "STM32F103C8T6" on the top, with ST logo; CKS32F103 / CS32F103
   parts carry their own brand and part numbers. The cnx-software article
   notes that STMicro changed chip marking in Nov 2022 (PCN MDG/22/13318),
   so the marking alone is not conclusive.
   Source: https://www.cnx-software.com/2020/03/22/how-to-detect-stm32-fakes/
2. **Run the Bluepill Diagnostics binary** (menu `a`, `h`, `d`, `f`, `i`) on
   the same board; compare to the table above. Source link above.
3. **Run f103id** (kingkevin) against the board to check CPUID variant/rev,
   JEP106 ID, flash size, UID and system-memory CRC.
   Source: https://git.cuvoodoo.info/kingkevin/f103id
4. **Read the UID with OpenOCD** (`mdw 0x1FFFF7E8 3`) to confirm T4 with a
   second method before drawing a conclusion.

## Sources

- https://www.eevblog.com/forum/beginners/unexpected-idcode-flashing-bluepill-clone/msg2143567
- https://mecrisp-stellaris-folkdoc.sourceforge.io/bluepill-diagnostics-v1.6.html
- https://mecrisp-stellaris-folkdoc.sourceforge.io/clones-stm32-mcus.html
- https://git.cuvoodoo.info/kingkevin/f103id/src/branch/master/identifier.c
- https://www.cnx-software.com/2020/03/22/how-to-detect-stm32-fakes/
- https://www.cnx-software.com/2019/02/10/cs32-mcu-stm32-clone-bluepill-board/
- https://hackaday.com/2020/10/22/stm32-clones-the-good-the-bad-and-the-ugly/
- https://lists.gnupg.org/pipermail/gnuk-users/2018-August/000066.html
- https://community.platformio.org/t/debugging-of-stm32f103-clone-bluepill-board-wrong-idcode/14635
