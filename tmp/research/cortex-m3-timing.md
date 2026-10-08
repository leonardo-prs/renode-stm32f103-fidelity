# Cortex-M3 instruction and exception timing: research notes

Target: STM32F103 (Cortex-M3 r2p0), HSI 8 MHz, 0 flash wait states, prefetch on.
Status legend: **VERIFIED** = read on a fetched page. **SNIPPET** = seen only in a search-result excerpt, not a fetched page. **UNVERIFIED** = from memory or not confirmed; do not cite without checking the primary document.

## Primary-source access status

| Document | Result |
|---|---|
| ARM DDI0337 (Cortex-M3 TRM), developer.arm.com / support.arm.com `ddi0337/g` | Pages redirect to `support.arm.com`; the fetched content is JavaScript-rendered and returned only the title "Documentation – Arm Developer". Not readable. |
| DDI0337G r2p0 PDF (`keil.com/dd/docs/datashts/arm/cortex_m3/r2p0/ddi0337g_cortex_m3_r2p0_trm.pdf`) | Fetched, but as a raw compressed PDF byte stream. No PDF text tool (pdftotext, pypdf, pdftoppm) is installed, so text could not be extracted. The PDF bookmarks show the relevant sections (see below). |
| mbed Cortex-M3 instruction summary (`os.mbed.com/media/uploads/4180_1/cortexm3_instructions.htm`) | Redirects to a GitHub org page; not fetched. |
| Microchip Cortex-M3 reference | HTTP 503 on fetch. |
| ST PM0056 (Cortex-M3 programming manual) | Only search results; no cycle tables found. |
| Joseph Yiu blog, Arm Community, 2016-04-01 | **VERIFIED** (fetched; see below). |

Section locations in DDI0337G (from the PDF bookmark outline, no page numbers): Chapter 18 "Instruction Timing" (18.1 About instruction timing, 18.3 Load-store timings); Chapter 19 "Processor timing parameters" (19.1); Chapter 5 "Exceptions" (5.5 Pre-emption, 5.6 Tail-chaining, 5.7 Late-arriving, 5.8 Exit, 5.8.1 Exception exit); Chapter 1.3 "Execution pipeline stages", 1.5 "Branch target forwarding".

Next step to get a citable table: open DDI0337G chapters 18, 19 and 5 in a PDF viewer (or run `pdftotext -layout` on a machine that has poppler), and fill in the UNVERIFIED rows below with page numbers.

## 1. Instruction cycle table

| Instruction class | Cycles | Conditions / footnotes | Source + section | Status |
|---|---|---|---|---|
| MOV / ADD / EOR (register, 16-bit) | 1 | Single-cycle ALU | DDI0337G ch. 18 | UNVERIFIED (memory) |
| MUL | 1 | 32x32 low result | DDI0337G ch. 18 | UNVERIFIED (memory) |
| MLA | 2 | | DDI0337G ch. 18 | UNVERIFIED (memory) |
| UMULL / SMULL | 3–5 | | DDI0337G ch. 18 | UNVERIFIED (memory) |
| SDIV / UDIV | 2–12 | Early termination; cycle count depends on operand magnitude | DDI0337G ch. 18 | UNVERIFIED (memory) |
| LDR (word, from memory) | 2 | Pipelined loads: consecutive loads can overlap; footnote on N+1 | DDI0337G ch. 18.3 | UNVERIFIED (memory) |
| STR | 2 | | DDI0337G ch. 18.3 | UNVERIFIED (memory) |
| LDM / STM | 1 + N | N = number of registers transferred. Interruptible: state kept in EPSR/ICI bits and resumed | DDI0337G ch. 18.3 | SNIPPET (r1p1 excerpt): "Load-store Multiple: 1+Nb (+Pa if PC loaded): LDMIA, POP, PUSH, and STMIA." |
| PUSH / POP | 1 + N | +P if PC loaded | DDI0337G ch. 18.3 | SNIPPET (same row as LDM/STM) |
| B / BL / BX / BLX (taken) | 1 + P | P = pipeline refill, 1 to 3 cycles, depends on target alignment/width and speculation. Taken branch adds a 2-cycle reload in the r1p1 excerpt | DDI0337G ch. 18 and 1.5 | SNIPPET (r1p1 excerpt "Branches 16 1+Pa ... B, BL, BX, BLX"; mbed summary "P ... ranges from 1 to 3", not fetched) |
| B<cond> (not taken) | 1 | | DDI0337G ch. 18 | SNIPPET (third-party summary, not primary) |
| NOP | 1 | | DDI0337G ch. 18 | UNVERIFIED (memory) |
| WFI | UNVERIFIED | Wakes on interrupt; not in any fetched source | | UNVERIFIED |
| IT | 1 | | DDI0337G ch. 18 | UNVERIFIED (memory) |
| CBZ / CBNZ (taken) | 1 + P | Like other taken branches | DDI0337G ch. 18 | UNVERIFIED (memory) |

