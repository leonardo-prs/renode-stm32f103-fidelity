/*
 * src/c1/func/fex.S — grupo FEX: acesso exclusivo (§A3.4).
 *
 * STREX escreve só se o monitor local estiver em Exclusive Access e devolve
 * 0 (escreveu) ou 1 (não escreveu). O monitor volta a Open Access com CLREX,
 * com qualquer STREX e, no ARMv7-M, em TODA entrada ou saída de exceção
 * (§A3.4.4) — a regra de que depende o registrador de eventos dos demais
 * cenários. Alvo: c1_scratch + 12. Oráculo: scripts/c1/func/fex.py.
 */
#include "moldes.inc"

@ in = {valor antigo, valor novo}  out = {carregado, status[, status2], memória} + janela
.macro EXSETUP
    push    {r4, lr}
    ldr     r2, =c1_scratch + 12
    ldr     r3, [r0, #0]
    str     r3, [r2]
    ldr     r4, [r0, #4]
    mov.w   r3, #0
    mov.w   r12, #0xFF
.endm
.macro EXEND off
    ldr     r2, [r2]
    str     r2, [r1, #\off]
    pop     {r4, pc}
.endm

FUNC v_fex01                        @ LDREX; STREX → 0, memória nova
    EXSETUP
X v_fex01, 0
    ldrex   r3, [r2]
X v_fex01, 1
    strex   r12, r4, [r2]
    str     r3, [r1, #0]
    str     r12, [r1, #4]
    EXEND   8
ENDF v_fex01

FUNC v_fex02                        @ (CLREX garante Open) STREX → 1
    EXSETUP
    clrex
X v_fex02
    strex   r12, r4, [r2]
    str     r3, [r1, #0]
    str     r12, [r1, #4]
    EXEND   8
ENDF v_fex02

FUNC v_fex03                        @ LDREX; CLREX; STREX → 1
    EXSETUP
    ldrex   r3, [r2]
X v_fex03
    clrex
    strex   r12, r4, [r2]
    str     r3, [r1, #0]
    str     r12, [r1, #4]
    EXEND   8
ENDF v_fex03

FUNC v_fex04                        @ LDREX; SVC (tratador vazio); STREX → 1
    EXSETUP
    ldrex   r3, [r2]
X v_fex04
    svc     #0
    strex   r12, r4, [r2]
    str     r3, [r1, #0]
    str     r12, [r1, #4]
    EXEND   8
ENDF v_fex04

FUNC v_fex05                        @ LDREX; STREX → 0; STREX → 1
    EXSETUP
    ldrex   r3, [r2]
    strex   r12, r4, [r2]
    str     r12, [r1, #4]
    add     r4, r4, #1
X v_fex05
    strex   r12, r4, [r2]
    str     r3, [r1, #0]
    str     r12, [r1, #8]
    EXEND   12
ENDF v_fex05

@ FEX-06: byte e meia palavra (carga estende com zero; escrita só na largura)
.macro EXNARROW name, ld, st
FUNC \name
    EXSETUP
X \name, 0
    \ld     r3, [r2]
X \name, 1
    \st     r12, r4, [r2]
    str     r3, [r1, #0]
    str     r12, [r1, #4]
    EXEND   8
ENDF \name
.endm
    EXNARROW v_fex06_b, ldrexb, strexb
    EXNARROW v_fex06_h, ldrexh, strexh
