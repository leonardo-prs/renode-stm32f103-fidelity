/*
 * src/c1/cycle/dwt.S — T-DWT: validar o DWT_CYCCNT como régua, antes de
 * medir qualquer instrução (material-base, @sec-tdwt). A linearidade
 * (T-DWT-04) usa os blocos de T-ALU-01 (alu.S).
 */
#include "blocks.inc"

@ T-DWT-03 e T-DWT-05: bloco vazio, Δ(0) = custo das duas leituras.
    BLOCK   t_dwt_empty, 0, , , , 4

@ T-DWT-02: escreve 0xFFFFFFF0 no CYCCNT antes de t0; 24 ADDS dão a volta.
.macro P_WRAP n
    ldr     r5, =0xE0001004
    ldr     r7, =0xFFFFFFF0
    str     r7, [r5]
.endm
    UNIT1   adds1, adds r0, r0, #1
    BLOCKSET t_dwt02, U_adds1, P_WRAP

@ T-DWT-06: exceção dentro da janela (tratador de SVC vazio, bx lr).
    UNIT1   svc0, svc 0
    BLOCKSET t_dwt06, U_svc0