## 2. Exception timing

| Event | Cycles | Conditions | Source + section | Status |
|---|---|---|---|---|
| Interrupt entry latency (Cortex-M3) | **12** | Zero wait-state memory; no bus contention from other masters; no added delay on the interrupt signal path; no blocking by a running exception; no unaligned or bit-band transfer in progress (such a transfer "can take 1 extra transfer cycle") | Yiu, "Beginner guide on interrupt latency..." (Arm Community blog, 2016-04-01), section "Interrupt Latency on the Cortex-M processor family", Table 1 ("Interrupt latency of Cortex-M processors with zero wait state memory systems") | **VERIFIED** (fetched) |
| Interrupt entry: R0–R3, R12 stacking | within the 12 cycles | Same table; "pushed onto the stack within the 12 cycle interrupt latency" | same section | **VERIFIED** |
| Exception exit | UNVERIFIED | The Yiu article gives no numeric exit count for M3/M4. Figures often quoted for M3 are around 10–12 cycles; not confirmed | DDI0337G ch. 5.8 | UNVERIFIED |
| Tail-chaining | **6** | "can be just six cycles in the Cortex-M3 and Cortex-M4 processors"; no extra conditions stated | Yiu blog, "What else could make a difference?" > "Tail chaining" | **VERIFIED** |
| Late-arrival | no number in text | Higher-priority IRQ arriving during stacking of a lower one is serviced first. The cycle figure is only in the article's Figure 10 | Yiu blog, "What else could make a difference?" > "Late Arrival" | **VERIFIED** (no number) |
| Pop pre-emption | no number in text | Only in the article's Figure 11 | Yiu blog, "What else could make a difference?" > "Pop pre-emption" | **VERIFIED** (no number) |
| Cortex-M0 figures (11-cycle sleep-on-exit, 4-cycle WFE) | n/a | Cortex-M0 only; do not use for M3 | Yiu blog | **VERIFIED** (scope note) |

Yiu's conditions also note that the interrupt latency table "does not tell you about the jitter of interrupt response time." That jitter comes from multi-cycle instructions and is the point where Renode and hardware can diverge.

## 3. Interruptibility

| Question | Answer | Source + section | Status |
|---|---|---|---|
| Are LDM / STM interruptible and resumable? | Yes. The multiple transfer's state is stored in the PSR (ICI bits), and the transfer resumes from where it stalled after the ISR. | Yiu blog, subsection "Interrupt Latency figure does not tell you about the jitter of interrupt response time" | **VERIFIED** (the blog says "the current state of the multiple transfer is automatically stored as part of the PSR"; it does not name ICI bits) |
| Is DIV (SDIV/UDIV) abandoned and restarted on interrupt? | UNVERIFIED. My recollection of the M3 TRM is that divide is not resumable and is restarted. The Yiu blog says "in most cases, the instruction is abandoned and restarted when the ISR is completed," which does not name DIV | DDI0337G ch. 18 / 5 | UNVERIFIED (DIV specifically). The general "abandoned and restarted" phrase is VERIFIED but not tied to DIV |
| ICI bit definition (EPSR[15:10], [26:25]) | UNVERIFIED | PM0056 / DDI0337G programmer's model | UNVERIFIED |

## 4. STM32F1 specifics (RM0008 not fetched)

| Item | Value | Source | Status |
|---|---|---|---|
| FLASH_ACR LATENCY = 0 WS allowed for SYSCLK ≤ 24 MHz | 0 WS for HCLK 0–24 MHz, 1 WS for 24–48 MHz, 2 WS for 48–72 MHz | Search snippet quoting an STM32F1 vendor-library comment (ese.han.nl and community forums). Not the RM0008 text | SNIPPET (not primary) |
| PRFTBE (prefetch buffer enable, bit 4 of FLASH_ACR) | Name on F1 is PRFTBE; F4/F7 use PRFTEN | Search snippet | SNIPPET |
| HLFCYA (half-cycle access, bit 3) | Only valid at 0 WS | Search result gave no source; my memory of RM0008 | UNVERIFIED |
| Code from SRAM on Cortex-M3 | Executes over the system bus, not ICode, so it has no prefetch and no I-cache path; penalty is extra latency per fetch and bus contention with DMA | UNVERIFIED (memory of the M3 bus matrix; needs DDI0337G ch. 1 and RM0008 ch. 2) | UNVERIFIED |

## 5. Gaps and recommended next steps

1. Get DDI0337G (r2p0) text for ch. 18 (instruction timing, incl. footnotes on pipelined loads, P, and divide early termination). The DDI0337G PDF is saved locally at `/home/leonardo/.claude/projects/-home-leonardo-projects-renode-stm32f103-fidelity/ad50eb8b-5aff-4984-81f7-67e29f99cc6f/tool-results/webfetch-1791424724617-8ao0nu.pdf`. It needs a PDF text tool on a machine that has one.
2. Get the exception exit cycle count and the Figure 10/11 numbers from DDI0337G ch. 5.
3. Get RM0008 (FLASH_ACR, PRFTBE, HLFCYA) from st.com to confirm the 0 WS / 24 MHz boundary.
4. For the thesis, cite the Yiu blog for the 12-cycle entry and 6-cycle tail-chaining figures. These are the only numbers verified on a fetched page.

