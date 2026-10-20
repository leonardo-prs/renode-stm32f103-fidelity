/*
 * src/c1/cycle/fe.S — T-FE (busca de instruções) e T-COMP (composição).
 */
#include "blocks.inc"

@ T-FE-01: ADD.W com a 1ª unidade alinhada à palavra × à meia palavra.
    UNIT1   addw3, add.w r0, r1, r2
    BLOCKSET t_fe01_w, U_addw3, , , 4
    BLOCKSET t_fe01_h, U_addw3, , , 2

@ T-FE-02: os blocos de T-ALU-01, T-ALU-02, T-LS-03 e T-BR-01 executando da
@ SRAM (.ramfunc: LMA na flash, copiados pelo Reset_Handler).
    UNIT1   addsr, adds r0, r0, #1
    BLOCKSET t_fe02_alu01, U_addsr, , , 4, .ramfunc
    UNIT1   addlslr, add.w r0, r1, r2, lsl #3
    BLOCKSET t_fe02_alu02, U_addlslr, , , 4, .ramfunc
    UNIT2   ldraddr, "ldr r1, [r0]", "adds r2, r2, #1"
    BLOCKSET t_fe02_ls03, U_ldraddr, , , 4, .ramfunc
.macro U_bnr
    b.n     1f
1:
.endm
    BLOCKSET t_fe02_br01, U_bnr, , , 4, .ramfunc

@ T-COMP: trechos reais com o laço inteiro como "unidade" (executada uma
@ vez por bloco); o número de iterações n vem de regs (8, 16, 24).
.macro U_copy                        @ T-COMP-01: cópia de palavras
    .p2align 2
1:  ldr.w   r3, [r1], #4
    str.w   r3, [r0], #4
    subs    r2, r2, #1
    bne     1b
.endm
.macro U_crc                         @ T-COMP-02: CRC-32 bit a bit
    .p2align 2
1:  lsrs    r3, r2, #1
    it      cs
    eorcs   r3, r4
    mov     r2, r3
    subs    r1, #1
    bne     1b
.endm
    BLOCK   t_comp01, 1, U_copy
    BLOCK   t_comp02, 1, U_crc
