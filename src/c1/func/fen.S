/*
 * src/c1/func/fen.S — grupo FEN: exceções síncronas e faltas.
 *
 * Quadro de 8 palavras (R0–R3, R12, LR, PC, xPSR), EXC_RETURN em LR
 * (§B1.5.6), alinhamento por CCR.STKALIGN, causas de UsageFault (TRM
 * Tab. 5-10), escalonamento para HardFault, XN e ITSTATE no quadro.
 * Ganchos de SVC: svc.S. Vetores e oráculo: scripts/c1/func/fen.py.
 */
#include "moldes.inc"

/* FEN-01 (MSP) e FEN-02 (PSP): SVC com R0–R3, R12 e LR conhecidos.
 * out = {quadro[8], EXC_RETURN, IPSR, SP antes − quadro, R0–R3, R12, LR
 * depois do retorno} */
.macro SVCFRAME name, psp
FUNC \name
    push    {r4-r8, lr}             @ 6 palavras: SP continua múltiplo de 8
    HOOK    r2, r3, c1_svc_record
    mov     r4, r1                  @ out
    .if \psp
    ldr     r2, =_epsp
    msr     psp, r2
    movs    r2, #2
    msr     control, r2             @ SPSEL = 1: Thread passa a usar o PSP
    isb
    .endif
    ldr     r5, =0x90000000
    msr     APSR_nzcvq, r5          @ N = 1, V = 1
    ldr     r0, =0xA0A0A0A0
    ldr     r1, =0xA1A1A1A1
    ldr     r2, =0xA2A2A2A2
    ldr     r3, =0xA3A3A3A3
    ldr     r12, =0xACACACAC
    ldr     lr, =0xAEAEAEAE
    mov     r6, sp                  @ SP antes do SVC
