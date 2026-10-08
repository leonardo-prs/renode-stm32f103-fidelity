/*
 * lib/fidelity_measure.S — bracket de medição imune ao compilador.
 *
 *   uint32_t fidelity_measure(FidelityFn fn, uint32_t a, uint32_t b,
 *                             FidelityMeasure *out);
 *     FidelityFn = uint32_t (*)(uint32_t a, uint32_t b)
 *     out->ret = fn(a, b); out->t0 = DWT antes; devolve ticks (t1 − t0).
 *
 * O bracket é SEMPRE: LDR CYCCNT → BLX fn → (corpo) → retorno → LDR CYCCNT.
 * Em C, uma chamada a função "pure" pode ser movida pelo GCC -O2 para fora
 * de duas leituras volatile (observado em S1B); aqui a ordem é fixa no
 * assembly e o custo do bracket é idêntico para toda medição (o laço vazio
 * / carga "empty" o mede).
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.fidelity_measure, "ax", %progbits
    .global fidelity_measure
    .type fidelity_measure, %function
    .thumb_func
    .p2align 2
fidelity_measure:
    push    {r4-r7, lr}
    mov     r4, r0              @ fn
    mov     r5, r3              @ out
    mov     r0, r1              @ a
    mov     r1, r2              @ b
    ldr     r6, =0xE0001004     @ DWT->CYCCNT
    ldr     r7, [r6]            @ t0
    blx     r4
    ldr     r2, [r6]            @ t1
    str     r0, [r5]            @ out->ret
    str     r7, [r5, #4]        @ out->t0
    subs    r0, r2, r7          @ ticks
    pop     {r4-r7, pc}
    .size fidelity_measure, . - fidelity_measure
    .ltorg
