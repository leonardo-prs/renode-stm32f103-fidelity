/*
 * src/c1/func/fa.S — grupo FA: aritmética e flags (AddWithCarry, §A2.2.1).
 *
 * Uma rotina por codificação (16 e 32 bits passam por caminhos de
 * decodificação diferentes no simulador) e, nas formas com imediato, uma
 * por constante (o imediato faz parte da instrução). Vetores e oráculo:
 * scripts/c1/func/fa.py.
 */
#include "moldes.inc"

@ FA-01 ADDS registrador: T1 (16 bits) e T3 (.W)
    VBIN    v_fa01_t1, adds r2, r2, r3
    VBIN    v_fa01_t3, adds.w r2, r2, r3
@ FA-02 ADCS registrador: T1 (Rdn, 16 bits) e T2
    VBIN    v_fa02_t1, adcs r2, r3
    VBIN    v_fa02_t2, adcs.w r2, r2, r3
@ FA-03 SUBS registrador: T1 e T2
    VBIN    v_fa03_t1, subs r2, r2, r3
    VBIN    v_fa03_t2, subs.w r2, r2, r3
@ FA-04 SBCS registrador: T1 (Rdn) e T2
    VBIN    v_fa04_t1, sbcs r2, r3
    VBIN    v_fa04_t2, sbcs.w r2, r2, r3
@ FA-05 RSBS: imediato T1 (só #0, o NEGS), imediato T2 (constante
@ modificada) e registrador (só existe em 32 bits). Rd = Rm − Rn.
    VUN     v_fa05_i1, rsbs r2, r2, #0
    VUN     v_fa05_i2_0, rsbs.w r2, r2, #0
    .irp c, 0xab, 0xab00ab, 0xab00ab00, 0xabababab, 0x80000000, 0xff0
    VUN     v_fa05_i2_\c, rsbs.w r2, r2, #\c
    .endr
    VBIN    v_fa05_r, rsbs r2, r2, r3
@ FA-06 CMP/CMN: registrador T1, CMP com registrador alto (T2), CMP.W (T3),
@ CMN.W; imediatos: CMP T1 (imm8), CMP.W e CMN.W (constante modificada).
    VFLG2   v_fa06_cmp_t1, cmp r2, r3
    VFLG2   v_fa06_cmn_t1, cmn r2, r3
    VFLG2   v_fa06_cmp_t3, cmp.w r2, r3
    VFLG2   v_fa06_cmn_t2, cmn.w r2, r3
FUNC v_fa06_cmp_t2                  @ CMP T2: Rn alto (r8); r8 é callee-saved
    push    {r4, r8}
    ldr     r2, [r0, #8]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    mov     r8, r2
    ldr     r3, [r0, #4]
X v_fa06_cmp_t2
    cmp     r8, r3
    mrs     r4, APSR
    str     r4, [r1, #0]
    pop     {r4, r8}
    bx      lr
ENDF v_fa06_cmp_t2
    .irp c, 0, 1, 7, 255
    VFLG1   v_fa06_cmpi_t1_\c, cmp r2, #\c
    .endr
    .irp c, 0xab, 0xab00ab, 0xab00ab00, 0xabababab, 0x80000000, 0xff0
    VFLG1   v_fa06_cmpi_t2_\c, cmp.w r2, #\c
    VFLG1   v_fa06_cmni_\c, cmn.w r2, #\c
    .endr
@ FA-07 ADD.W, SUB.W, ADDW, SUBW sem S: flags inalteradas
    VBIN    v_fa07_add, add.w r2, r2, r3
    VBIN    v_fa07_sub, sub.w r2, r2, r3
    VUN     v_fa07_addw, addw r2, r2, #0xfff
    VUN     v_fa07_subw, subw r2, r2, #0xfff
@ FA-08 ADDS/SUBS imediato: imm3 (T1), imm8 (T2, Rdn), constante modificada (T3)
    .irp c, 0, 1, 7
    VUN     v_fa08_adds_t1_\c, adds.n r2, r3, #\c
    VUN     v_fa08_subs_t1_\c, subs.n r2, r3, #\c
    .endr
    .irp c, 0, 1, 7, 255
    VUN     v_fa08_adds_t2_\c, adds.n r2, #\c
    VUN     v_fa08_subs_t2_\c, subs.n r2, #\c
    .endr
    .irp c, 0xab, 0xab00ab, 0xab00ab00, 0xabababab, 0x80000000, 0xff0
    VUN     v_fa08_adds_t3_\c, adds.w r2, r3, #\c
    VUN     v_fa08_subs_t3_\c, subs.w r2, r3, #\c
    .endr