X \name
    svc     #0
    str     r0, [r4, #44]
    str     r1, [r4, #48]
    str     r2, [r4, #52]
    str     r3, [r4, #56]
    str     r12, [r4, #60]
    str     lr, [r4, #64]
    ldr     r2, [r4, #40]
    sub     r2, r6, r2
    str     r2, [r4, #40]           @ SP antes − endereço do quadro
    .if \psp
    movs    r2, #0
    msr     control, r2
    isb
    .endif
    pop     {r4-r8, pc}
ENDF \name
.endm
    SVCFRAME v_fen01, 0
    SVCFRAME v_fen02, 1

/* FEN-03: SVC dentro do tratador de SVC → HardFault (um SVC não preempta a
 * si mesmo). A aterrissagem é a instrução seguinte ao SVC interno.
 * out = {marcador} + faltas */
FUNC c1_fen03_hook
    push    {r4, lr}
    LAND    r2, r3, 1f
X v_fen03, 1
    svc     #1
1:  pop     {r4, pc}                @ PC = EXC_RETURN: retorno do SVC
ENDF c1_fen03_hook

FUNC v_fen03
    push    {r4, lr}
    HOOK    r2, r3, c1_fen03_hook
    mov.w   r3, #0
X v_fen03, 0
    svc     #0
    mov.w   r3, #1
    str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fen03

/* FEN-04: alinhamento do quadro. in = {STKALIGN, SP mod 8}
 * out = {SP antes − quadro, bit 9 do xPSR empilhado, SP depois − antes} */
FUNC c1_fen04_hook
    ldr     r2, =c1_svc_out
    ldr     r2, [r2]
    mrs     r0, msp
    str     r0, [r2, #0]
    ldr     r3, [r0, #28]
    str     r3, [r2, #4]
    bx      lr
ENDF c1_fen04_hook

FUNC v_fen04
    push    {r4, r5, r6, lr}
    HOOK    r2, r3, c1_fen04_hook
    ldr     r2, [r0, #0]
    cbz     r2, 1f
    CCR_SET r2, r3, 0x200           @ STKALIGN = 1
    b       2f
1:  CCR_CLR r2, r3, 0x200           @ STKALIGN = 0 (reset da r1p1)
2:  ldr     r4, [r0, #4]
    sub     sp, sp, r4              @ SP mod 8 = 0 ou 4
    mov     r5, sp
X v_fen04
    svc     #0
    mov     r6, sp
    add     sp, sp, r4
    ldr     r2, [r1, #0]
    sub     r2, r5, r2
    str     r2, [r1, #0]
    ldr     r2, [r1, #4]
    and     r2, r2, #0x200
    str     r2, [r1, #4]
    sub     r6, r6, r5
    str     r6, [r1, #8]
    pop     {r4, r5, r6, pc}
ENDF v_fen04

/* FEN-05: cada causa de UsageFault, isolada. Instruções que o montador
 * recusa para o M3 entram como palavra crua (codificação do ARMv7E-M).
 * in = {APSR}  out = {} + faltas */
.macro UFAULT name, width, word
FUNC \name
    push    {r4, lr}
    LAND    r2, r3, 9f
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X \name
    .inst.\width \word
9:  pop     {r4, pc}
ENDF \name
.endm
    UFAULT  v_fen05_udf, n, 0xde00          @ UDF #0
    UFAULT  v_fen05_qadd, w, 0xfa81f080     @ QADD r0, r0, r1 (DSP)
    UFAULT  v_fen05_sel, w, 0xfaa1f082      @ SEL r0, r1, r2 (DSP)
    UFAULT  v_fen05_setend, n, 0xb650       @ SETEND LE (TRM Tab. 2-4: sempre falha)
    UFAULT  v_fen05_mrc, w, 0xee100f10      @ MRC p15, 0, r0, c0, c0, 0 → NOCP

/* FEN-05 INVPC (caso TERMINAL, execução própria): o tratador de SVC
 * retorna com EXC_RETURN = 0xFFFFFFF5 (reservado), com SHPR2.PRI_11 = 0x80
 * para que a UsageFault possa preemptar. Sem aterrissagem: o tratador de
 * faltas grava o registro e encerra o run. */
FUNC c1_fen05_hook
    ldr     lr, =0xFFFFFFF5
X v_fen05_invpc, 1
    bx      lr
ENDF c1_fen05_hook

FUNC v_fen05_invpc
    push    {r4, lr}
    HOOK    r2, r3, c1_fen05_hook
    ldr     r2, =0xE000ED1C         @ SHPR2: PRI_11 (SVCall) nos bits [31:24]
    ldr     r3, =0x80000000
    str     r3, [r2]
    dsb
X v_fen05_invpc, 0
    svc     #0
    pop     {r4, pc}                @ não deveria chegar aqui
ENDF v_fen05_invpc

/* FEN-06: escalonamento com USGFAULTENA = 0 → HardFault FORCED, a causa
 * continua no CFSR. in = {APSR}  out = {} + faltas */
FUNC v_fen06_udf
    push    {r4, lr}
    SHCSR_CLR r2, r3, 0x40000
    LAND    r2, r3, 9f
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X v_fen06_udf
    .inst.n 0xde00
9:  pop     {r4, pc}
ENDF v_fen06_udf

FUNC v_fen06_div
    push    {r4, lr}
    SHCSR_CLR r2, r3, 0x40000
    CCR_SET r2, r3, 0x10
    LAND    r2, r3, 9f
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
    mov.w   r3, #0
X v_fen06_div
    udiv    r2, r2, r3
9:  pop     {r4, pc}
ENDF v_fen06_div

/* FEN-07: execução em região XN (periféricos, PPB) com MEMFAULTENA = 1 e 0.
 * in = {alvo | 1, MEMFAULTENA, APSR}  out = {} + faltas. Lote isolado: um
 * ambiente que executasse dados de periférico poderia não voltar. */
FUNC v_fen07
    push    {r4, lr}
    ldr     r2, [r0, #4]
    cbnz    r2, 1f
    SHCSR_CLR r2, r3, 0x10000       @ MEMFAULTENA = 0
1:  LAND    r2, r3, 9f
    ldr     r3, [r0, #8]
    msr     APSR_nzcvq, r3
    ldr     r2, [r0, #0]
X v_fen07
    blx     r2
9:  pop     {r4, pc}
ENDF v_fen07

/* FEN-09: SVC no meio de um bloco IT (Z = 1). O gancho grava o xPSR
 * empilhado: o ITSTATE nele descreve as instruções restantes do bloco.
 * out = {xPSR empilhado, marcador} */
FUNC c1_fen09_hook
    ldr     r2, =c1_svc_out
    ldr     r2, [r2]
    mrs     r0, msp
    ldr     r3, [r0, #28]
    str     r3, [r2, #0]
    bx      lr
ENDF c1_fen09_hook

FUNC v_fen09_a
    push    {r4, lr}
    HOOK    r2, r3, c1_fen09_hook
    movs    r3, #0
    ldr     r2, =0x40000000
    msr     APSR_nzcvq, r2          @ Z = 1
X v_fen09_a
    itt     eq
    svceq   #0                      @ 1ª: executa → SVC
    orreq   r3, r3, #1              @ 2ª: depois do retorno, executa
    str     r3, [r1, #4]
    pop     {r4, pc}
ENDF v_fen09_a

FUNC v_fen09_b
    push    {r4, lr}
    HOOK    r2, r3, c1_fen09_hook
    movs    r3, #0
    ldr     r2, =0x40000000
    msr     APSR_nzcvq, r2
X v_fen09_b
    itte    eq
    svceq   #0
    orreq   r3, r3, #1
    orrne   r3, r3, #2              @ 3ª: pulada (NE falsa)
    str     r3, [r1, #4]
    pop     {r4, pc}
ENDF v_fen09_b
