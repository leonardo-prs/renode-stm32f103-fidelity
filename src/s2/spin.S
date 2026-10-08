/*
 * src/s2/spin.S — S2A: laços de fundo com mix de instruções controlado.
 *
 *   void s2_spin_X(S2Work *w)   — roda até w->stop != 0.
 * Cada iteração: incrementa w->count (LDR/ADDS/STR), executa o corpo da
 * classe e testa w->stop (LDR/CMP/BEQ). A ISR amostra w->count: iterações
 * por período = trabalho da CPU entre dois eventos do timer.
 *
 * S2Work (palavras): [0] count  [1] stop  [2..7] dados p/ LDM/UDIV.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .macro SPIN name, setup, body
    .section .text.\name, "ax", %progbits
    .global \name
    .type \name, %function
    .thumb_func
    .p2align 4
\name:
    push    {r4-r7, lr}
    \setup
    .p2align 3
1:
    ldr     r1, [r0]
    adds    r1, r1, #1
    str     r1, [r0]
    .rept 8
    \body
    .endr
    ldr     r2, [r0, #4]
    cmp     r2, #0
    beq     1b
    pop     {r4-r7, pc}
    .size \name, . - \name
    .endm

/* 8 × ADDS (1 ciclo cada no HW). */
SPIN s2_spin_alu,  "movs r3, #0", "adds r3, r3, r1"
/* 8 × UDIV lento (0xFFFFFFFF/3: 12 ciclos no HW, interrompível). */
SPIN s2_spin_div,  "ldr r6, [r0, #8]; ldr r7, [r0, #12]", "udiv r5, r6, r7"
/* 8 × LDM de 4 palavras (5 ciclos no HW, continuável). */
SPIN s2_spin_ldm,  "add r3, r0, #16", "ldm r3, {r4-r7}"
