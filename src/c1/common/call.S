/*
 * src/c1/common/call.S — chamada com rótulos fixos para o traço por stepi.
 *
 *   uint32_t c1_call(uintptr_t fn, uint32_t a, uint32_t b)  →  fn(a, b)
 *
 * Toda rotina de teste (vetor funcional ou bloco temporal) é chamada por
 * aqui. O host (scripts/c1/trace.py) põe um hbreak em c1_call_go e executa
 * stepi até chegar em c1_call_back: a sequência de PCs entre os dois rótulos
 * é exatamente o que a rotina executou, inclusive o tratador de faltas
 * quando o caso provoca uma (nível de instrução, cap. Método).
 *
 * AAPCS: entramos com SP múltiplo de 8 e empilhamos 2 registradores.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.c1_call, "ax", %progbits
    .global c1_call
    .type c1_call, %function
    .thumb_func
    .p2align 2
c1_call:
    push    {r4, lr}
    mov     r4, r0                      @ fn
    mov     r0, r1                      @ a
    mov     r1, r2                      @ b
    .global c1_call_go
c1_call_go:
    blx     r4
    .global c1_call_back
c1_call_back:
    pop     {r4, pc}
    .size c1_call, . - c1_call
