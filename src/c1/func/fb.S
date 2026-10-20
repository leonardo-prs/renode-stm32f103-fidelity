/*
 * src/c1/func/fb.S — grupo FB: manipulação de bits (nenhuma altera flags).
 * Vetores e oráculo: scripts/c1/func/fb.py.
 */
#include "moldes.inc"

@ FB-01 CLZ; FB-02 RBIT, REV, REV16, REVSH
    VUN     v_fb01_clz, clz r2, r3
    VUN     v_fb02_rbit, rbit r2, r3
    .irp op, rev, rev16, revsh
    VUN     v_fb02_\op\()_t1, \op r2, r3
    VUN     v_fb02_\op\()_t2, \op\().w r2, r3
    .endr
@ FB-03 extensões: T1 (16 bits) e T2 com ROR #0/8/16/24
    .irp op, sxtb, sxth, uxtb, uxth
    VUN     v_fb03_\op\()_t1, \op r2, r3
    VUN     v_fb03_\op\()_t2_0, \op\().w r2, r3
    .irp r, 8, 16, 24
    VUN     v_fb03_\op\()_t2_\r, \op\().w r2, r3, ror #\r
    .endr
    .endr
@ FB-04 UBFX/SBFX; FB-05 BFI/BFC — (lsb, largura) fixos na instrução.
@ BFI: in = {destino, origem, APSR} (molde VBIN: destino em r2, origem em r3).
.macro FB_FIELD lsb, w
    VUN     v_fb04_ubfx_\lsb\()_\w, ubfx r2, r3, #\lsb, #\w
    VUN     v_fb04_sbfx_\lsb\()_\w, sbfx r2, r3, #\lsb, #\w
    VBIN    v_fb05_bfi_\lsb\()_\w, bfi r2, r3, #\lsb, #\w
    VUN     v_fb05_bfc_\lsb\()_\w, bfc r2, #\lsb, #\w
.endm
    .irp lw, "0,1", "0,8", "0,32", "4,8", "28,4", "31,1"
    FB_FIELD \lw
    .endr
