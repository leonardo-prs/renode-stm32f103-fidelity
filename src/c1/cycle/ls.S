/*
 * src/c1/cycle/ls.S — T-LS, T-LSM, T-AL e T-BB (carga/escrita; TRM §18.3).
 * As bases (r0, r1, r2, r3) são preparadas por setup() em main.c antes de
 * cada chamada; ver scripts/c1/cycle/ls.py. Separadora das sequências
 * isoladas: `adds r4, r4, #1` (r7 guarda t0 no esqueleto do bloco).
 */
#include "blocks.inc"

    UNIT1   ldr, ldr r1, [r0]
    BLOCKSET t_ls01, U_ldr
    UNIT1   ldrdep, ldr r0, [r0]
    BLOCKSET t_ls02, U_ldrdep
    UNIT2   ldradd, "ldr r1, [r0]", "adds r2, r2, #1"
    BLOCKSET t_ls03, U_ldradd                       @ e T-LS-10, T-AL-01, T-BB-01
    UNIT2   ldrwbcmp, "ldr r1, [r0], #4", "cmp r7, #0"
    BLOCKSET t_ls04_cmp, U_ldrwbcmp
    UNIT2   ldrwbuse, "ldr r1, [r0], #4", "adds r2, r1, #0"
    BLOCKSET t_ls04_use, U_ldrwbuse
    UNIT2   ldrlit, "ldr r1, =0x12345678", "adds r2, r2, #1"   @ não codificável como imediato: vai ao pool
    BLOCKSET t_ls05, U_ldrlit
    UNIT1   str, str r1, [r0, #0]
    BLOCKSET t_ls06, U_str
    UNIT2   strreg, "str r1, [r0, r2]", "adds r4, r4, #1"
    BLOCKSET t_ls07, U_strreg

@ T-LS-08: os quatro exemplos do TRM §18.3, cada um seguido da separadora.
.macro U_ls08a
    ldr     r0, [r1]
    ldr     r1, [r2]
    adds    r4, r4, #1
.endm
.macro U_ls08b
    ldr     r0, [r1, r2]
    str     r0, [r3, #20]
    adds    r4, r4, #1
.endm
.macro U_ls08c
    ldr     r0, [r1, r2]
    str     r1, [r3, r2]
    adds    r4, r4, #1
.endm
.macro U_ls08d
    ldr     r0, [r1, r5]
    ldr     r1, [r2]
    ldr     r2, [r3, #4]
    adds    r4, r4, #1
.endm
.macro P_R5ZERO n                    @ (d) usa r5 como deslocamento: 0 antes de t0
    mov.w   r5, #0
.endm
    BLOCKSET t_ls08a, U_ls08a
    BLOCKSET t_ls08b, U_ls08b
    BLOCKSET t_ls08c, U_ls08c
    BLOCKSET t_ls08d, U_ls08d, P_R5ZERO

@ T-LS-09: T-LS-01 e T-LS-03 com as outras larguras (formas de 16 bits).
    .irp w, ldrb, ldrh
    UNIT1   \w, \w r1, [r0]
    BLOCKSET t_ls09_\w, U_\w
    UNIT2   \w\()add, "\w r1, [r0]", "adds r2, r2, #1"
    BLOCKSET t_ls09_\w\()_add, U_\w\()add
    .endr
    .irp w, ldrsb, ldrsh
    UNIT1   \w, \w r1, [r0, r2]
    BLOCKSET t_ls09_\w, U_\w
    UNIT2   \w\()add, "\w r1, [r0, r2]", "adds r3, r3, #1"
    BLOCKSET t_ls09_\w\()_add, U_\w\()add
    .endr

@ T-LSM-01/02: N = 2..8 registradores; para N ≥ 5 a lista pula r5–r7
@ (instrumento): {r1-r4, r8, r9, r10, r11}. O custo depende só de N.
    UNIT1   ldm2, ldm.w r0, {r1, r2}
    UNIT1   ldm3, ldm.w r0, {r1-r3}
    UNIT1   ldm4, ldm.w r0, {r1-r4}
    UNIT1   ldm5, ldm.w r0, {r1-r4, r8}
    UNIT1   ldm6, ldm.w r0, {r1-r4, r8-r9}
    UNIT1   ldm7, ldm.w r0, {r1-r4, r8-r10}
    UNIT1   ldm8, ldm.w r0, {r1-r4, r8-r11}
    UNIT1   stm2, stm.w r0, {r1, r2}
    UNIT1   stm3, stm.w r0, {r1-r3}
    UNIT1   stm4, stm.w r0, {r1-r4}
    UNIT1   stm5, stm.w r0, {r1-r4, r8}
    UNIT1   stm6, stm.w r0, {r1-r4, r8-r9}
    UNIT1   stm7, stm.w r0, {r1-r4, r8-r10}
    UNIT1   stm8, stm.w r0, {r1-r4, r8-r11}
    .irp n, 2, 3, 4, 5, 6, 7, 8
    BLOCKSET t_lsm01_\n, U_ldm\n
    BLOCKSET t_lsm02_\n, U_stm\n
    .endr

@ T-LSM-03: PUSH + POP da mesma lista a partir de r4 (r5–r7 voltam intactos).
    UNIT2   pp1, "push {r4}", "pop {r4}"
    UNIT2   pp2, "push {r4-r5}", "pop {r4-r5}"
    UNIT2   pp3, "push {r4-r6}", "pop {r4-r6}"
    UNIT2   pp4, "push {r4-r7}", "pop {r4-r7}"
    UNIT2   pp5, "push {r4-r8}", "pop {r4-r8}"
    UNIT2   pp6, "push {r4-r9}", "pop {r4-r9}"
    UNIT2   pp7, "push {r4-r10}", "pop {r4-r10}"
    UNIT2   pp8, "push {r4-r11}", "pop {r4-r11}"
    .irp n, 1, 2, 3, 4, 5, 6, 7, 8
    BLOCKSET t_lsm03_\n, U_pp\n
    .endr

    UNIT1   ldrd, ldrd r2, r3, [r0]
    BLOCKSET t_lsm04_ldrd, U_ldrd
    UNIT1   strd, strd r2, r3, [r0]
    BLOCKSET t_lsm04_strd, U_strd
    UNIT1   ldrex, ldrex r1, [r0]
    BLOCKSET t_lsm05a, U_ldrex
    UNIT2   ldrexadd, "ldrex r1, [r0]", "adds r4, r4, #1"
    BLOCKSET t_lsm05b, U_ldrexadd
    UNIT2   ldrexstrex, "ldrex r1, [r0]", "strex r2, r1, [r0]"
    BLOCKSET t_lsm05c, U_ldrexstrex

@ T-AL-02 e T-BB-02: escrita (desalinhada ou no alias) + ADDS.
    UNIT2   stradd, "str r1, [r0]", "adds r2, r2, #1"
    BLOCKSET t_al02_str, U_stradd
    UNIT2   strhadd, "strh r1, [r0]", "adds r2, r2, #1"
    BLOCKSET t_al02_strh, U_strhadd
@ T-BB-03: escrita (alias ou comum) seguida de carga da SRAM.
    UNIT2   strldr, "str r1, [r0]", "ldr r2, [r3]"
    BLOCKSET t_bb03, U_strldr
