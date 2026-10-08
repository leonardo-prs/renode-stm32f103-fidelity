# STM32F103 first-call penalty for code in flash: literature search

Scope: explain why the first call of each flash-resident kernel costs ~110-440 extra cycles, while the same kernel in SRAM shows no penalty. Setup: STM32F103C8T6, Cortex-M3 r2p0, SYSCLK = HSI 8 MHz, FLASH_ACR = 0x30 (LATENCY=0, PRFTBE=1, PRFTBS=1), no caches.

Labels used: **VERIFIED** (seen in a fetched or searched page, quote as recorded), **UNVERIFIED** (claim from a search summary or memory, not checked against a primary source), **SPECULATION** (my reasoning, no source).

## Bottom line

No source found that documents a first-call-only penalty for flash code on STM32F103. The documented mechanisms (prefetch buffer, wait states, Cortex-M3 pipeline) are per-access effects and should make the first and later calls cost the same. The F1 has no cache or ART-style accelerator (VERIFIED from secondary sources only, see below). So the best-supported position is: the cause is not a documented F1 flash cache, and the first-call asymmetry still needs an explanation that the literature does not supply.

## 1. Flash interface (RM0008)

- **RM0008 section 3.3.3 text: NOT RETRIEVED.** Search returned only driver sources and a cover excerpt. UNVERIFIED that the section name matches the user's reference; check the revision PDF on st.com.
- HAL driver for F1 (search result, pigweed.googlesource.com `stm32f1xx_hal_flash.c`) describes the flash interface as managing AHB I-Code and D-Code accesses and accelerating execution with "instruction prefetch". VERIFIED from search snippet: "Prefetch on I-Code". The HAL prefetch enable/disable macros set/clear the PRFTBE bit in FLASH->ACR. VERIFIED from search snippet.
- Prefetch scope is instruction fetch only (I-Code), per the same snippet. Data reads from flash are not covered by this buffer.
- General article (DEV Community, https://dev.to/carolineee/flash-prefetching-function-of-mcu-39ph), fetched via WebFetch summarizer. VERIFIED quote (via summarizer): "Flash prefetching works best for sequential code execution." The article does not say whether fetched code is retained for repeat execution, and it does not describe F1 specifics. Buffer size "usually 32 to 128 bytes" is its generic claim, UNVERIFIED for F103.

## 2. Undocumented "cache" / line buffer on F103

- No source found describing a cache, ART, or retained line buffer on F103. VERIFIED negative: the F2/F4 ART is the only accelerator described in the results.
- ST forum (search summary, https://community.st.com/s/question/0D50X00009XkZF0SAN/ and related threads): a reply reportedly says the F1 has "no attempt to cache, or hold lines for the prefetch queue". UNVERIFIED: this is a summary of a forum reply, not a verbatim quote I checked.
- Search summary also says the F1 "is also a simpler design than the F2 and F4, which mask flash slowness with caches". UNVERIFIED.
- MicroMouse article (https://micromouseonline.com/?p=242), fetched via WebFetch summarizer. VERIFIED quotes (via summarizer): "Wait states can be added to flash memory accesses to allow the pre-fetch buffer to keep up." and "The buffer is turned on by default after a reset so you don't need to do anything special there." The article never mentions F1 and describes no retained lines.
- Errata: ES0340 is the wrong document for this part. Search result (https://www.stmcu.com.cn/upload/pdf_html/f3386aff8b75c94ffe6e652a91bad4c0.html) describes ES0340 Rev 16 as covering STM32F101xC/D/E and STM32F103xC/D/E. VERIFIED from search snippet. The x8 erratum is a separate document; a copy is referenced (DocID14574, Rev 13, Nov 2015) and I saw only its table of contents with no prefetch item. UNVERIFIED for prefetch content. The x8 erratum PDF was not fetched.

## 3. Cortex-M3 itself (prefetch unit, branch behavior)

- r2p0 TRM: the search result identifies ARM DDI 0337G (r2p0 first release, 2008) at https://WWW.KEIL.COM/dd/docs/datashts/arm/cortex_m3/r2p0/ddi0337g_cortex_m3_r2p0_trm.pdf. VERIFIED that the URL appears in results. The PDF was not fetched, so the chapter content below is UNVERIFIED.
- Secondary sources (search results, not verified against the TRM): the core prefetches ahead of execution and speculatively fetches from branch targets (Microchip docs, https://onlinedocs.microchip.com/oxy/GUID-199548F4-607C-436B-80C7-E4F280C1CAD2-en-US-1/GUID-6D1AE9A3-022F-403A-9C94-39DD2DC03A50.html). UNVERIFIED for the exact text.
- ST forum (search summary): with 2 flash wait states, prediction helps only unconditional branches. UNVERIFIED. At LATENCY=0 this effect should not apply at 8 MHz.
- Cortex-M3 instruction timing assumes zero wait states, and pipeline refill costs 1-3 cycles (search summary of the M3 instruction summary, https://os.mbed.com/media/uploads/4180_1/cortexm3_instructions.htm). UNVERIFIED wording.
- SPECULATION: none of the core-side mechanisms (pipeline refill, branch speculation) is stateful across calls in a way that would leave a one-time penalty of 110-440 cycles on the first call only. They would cost roughly the same on call 1 and call 2.

## 4. Debugger / DWT measurement artifacts

- ST forum (https://community.st.com/stm32-mcus-products-25/cycle-counter-different-when-stepping-79511): an F103C8T6 at 72 MHz saw CYCCNT differ by about 80 cycles between stepping and free-running. VERIFIED from search snippet.
- Debugger can disable DWT when it disconnects, freezing the counter (https://industrialmonitordirect.com/blogs/knowledgebase/stm32-dwt-cyccnt-debugger-freeze-prevention). UNVERIFIED. Not relevant to the user's reproduction, which was made with the debugger detached.
- Forum advice (https://community.st.com/s/question/0D53W00000JMWtc/dwtcyccnt-does-not-seems-to-count-cycle?): read disassembly to see what runs between the two reads; time many iterations and subtract loop overhead. VERIFIED from search summary.
- Interrupt inflation of single samples (https://community.st.com/stm32-mcus-products-25/how-do-you-measure-the-execution-cpu-cycles-for-a-section-of-code-38772). VERIFIED from search summary.
- Counterpoint (https://community.st.com/stm32-mcus-products-25/stm32h503-code-execution-performance-issue-152107): one user saw the same DWT count from flash and SRAM on an H503. Different family, so weak evidence.

## 5. Other secondary observations (from search summaries, all UNVERIFIED)

- Prefetch matters most for linear code; jumps stall for the wait-state count (ST forum 2020, https://community.st.com/t5/stm32-mcus-products/about-performance-in-stm32f103c8t6/m-p/252878). UNVERIFIED.
- A user measured non-optimal code from RAM about 11% faster than from flash; a reply cautioned that SRAM is not always faster (https://community.st.com/s/question/0D50X00009Xkamc/stm32f103-different-processing-rate). UNVERIFIED.

## 6. Why the observation is hard to explain with the documented mechanisms

1. The user's effect is per function and one-time: second and later calls are identical and bit-for-bit deterministic, and it returns after every reset. A pure per-access mechanism (prefetch miss, wait state, pipeline refill) would not single out the first call of the same code. This is the main argument against a documented flash-timing cause.
2. A retained line buffer would explain a one-time cost, but the sources found do not describe one on F103. The reply quoted in section 2 (UNVERIFIED) says there is none.
3. At LATENCY=0 and 8 MHz, flash access should be near SRAM speed. A 110-440 cycle first-call cost is large for that setting.
4. The effect disappears when the same kernel runs from SRAM, so it is tied to the flash fetch path or the flash-resident address. That is consistent with the flash interface, but the documented flash behavior does not predict a first-call-only effect.

## 7. SPECULATION: experiments that would separate the hypotheses

These are suggestions, not findings.

- Toggle PRFTBE (FLASH_ACR bit 4) off and repeat. If the first-call penalty changes size or vanishes, the flash prefetch path is implicated. If it is unchanged, look at the core or the measurement.
- Vary the kernel's address alignment (2-byte vs 4-byte aligned) and the number of instructions in the loop. A penalty tied to a fetch-window boundary would move with alignment.
- Call a different flash function first, then the kernel. If the penalty follows the kernel's address, it is address-keyed state. If it follows call order or time, it is something else.
- Disable SysTick and any other interrupts during the measurement. A fixed-phase timer event after reset would reproduce deterministically across resets.
- Measure an empty function (just BX LR) at the same flash address as the first call. If it shows the same first-call cost, the cost is in the call path, not the kernel body.
- Read the first-call cost as a single number across several resets and check whether it depends on the function pointer load itself (literal pool fetch from flash on the first use).

## Sources (with status)

- https://dev.to/carolineee/flash-prefetching-function-of-mcu-39ph (fetched via summarizer; VERIFIED quote)
- https://micromouseonline.com/?p=242 (fetched via summarizer; VERIFIED quotes)
- https://www.stmcu.com.cn/upload/pdf_html/f3386aff8b75c94ffe6e652a91bad4c0.html (search snippet; ES0340 scope VERIFIED)
- https://community.st.com/stm32-mcus-products-25/cycle-counter-different-when-stepping-79511 (search snippet)
- https://community.st.com/s/question/0D53W00000JMWtc/dwtcyccnt-does-not-seems-to-count-cycle? (search summary)
- https://community.st.com/stm32-mcus-products-25/how-do-you-measure-the-execution-cpu-cycles-for-a-section-of-code-38772 (search summary)
- https://community.st.com/stm32-mcus-products-25/stm32h503-code-execution-performance-issue-152107 (search summary)
- https://industrialmonitordirect.com/blogs/knowledgebase/stm32-dwt-cyccnt-debugger-freeze-prevention (search summary, UNVERIFIED)
- https://community.st.com/t5/stm32-mcus-products/about-performance-in-stm32f103c8t6/m-p/252878 (search summary, UNVERIFIED)
- https://community.st.com/s/question/0D50X00009Xkamc/stm32f103-different-processing-rate (search summary, UNVERIFIED)
- https://WWW.KEIL.COM/dd/docs/datashts/arm/cortex_m3/r2p0/ddi0337g_cortex_m3_r2p0_trm.pdf (URL only, not fetched)
- https://onlinedocs.microchip.com/oxy/GUID-199548F4-607C-436B-80C7-E4F280C1CAD2-en-US-1/GUID-6D1AE9A3-022F-403A-9C94-39DD2DC03A50.html (search snippet, UNVERIFIED)
- https://os.mbed.com/media/uploads/4180_1/cortexm3_instructions.htm (search snippet, UNVERIFIED)
- https://pigweed.googlesource.com/third_party/github/STMicroelectronics/stm32f1xx_hal_driver/+/HEAD/Src/stm32f1xx_hal_flash.c (search snippet, VERIFIED for PRFTBE macro and I-Code wording)

## Gaps

- RM0008 section 3.3.3 not retrieved (PDF not fetched).
- x8 erratum (DocID14574) not fetched; prefetch content unknown.
- Cortex-M3 r2p0 TRM (DDI0337G) not fetched; prefetch-unit wording unverified.
- No forum thread found that matches the first-call-only observation.
