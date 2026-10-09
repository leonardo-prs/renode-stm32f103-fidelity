/*
 * lib/fidelity_measure.S — bracket de medição com ordem fixa.
 *
 *   uint32_t fid_measure(FidFn fn, uint32_t a, uint32_t b, FidSpan *out);
 *     FidFn = uint32_t (*)(uint32_t a, uint32_t b)
 *     out->result = fn(a, b); out->t0 = CYCCNT antes; devolve t1 - t0.
 *
 * Intervalo medido (o mesmo para toda carga):
 *     ldr r7,[r6]  →  blx r4  →  (corpo de fn)  →  bx lr  →  ldr r2,[r6]
 * Em C, o GCC -O2 pode mover uma chamada a função sem efeitos colaterais
 * para fora de duas leituras volatile do contador; em assembly a ordem é
 * garantida. O custo fixo do bracket (LDR + BLX + retorno) é medido pela
 * carga vazia do C1 e reportado, não subtraído às cegas.
 *
 * AAPCS: o SP deve estar alinhado a 8 bytes em toda chamada pública.
 * Entramos alinhados (o chamador cumpre o AAPCS) e empilhamos 6 registros
 * (24 bytes: r3 entra só como enchimento), mantendo o alinhamento no BLX.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.fid_measure, "ax", %progbits
    .global fid_measure
    .type fid_measure, %function
    .thumb_func
    .p2align 2
fid_measure:
    push    {r3, r4, r5, r6, r7, lr}    @ 24 bytes: SP continua múltiplo de 8
    mov     r4, r0                      @ fn
    mov     r5, r3                      @ out
    mov     r0, r1                      @ a
    mov     r1, r2                      @ b
    ldr     r6, =0xE0001004             @ &DWT->CYCCNT
    ldr     r7, [r6]                    @ t0
    blx     r4
    ldr     r2, [r6]                    @ t1
    str     r0, [r5]                    @ out->result
    str     r7, [r5, #4]                @ out->t0
    subs    r0, r2, r7                  @ ticks = t1 - t0 (módulo 2^32)
    pop     {r3, r4, r5, r6, r7, pc}
    .size fid_measure, . - fid_measure
    .ltorg
