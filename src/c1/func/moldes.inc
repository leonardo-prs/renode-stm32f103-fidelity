/*
 * src/c1/func/moldes.inc — moldes dos casos funcionais (material-base,
 * "Anatomia de um caso funcional").
 *
 * Toda rotina de vetor tem a mesma assinatura C:
 *     void v_xxx(const uint32_t *in, volatile uint32_t *out);   (r0, r1)
 * e as mesmas quatro etapas: (1) estado inicial (flags via MSR, operandos
 * via LDR, que não alteram flags); (2) A INSTRUÇÃO SOB TESTE, marcada pelo
 * rótulo global <rotina>_x<k>; (3) estado final (MRS APSR); (4) grava as
 * saídas BRUTAS em out[]. Quem julga é o host (scripts/c1).
 *
 * O rótulo _x<k> serve a duas coisas: o gate confere no disassembly que
 * ali está exatamente a instrução, a largura e os operandos declarados no
 * catálogo; e, nos casos de falta, ele é o PC empilhado esperado.
 *
 * MSR APSR_nzcvq escreve só os bits [31:27]; APSR_g nunca é usado (sem DSP
 * seria UNPREDICTABLE, §B5.2.3). MRS APSR lê zeros fora de [31:27].
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

@ Ponto de teste: <rotina>_x<k> marca a instrução sob teste.
.macro X name, k=0
    .global \name\()_x\k
\name\()_x\k:
.endm

.macro FUNC name
    .section .text.\name, "ax", %progbits
    .global \name
    .type \name, %function
    .thumb_func
    .p2align 2
\name:
.endm

.macro ENDF name
    .size \name, . - \name
    .ltorg
.endm

@ VBIN: in = {Rn, Rm, APSR}   out = {Rd, APSR}.   Rn → r2, Rm → r3, Rd = r2.
.macro VBIN name, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, [r0, #8]            @ 1. flags iniciais (NZCVQ)
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]            @    operandos (LDR não altera flags)
    ldr     r3, [r0, #4]
X \name
    \insn                           @ 2. a instrução sob teste
    mrs     r4, APSR                @ 3. flags finais
    str     r2, [r1, #0]            @ 4. saídas brutas
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm

@ VUN: in = {x, APSR}   out = {Rd, APSR}.   x → r2 e r3, Rd = r2.
.macro VUN name, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, [r0, #4]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    mov     r3, r2
X \name
    \insn
    mrs     r4, APSR
    str     r2, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm

@ VFLG2: in = {Rn, Rm, APSR}   out = {APSR}   (comparações: nada é escrito).
.macro VFLG2 name, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, [r0, #8]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    ldr     r3, [r0, #4]
X \name
    \insn
    mrs     r4, APSR
    str     r4, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm

@ VFLG1: in = {x, APSR}   out = {APSR}.   x → r2.
.macro VFLG1 name, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, [r0, #4]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
X \name
    \insn
    mrs     r4, APSR
    str     r4, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm

@ VACC: in = {Rn, Rm, Ra, APSR}   out = {Rd, APSR}.   Rn → r2, Rm → r3, Ra → r4.
.macro VACC name, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, [r0, #12]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    ldr     r3, [r0, #4]
    ldr     r4, [r0, #8]
X \name
    \insn
    mrs     r4, APSR
    str     r2, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm

@ VLONG: in = {Rn, Rm, RdLo, RdHi, APSR}   out = {RdLo, RdHi, APSR}.
@ Rn → r2, Rm → r3, RdLo → r4, RdHi → r5 (acumulador inicial de UMLAL/SMLAL).
.macro VLONG name, insn:vararg
FUNC \name
    push    {r4, r5, r6, lr}
    ldr     r2, [r0, #16]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    ldr     r3, [r0, #4]
    ldr     r4, [r0, #8]
    ldr     r5, [r0, #12]
X \name
    \insn
    mrs     r6, APSR
    str     r4, [r1, #0]
    str     r5, [r1, #4]
    str     r6, [r1, #8]
    pop     {r4, r5, r6, pc}
ENDF \name
.endm

@ LAND t1, t2, alvo: publica a aterrissagem (endereço de instrução do rótulo)
@ para "falta e retoma". O tratador força o bit 0 = 0 ao copiá-la para o PC.
.macro LAND t1, t2, target
    ldr     \t1, =c1_fault
    adr.w   \t2, \target
    str     \t2, [\t1, #28]
.endm

@ CCR_SET / CCR_CLR bits: altera o CCR (precondição declarada do caso; o
@ main restaura o CCR de referência depois de cada vetor).
.macro CCR_SET t1, t2, bits
    ldr     \t1, =0xE000ED14
    ldr     \t2, [\t1]
    orr     \t2, \t2, #\bits
    str     \t2, [\t1]
    dsb
    isb
.endm
