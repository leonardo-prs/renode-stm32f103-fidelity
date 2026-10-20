/*
 * src/c1/cycle/blocks.inc — o microbenchmark diferencial (material-base,
 * "Como se mede um ciclo").
 *
 * Um BLOCO é uma função  uint32_t t_xxx_<n>(uint32_t regs[13])  que:
 *
 *   1. carrega as flags (regs[10]) e os operandos r0–r4, r8–r12 (regs[0..9])
 *      — flags fixadas ANTES de t0, e nenhuma unidade as altera quando a
 *      unidade tem instrução condicional;
 *   2. executa a preparação opcional do caso (PRE n), ainda fora da janela;
 *   3. lê t0 = DWT_CYCCNT, executa n cópias da UNIDADE (.rept: não há laço
 *      em execução) e lê t1;
 *   4. devolve Δ(n) = t1 − t0 (módulo 2^32) e grava t0/t1 em regs[11..12].
 *
 * r5, r6 e r7 são do instrumento (t1, &CYCCNT, t0). A janela entre t0 e t1
 * contém só as unidades. Três blocos (K = 8, 2K = 16, 3K = 24) por caso:
 * Δ(n) = O + n·c, com o teste de linearidade Δ(3K) − Δ(2K) = Δ(2K) − Δ(K).
 *
 * Alinhamento: a leitura de t0 começa num endereço múltiplo de 4; com
 * ua = 4 ela é de 32 bits (a 1ª unidade fica alinhada à palavra), com
 * ua = 2 é de 16 bits (a 1ª unidade fica em ≡ 2 mod 4). O rótulo
 * <bloco>_x0 marca a 1ª unidade (o gate confere instrução e alinhamento).
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

.macro X name, k=0
    .global \name\()_x\k
\name\()_x\k:
.endm

.macro BLOCK name, n, unit, pre, post, ua=4, sect=.text
    .section \sect\().\name, "ax", %progbits
    .global \name
    .type \name, %function
    .thumb_func
    .p2align 3
\name:
    push    {r4-r11, lr}
    sub     sp, sp, #4              @ 10 palavras: SP múltiplo de 8
    str     r0, [sp, #0]            @ guarda o ponteiro regs
    ldr     r1, [r0, #40]
    msr     APSR_nzcvq, r1          @ flags do caso, antes de t0
    ldm     r0, {r0-r4, r8-r12}     @ operandos
    .ifnb \pre
    \pre    \n
    .endif
    ldr     r6, =0xE0001004         @ &DWT_CYCCNT
    .p2align 2
    .if \ua == 4
    ldr.w   r7, [r6]                @ t0
    .else
    ldr     r7, [r6]                @ t0
    .endif
X \name
    .rept   \n
    \unit
    .endr
    ldr     r5, [r6]                @ t1
    subs    r0, r5, r7              @ Δ(n) = t1 − t0 (módulo 2^32)
    ldr     r1, [sp, #0]
    str     r7, [r1, #44]           @ regs[11] = t0
    str     r5, [r1, #48]           @ regs[12] = t1
    .ifnb \post
    \post
    .endif
    add     sp, sp, #4
    pop     {r4-r11, pc}
    .size \name, . - \name
    .ltorg
.endm

@ Os três tamanhos de um caso.
.macro BLOCKSET name, unit, pre, post, ua=4, sect=.text
    BLOCK   \name\()_8, 8, \unit, \pre, \post, \ua, \sect
    BLOCK   \name\()_16, 16, \unit, \pre, \post, \ua, \sect
    BLOCK   \name\()_24, 24, \unit, \pre, \post, \ua, \sect
.endm

@ Unidade de uma instrução: UNIT1 nome, instrução → macro U_nome.
.macro UNIT1 name, insn:vararg
.macro U_\name
    \insn
.endm
.endm

@ Unidade de duas instruções.
.macro UNIT2 name, a, b
.macro U_\name
    \a
    \b
.endm
.endm
