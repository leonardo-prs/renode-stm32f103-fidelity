/*
 * src/c1/func/fsy.S — grupo FSY: registradores especiais e privilégio
 * (MRS/MSR, §B5.2.2–3; CPS, §B5.2.1). Ganchos de SVC: svc.S.
 * Vetores e oráculo: scripts/c1/func/fsy.py.
 */
#include "moldes.inc"

/* FSY-01: MSR APSR_nzcvq + MRS APSR. in = {valor}  out = {lido} */
FUNC v_fsy01
    push    {r4, lr}
    ldr     r2, [r0, #0]
X v_fsy01, 0
    msr     APSR_nzcvq, r2
X v_fsy01, 1
    mrs     r3, APSR
    str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fsy01

/* FSY-02: IPSR, EPSR e xPSR em Thread e no tratador de SVC.
 * in = {APSR}  out = {IPSR, EPSR, xPSR em Thread; IPSR, EPSR, xPSR no SVC} */
FUNC c1_fsy02_hook
    ldr     r2, =c1_svc_out
    ldr     r2, [r2]
X v_fsy02, 3
    mrs     r3, ipsr
    str     r3, [r2, #12]
X v_fsy02, 4
    mrs     r3, epsr
    str     r3, [r2, #16]
X v_fsy02, 5
    mrs     r3, xpsr
    str     r3, [r2, #20]
    bx      lr
ENDF c1_fsy02_hook

FUNC v_fsy02
    push    {r4, lr}
    HOOK    r2, r3, c1_fsy02_hook
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X v_fsy02, 0
    mrs     r3, ipsr
    str     r3, [r1, #0]
X v_fsy02, 1
    mrs     r3, epsr
    str     r3, [r1, #4]
X v_fsy02, 2
    mrs     r3, xpsr
    str     r3, [r1, #8]
    svc     #0
    pop     {r4, pc}
ENDF v_fsy02

/* FSY-03: PRIMASK/FAULTMASK por MSR e por CPSID/CPSIE em Thread.
 * out = {PM após MSR 1, MSR 0, CPSID, CPSIE; FM idem} */
.macro READMASK reg, off
    mrs     r3, \reg
    str     r3, [r1, #\off]
.endm
FUNC v_fsy03_thread
    push    {r4, lr}
    movs    r2, #1
X v_fsy03_thread, 0
    msr     primask, r2
    READMASK primask, 0
    movs    r2, #0
    msr     primask, r2
    READMASK primask, 4
X v_fsy03_thread, 1
    cpsid   i
    READMASK primask, 8
X v_fsy03_thread, 2
    cpsie   i
    READMASK primask, 12
    movs    r2, #1
    msr     faultmask, r2
    READMASK faultmask, 16
    movs    r2, #0
    msr     faultmask, r2
    READMASK faultmask, 20
X v_fsy03_thread, 3
    cpsid   f
    READMASK faultmask, 24
X v_fsy03_thread, 4
    cpsie   f
    READMASK faultmask, 28
    pop     {r4, pc}
ENDF v_fsy03_thread

/* (a) CPSID F dentro do tratador de SVC; o retorno de exceção limpa
 * FAULTMASK (§B1.5.8). out = {FM no tratador, FM em Thread depois} */
FUNC c1_fsy03a_hook
    ldr     r2, =c1_svc_out
    ldr     r2, [r2]
X v_fsy03_ret, 0
    cpsid   f
    mrs     r3, faultmask
    str     r3, [r2, #0]
    bx      lr
ENDF c1_fsy03a_hook

FUNC v_fsy03_ret
    push    {r4, lr}
    HOOK    r2, r3, c1_fsy03a_hook
    svc     #0
    READMASK faultmask, 4
    pop     {r4, pc}
ENDF v_fsy03_ret

/* (b) CPSID F dentro do HardFault (UDF com USGFAULTENA = 0, como FEN-06):
 * a prioridade de execução já é −1, a escrita é ignorada (§B5.2.1).
 * out = {FM lido no HardFault} + faltas */
FUNC c1_fsy03b_hook
    ldr     r2, =c1_svc_out
    ldr     r2, [r2]
X v_fsy03_hf, 1
    cpsid   f
    mrs     r3, faultmask
    str     r3, [r2, #0]
    bx      lr
ENDF c1_fsy03b_hook

FUNC v_fsy03_hf
    push    {r4, lr}
    ldr     r2, =c1_svc_out
    str     r1, [r2]
    ldr     r2, =c1_fault_hook
    ldr     r3, =c1_fsy03b_hook
    str     r3, [r2]
    SHCSR_CLR r2, r3, 0x40000       @ USGFAULTENA = 0: a UDF escala para HardFault
    LAND    r2, r3, 9f
    mov.w   r3, #0xFF
    str     r3, [r1, #0]
X v_fsy03_hf, 0
    .inst.n 0xde00                  @ UDF #0
9:  pop     {r4, pc}
ENDF v_fsy03_hf

/* FSY-04: BASEPRI (só os bits [7:4] existem no STM32) e BASEPRI_MAX.
 * out = {0xFF → ?, de 0x40: MAX 0x80, MAX 0x20, MAX 0; de 0: MAX 0x80} */
FUNC v_fsy04
    push    {r4, lr}
    movs    r2, #0xFF
X v_fsy04, 0
    msr     basepri, r2
    READMASK basepri, 0
    movs    r2, #0x40
    msr     basepri, r2
    movs    r2, #0x80
X v_fsy04, 1
    msr     basepri_max, r2
    READMASK basepri, 4
    movs    r2, #0x20
    msr     basepri_max, r2
    READMASK basepri, 8
    movs    r2, #0
    msr     basepri_max, r2
    READMASK basepri, 12
    movs    r2, #0
    msr     basepri, r2
    movs    r2, #0x80
    msr     basepri_max, r2
    READMASK basepri, 16
    movs    r2, #0
    msr     basepri, r2
    pop     {r4, pc}
ENDF v_fsy04

/* FSY-05: MSP e PSP com valores alinhados a 4 (escrever bits [1:0] ≠ 0 é
 * UNPREDICTABLE, §A5.1.3: excluído). Nada usa a pilha entre a escrita e a
 * restauração do MSP. in = {valor}  out = {MSP lido, PSP lido} */
FUNC v_fsy05
    push    {r4, lr}
    ldr     r2, [r0, #0]
    mov     r12, sp
X v_fsy05, 0
    msr     msp, r2
X v_fsy05, 1
    mrs     r3, msp
    msr     msp, r12
    str     r3, [r1, #0]
    mrs     r4, psp
X v_fsy05, 2
    msr     psp, r2
    mrs     r3, psp
    msr     psp, r4
    str     r3, [r1, #4]
    pop     {r4, pc}
ENDF v_fsy05

/* FSY-06: CONTROL.SPSEL = 1 em Thread: o SP em uso passa a ser o PSP.
 * out = {SP visto, PSP lido, palavra empilhada, SP após o PUSH, MSP depois − antes} */
FUNC v_fsy06
    push    {r4, r5, r6, lr}
    ldr     r2, =_epsp
    msr     psp, r2
    mrs     r5, msp
    movs    r2, #2
X v_fsy06, 0
    msr     control, r2
    isb
    mov     r3, sp
    str     r3, [r1, #0]
    mrs     r3, psp
    str     r3, [r1, #4]
    ldr     r4, =0xC0FFEE00
    push    {r4}                    @ vai para a área do PSP
    ldr     r3, =_epsp - 4
    ldr     r3, [r3]
    str     r3, [r1, #8]
    mov     r3, sp
    str     r3, [r1, #12]
    pop     {r4}
    movs    r2, #0
    msr     control, r2
    isb
    mrs     r6, msp
    sub     r6, r6, r5
    str     r6, [r1, #16]
    pop     {r4, r5, r6, pc}
ENDF v_fsy06

/* FSY-07: Thread sem privilégio (nPRIV = 1): MSR em máscaras e CONTROL e
 * CPSID são ignorados, MRS das máscaras lê 0; volta ao privilégio por SVC.
 * out = {CONTROL, PRIMASK, BASEPRI, FAULTMASK, PRIMASK após CPSID, CONTROL
 * após MSR 0 — sem privilégio; CONTROL, PRIMASK, BASEPRI, FAULTMASK — de
 * volta ao privilégio} */
FUNC c1_fsy07_hook                  @ tratador: limpa CONTROL.nPRIV
    mrs     r2, control
    bic     r2, r2, #1
    msr     control, r2
    bx      lr
ENDF c1_fsy07_hook

FUNC v_fsy07
    push    {r4, lr}
    HOOK    r2, r3, c1_fsy07_hook
    movs    r2, #1
    msr     control, r2
    isb
    READMASK control, 0
    movs    r2, #1
X v_fsy07, 0
    msr     primask, r2
    READMASK primask, 4
    movs    r2, #0x80
    msr     basepri, r2
    READMASK basepri, 8
    movs    r2, #1
    msr     faultmask, r2
    READMASK faultmask, 12
X v_fsy07, 1
    cpsid   i
    READMASK primask, 16
    movs    r2, #0
X v_fsy07, 2
    msr     control, r2
    isb
    READMASK control, 20
    svc     #0
    isb
    READMASK control, 24
    READMASK primask, 28
    READMASK basepri, 32
    READMASK faultmask, 36
    pop     {r4, pc}
ENDF v_fsy07

/* FSY-08 (= FEN-08): LDR do SCB em Thread sem privilégio → BusFault precisa
 * (PRECISERR + BFARVALID, BFAR = endereço). in = {APSR}  out = {Rt} + faltas */
FUNC v_fsy08
    push    {r4, lr}
    HOOK    r2, r3, c1_fsy07_hook
    LAND    r2, r3, 9f
    movs    r2, #1
    msr     control, r2
    isb
    ldr     r2, =0xE000ED00
    ldr     r3, [r0, #0]
    msr     APSR_nzcvq, r3
    ldr     r3, =0xDEADBEEF
X v_fsy08
    ldr     r3, [r2]
9:  svc     #0                      @ de volta ao privilégio
    isb
    str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fsy08
