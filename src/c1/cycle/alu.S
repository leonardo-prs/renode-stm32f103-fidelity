/*
 * src/c1/cycle/alu.S — T-ALU (dados), T-MUL e T-DIV (TRM r1p1 Tab. 18-1).
 * Operandos: r0–r4, r8–r12 vêm de regs[] (definidos no catálogo).
 */
#include "blocks.inc"

    UNIT1   adds1, adds r0, r0, #1
    BLOCKSET t_alu01, U_adds1                       @ e T-DWT-01/04
    UNIT1   addlsl, add.w r0, r1, r2, lsl #3
    BLOCKSET t_alu02, U_addlsl
    UNIT2   movwt, "movw r0, #0x1234", "movt r0, #0x5678"
    BLOCKSET t_alu03, U_movwt
    UNIT1   lslreg, lsl.w r0, r1, r2
    BLOCKSET t_alu04, U_lslreg
    UNIT1   clz, clz r0, r1
    BLOCKSET t_alu05_clz, U_clz
    UNIT1   rbit, rbit r0, r1
    BLOCKSET t_alu05_rbit, U_rbit
    UNIT1   rev, rev r0, r1
    BLOCKSET t_alu05_rev, U_rev
    UNIT1   uxtbw, uxtb.w r0, r1
    BLOCKSET t_alu05_uxtb, U_uxtbw
    UNIT1   ubfx, ubfx r0, r1, #4, #8
    BLOCKSET t_alu05_ubfx, U_ubfx
    UNIT1   bfi, bfi r0, r1, #4, #8
    BLOCKSET t_alu05_bfi, U_bfi
    UNIT1   ssat, ssat r0, #8, r1
    BLOCKSET t_alu06, U_ssat
    UNIT1   adddep, adds r0, r0, r1
    BLOCKSET t_alu07_dep, U_adddep
    UNIT1   addind, adds r2, r0, r1
    BLOCKSET t_alu07_ind, U_addind

    UNIT1   mul, mul r2, r0, r1
    BLOCKSET t_mul01, U_mul
    UNIT1   mla, mla r2, r0, r1, r3
    BLOCKSET t_mul02_mla, U_mla
    UNIT1   mls, mls r2, r0, r1, r3
    BLOCKSET t_mul02_mls, U_mls
    UNIT1   umull, umull r2, r3, r0, r1
    BLOCKSET t_mul03_umull, U_umull
    UNIT1   smull, smull r2, r3, r0, r1
    BLOCKSET t_mul03_smull, U_smull
    UNIT1   umlal, umlal r2, r3, r0, r1
    BLOCKSET t_mul04_umlal, U_umlal
    UNIT1   smlal, smlal r2, r3, r0, r1
    BLOCKSET t_mul04_smlal, U_smlal

    UNIT1   udiv, udiv r2, r0, r1
    BLOCKSET t_div01, U_udiv
    UNIT1   sdiv, sdiv r2, r0, r1
    BLOCKSET t_div02, U_sdiv
