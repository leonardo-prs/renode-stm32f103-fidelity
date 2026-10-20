/*
 * src/c1/cycle/br.S — T-BR (desvios), T-IT (execução condicional) e T-SYS.
 * Em todo desvio, o alvo de uma unidade é o início da unidade seguinte.
 */
#include "blocks.inc"

.macro U_bn
    b.n     1f
1:
.endm
.macro U_bw
    b.w     1f
1:
.endm
.macro U_bne
    bne.n   1f
1:
.endm
.macro U_beq
    beq.n   1f
1:
.endm
.macro U_cbz
    cbz     r0, 1f
    nop
1:
.endm
.macro U_cbnz
    cbnz    r0, 1f
    nop
1:
.endm
.macro U_bx
    adr.w   r1, 1f + 1              @ BX exige bit 0 = 1 para seguir em Thumb
    bx      r1
1:
.endm
.macro U_bl
    bl      c1_leaf
.endm
.macro U_addpc                      @ r1 = −2: alvo = PC (ADD + 4) − 2 = próxima
    add     pc, r1
.endm
.macro U_movpc
    adr.w   r1, 1f
    mov     pc, r1
1:
.endm
.macro U_ldrpc                      @ r0 percorre a tabela dos alvos (setup)
    ldr     pc, [r0], #4
.endm
.macro U_poppc                      @ a pilha tem os pares (valor, alvo) (P_PAIRS)
    pop     {r4, pc}
.endm
.macro U_tbb
    tbb     [pc, r0]
1:  .byte   (2f - 1b) / 2
    .byte   0
2:
.endm

@ Rotina folha compartilhada por T-BR-07.
    .section .text.c1_leaf, "ax", %progbits
    .global c1_leaf
    .type c1_leaf, %function
    .thumb_func
c1_leaf:
    bx      lr
    .size c1_leaf, . - c1_leaf

@ P_PAIRS n: empilha os n pares de c1_cyc_tab (preparados por setup()) de
@ trás para a frente, para que o 1º POP leve o par 0.
.macro P_PAIRS n
    ldr     r5, =c1_cyc_tab + 8 * \n
    .rept   \n
    ldmdb   r5!, {r6, r7}
    push    {r6, r7}
    .endr
.endm

    BLOCKSET t_br01, U_bn
    BLOCKSET t_br02_w, U_bw, , , 4
    BLOCKSET t_br02_h, U_bw, , , 2
    BLOCKSET t_br03, U_bne
    BLOCKSET t_br04, U_beq
    BLOCKSET t_br05_cbz, U_cbz
    BLOCKSET t_br05_cbnz, U_cbnz
    BLOCKSET t_br06, U_bx
    BLOCKSET t_br07, U_bl
    BLOCKSET t_br08_add, U_addpc
    BLOCKSET t_br08_mov, U_movpc
    BLOCKSET t_br09, U_ldrpc
    BLOCKSET t_br10, U_poppc, P_PAIRS
    BLOCKSET t_br11, U_tbb

@ T-IT
.macro U_it01
    mov     r1, r4
    it      eq
    moveq   r2, r3
.endm
.macro U_it02
    mov.w   r1, r4
    it      eq
    moveq   r2, r3
.endm
.macro U_it03
    it      ne
    movne   r2, r3
.endm
.macro U_it04br                      @ Yiu §23.2: desvio sobre 4 instruções
    cmp     r0, r1
    bne     1f
    movs    r2, #0
    movs    r2, #0
    movs    r2, #0
    movs    r2, #0
1:
.endm
.macro U_it04it                      @ o mesmo com ITTTT
    cmp     r0, r1
    itttt   eq
    moveq   r2, #0
    moveq   r2, #0
    moveq   r2, #0
    moveq   r2, #0
.endm
    BLOCKSET t_it01, U_it01
    BLOCKSET t_it02, U_it02
    BLOCKSET t_it03, U_it03
    BLOCKSET t_it04_br, U_it04br
    BLOCKSET t_it04_it, U_it04it
    UNIT1   nop, nop
    BLOCKSET t_it05, U_nop

@ T-SYS (com PRIMASK = 1 nas medições: nenhuma muda o estado)
    UNIT1   mrspm, mrs r0, primask
    BLOCKSET t_sys01_mrs, U_mrspm
    UNIT1   msrpm, msr primask, r0
    BLOCKSET t_sys01_msr, U_msrpm
    UNIT1   cpsid, cpsid i
    BLOCKSET t_sys01_cpsid, U_cpsid
    UNIT1   isb, isb
    BLOCKSET t_sys02, U_isb
    UNIT1   dmb, dmb
    BLOCKSET t_sys03_dmb, U_dmb
    UNIT1   dsb, dsb
    BLOCKSET t_sys03_dsb, U_dsb
    UNIT2   strdsb, "str r1, [r0]", "dsb"
    BLOCKSET t_sys03_str, U_strdsb
    UNIT1   sev, sev
    BLOCKSET t_sys04, U_sev

@ Diagnóstico de T-BR-03 e T-BR-06 (fora do intervalo do TRM): as mesmas
@ unidades com a 1ª unidade em ≡ 2 (mod 4).
    BLOCKSET t_br03_h, U_bne, , , 2
    BLOCKSET t_br06_h, U_bx, , , 2