## Sources

- Yiu, J. "A Beginner's Guide on Interrupt Latency - and Interrupt Latency of the Arm Cortex-M processors." Arm Community, 2016-04-01. https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/beginner-guide-on-interrupt-latency-and-interrupt-latency-of-the-arm-cortex-m-processors (fetched)
- ARM DDI0337G, Cortex-M3 r2p0 TRM (PDF copy, binary only). https://WWW.KEIL.COM/dd/docs/datashts/arm/cortex_m3/r2p0/ddi0337g_cortex_m3_r2p0_trm.pdf (fetched as binary, text not extractable)
- ARM DDI0337 (official landing; JS-rendered, not readable). https://support.arm.com/documentation/ddi0337/latest/
- mbed Cortex-M3 instruction summary (redirected, not fetched). https://os.mbed.com/media/uploads/4180_1/cortexm3_instructions.htm
- ST PM0056 Cortex-M3 programming manual (search results only). https://usermanual.wiki/Pdf/stm32cortexm3programmingmanual.416333244/html (403/redirect, not read)

---

## VERIFICADO NO PDF PRIMÁRIO (sessão principal, 2026-10-07 ~23:30)

Fonte: ARM DDI 0337G — *Cortex-M3 Technical Reference Manual*, revision r2p0
(© 2005–2008). PDF salvo em `tmp/research/src/ddi0337g_cortex_m3_r2p0_trm.pdf`
(origem: keil.com/dd/docs/datashts/arm/cortex_m3/r2p0/ddi0337g_cortex_m3_r2p0_trm.pdf).
Texto extraído (PyMuPDF): `tmp/research/src/trm_ch18.txt`, `trm_ch5.txt`.
Bancada: OpenOCD detecta **Cortex-M3 r2p0** → revisão do manual = revisão do núcleo.

### Tabela 18-1 (pp. 18-3 a 18-5, PDF 357–359)
| Classe | Ciclos | Nota |
|---|---|---|
| Data ops 16/32-bit (ADD, EOR, MOV, LSL, ROR, MUL 16-bit…) | 1 (+P se PC destino) | "MUL is one cycle" |
| Branches B/BL/BX/B<cond> | 1+P | nota a: tomado com imediato = 2 ciclos totais; com registrador = 3; não tomado = 1 |
| Load-store single LDR/STR | 2 (nota b) | "two cycles for the first access and one cycle for each additional access. Stores with immediate offsets take one cycle." |
| LDM/STM/PUSH/POP | 1+N | |
| MUL/MLA/MLS 32-bit | 1 ou 2 | MLA/MLS 2 |
| UMULL/SMULL… | 3–7 | early termination; interrompível (abandon/restart) |
| SDIV/UDIV | 2–12 | nota e: depende de dividendo/divisor; mínimo quando divisor > dividendo ou divisor 0; interrompível (abandonado/reiniciado, latência pior caso 1 ciclo) |
| IT, NOP | 0–1 | nota d: IT pode ser "folded" |
| WFI/WFE/SEV | 1+W | |
| ISB/DSB/DMB | 1+B | |
| CBZ | 1+P | |

§18.3 (pp. 18-7/18-8): STR Rx,[Ry,#imm] sempre 1 ciclo (store buffer); LDRs
consecutivas são "pipelined" (−1 ciclo na seguinte) se o destino da primeira não
compõe o endereço da seguinte — ex. "LDR R0,[R1,R5]; LDR R1,[R2]; LDR R2,[R3,#4]
— normally four cycles total"; LDR Rx,[PC,#imm] pode somar 1 ciclo (contenção
com fetch); LDM/STM não pipelinam com vizinhas, elementos após o 1º sim
("three element LDM takes 2+1+1 or 5 cycles" [sic]); LDM/STM interrompidas
continuam (ICI), +1–2 ciclos no reinício.

### Exceções (cap. 5)
- §5.5 Fig. 5-2, p. 5-13 (PDF 109): "there is a 12-cycle latency from asserting the
  interrupt to the first instruction of the ISR executing."
- §5.6, p. 5-14 (PDF 110): tail-chaining — "starts execution six cycles after exiting
  the previous ISR"; ocorre "if a pending interrupt has higher priority than all
  stacked exceptions".
- §5.7, p. 5-15 (PDF 111): late-arriving — pode preemptar "if the first instruction of
  the previous ISR has not entered the Execute stage, and the late-arriving interrupt
  has a higher priority"; sem novo salvamento de estado; após esse ponto = preempção.
- §5.8.1, p. 5-17/18: exit; pop abandonado se exceção de maior prioridade chega
  durante o pop → tratado como tail-chain.
