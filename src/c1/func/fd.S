/*
 * src/c1/func/fd.S — grupo FD: divisão.
 *
 * Divisor zero dá 0, sem falta, salvo com CCR.DIV_0_TRP = 1 (UsageFault
 * DIVBYZERO); arredonda para zero; 0x80000000 / -1 = 0x80000000
 * (§A7.7.127, §A7.7.195). Vetores e oráculo: scripts/c1/func/fd.py.
 */
#include "moldes.inc"

@ FD-01/FD-02 (e FD-04: flags inalteradas)
    VBIN    v_fd01_udiv, udiv r2, r2, r3
    VBIN    v_fd02_sdiv, sdiv r2, r2, r3

@ FD-03 divisão por zero com DIV_0_TRP = 1: in = {dividendo, APSR}
@ out = {Rd}. Rd é pré-carregado com uma sentinela: a instrução que falha
@ não completa, então Rd deve continuar 0xDEADBEEF.
    .irp op, udiv, sdiv
FUNC v_fd03_\op
    push    {r4, lr}
    CCR_SET r3, r4, 0x10            @ CCR.DIV_0_TRP (precondição do caso)
    LAND    r3, r4, 1f
    ldr     r4, [r0, #4]
    msr     APSR_nzcvq, r4
    ldr     r2, =0xDEADBEEF         @ sentinela no destino
    ldr     r3, [r0, #0]            @ dividendo
    mov.w   r4, #0                  @ divisor zero (MOV sem S: flags intactas)
X v_fd03_\op
    \op     r2, r3, r4              @ <- UsageFault DIVBYZERO
1:  str     r2, [r1, #0]            @ aterrissagem
    pop     {r4, pc}
ENDF v_fd03_\op
    .endr
