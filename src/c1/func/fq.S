/*
 * src/c1/func/fq.S — grupo FQ: saturação.
 *
 * SSAT #n limita a [-2^(n-1), 2^(n-1)-1], USAT #n a [0, 2^n-1]; saturou →
 * Q = 1, e Q é pegajosa (só MSR a zera). NZCV inalterados (§A7.7.152,
 * §A7.7.213). Vetores e oráculo: scripts/c1/func/fq.py.
 */
#include "moldes.inc"

@ FQ-01 SSAT #n; FQ-02 USAT #n
    .irp n, 1, 8, 16, 31, 32
    VUN     v_fq01_ssat_\n, ssat r2, #\n, r3
    .endr
    .irp n, 0, 1, 8, 16, 31
    VUN     v_fq02_usat_\n, usat r2, #\n, r3
    .endr
@ FQ-03 deslocamento antes de saturar
    .irp k, 1, 4, 31
    VUN     v_fq03_ssat_lsl_\k, ssat r2, #8, r3, lsl #\k
    VUN     v_fq03_ssat_asr_\k, ssat r2, #8, r3, asr #\k
    VUN     v_fq03_usat_lsl_\k, usat r2, #8, r3, lsl #\k
    VUN     v_fq03_usat_asr_\k, usat r2, #8, r3, asr #\k
    .endr

@ FQ-04 Q pegajosa: zera Q → satura → não satura → lê; MSR com bit 27 = 0.
@ in = {dummy}   out = {APSR após saturar, APSR após não saturar, APSR após MSR}
FUNC v_fq04_sticky
    push    {r4, lr}
    movs    r2, #0
    msr     APSR_nzcvq, r2          @ Q = 0 (e NZCV = 0)
    mov.w   r3, #300
X v_fq04_sticky, 0
    ssat    r2, #8, r3              @ 300 → 127: satura, Q = 1
    mrs     r4, APSR
    str     r4, [r1, #0]
    movs    r3, #5
    mov.w   r2, #0                  @ (MOVS acima zera N/Z; Q fica)
X v_fq04_sticky, 1
    ssat    r2, #8, r3              @ 5 → 5: não satura; Q continua 1
    mrs     r4, APSR
    str     r4, [r1, #4]
    mov.w   r2, #0
    msr     APSR_nzcvq, r2          @ escrita explícita com bit 27 = 0
    mrs     r4, APSR
    str     r4, [r1, #8]
    pop     {r4, pc}
ENDF v_fq04_sticky
