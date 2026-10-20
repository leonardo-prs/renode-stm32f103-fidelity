/*
 * src/c1/func/fal.S — grupo FAL: acesso desalinhado.
 *
 * LDR/LDRH/LDRSH/STR/STRH aceitam endereço desalinhado (a matriz de
 * barramento quebra o acesso, TRM Tab. 14-2), salvo com CCR.UNALIGN_TRP = 1;
 * LDM/STM/LDRD/STRD/LDREX* exigem alinhamento SEMPRE (§A3.2.1).
 * Vetores e oráculo: scripts/c1/func/fal.py.
 */
#include "moldes.inc"

@ Janela com bytes 0x80..0x9F (o byte k vale 0x80 + k): o valor lido identifica
@ exatamente os endereços acessados, e o bit 7 ligado exercita a extensão de sinal.
.macro RAMP
    ldr     r12, =c1_scratch
    ldr     r2, =0x83828180
    ldr     r3, =0x04040404
    str     r2, [r12, #0]
    add     r2, r2, r3
    str     r2, [r12, #4]
    add     r2, r2, r3
    str     r2, [r12, #8]
    add     r2, r2, r3
    str     r2, [r12, #12]
    add     r2, r2, r3
    str     r2, [r12, #16]
    add     r2, r2, r3
    str     r2, [r12, #20]
    add     r2, r2, r3
    str     r2, [r12, #24]
    add     r2, r2, r3
    str     r2, [r12, #28]
.endm

/* FAL-01 (UNALIGN_TRP = 0) e FAL-03 (UNALIGN_TRP = 1): base = c1_scratch + 8,
 * deslocamento r4 do vetor. in = {deslocamento, APSR}  out = {Rt} + janela
 * (+ registro de faltas em FAL-03). Rt começa com a sentinela 0xDEADBEEF. */
.macro UNAL name, trp, insn:vararg
FUNC \name
    push    {r4, lr}
    RAMP
    .if \trp
    CCR_SET r2, r3, 0x08            @ CCR.UNALIGN_TRP (precondição de FAL-03)
    .endif
    LAND    r2, r3, 9f
    add     r2, r12, #8
    ldr     r4, [r0, #0]
    ldr     r3, [r0, #4]
    msr     APSR_nzcvq, r3
    ldr     r3, =0xDEADBEEF
    .ifc \insn,str
    ldr     r3, =0xDDCCBBAA
    .endif
X \name
    \insn   r3, [r2, r4]
LANDING \name
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm
    .irp op, ldr, ldrh, ldrsh, str, strh
    UNAL    v_fal01_\op, 0, \op
    UNAL    v_fal03_\op, 1, \op
    .endr

/* FAL-02: desalinhado na flash (c1_rom, FMEM-07). in = {deslocamento}
 * out = {Rt} */
    .irp op, ldr, ldrh
FUNC v_fal02_\op
    push    {r4, lr}
    ldr     r2, =c1_rom
    ldr     r4, [r0, #0]
X v_fal02_\op
    \op     r3, [r2, r4]
    str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fal02_\op
    .endr

/* FAL-04: instruções que SEMPRE exigem alinhamento, com UNALIGN_TRP = 0 e
 * = 1 (in = {trp, APSR}). Endereço = c1_scratch + 2 (ou + 1 no LDREXH).
 * out = {Rt} + registro de faltas. */
.macro ALIGNED name, off, insn:vararg
FUNC \name
    push    {r4, lr}
    RAMP
    ldr     r2, [r0, #0]
    cbz     r2, 1f
    CCR_SET r2, r3, 0x08
1:  LAND    r2, r3, 9f
    add     r2, r12, #\off
    ldr     r3, [r0, #4]
    msr     APSR_nzcvq, r3
    ldr     r3, =0xDEADBEEF
X \name
    \insn
LANDING \name
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm
    ALIGNED v_fal04_ldm, 2, ldm r2, {r3, r4}
    ALIGNED v_fal04_stm, 2, stm r2!, {r3}
    ALIGNED v_fal04_ldrd, 2, ldrd r3, r4, [r2]
    ALIGNED v_fal04_strd, 2, strd r3, r4, [r2]
    ALIGNED v_fal04_ldrex, 2, ldrex r3, [r2]
    ALIGNED v_fal04_ldrexh, 1, ldrexh r3, [r2]
