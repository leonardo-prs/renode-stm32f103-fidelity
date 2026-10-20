/*
 * src/c1/func/svc.S — tratador de SVC do preset c1-func.
 *
 * Por padrão é o tratador VAZIO (só retorna), como pedem FEX-04 e T-DWT-06.
 * Um caso que precisa observar o lado do tratador (FEN-01..04, FEN-09,
 * FSY-02/03/07) instala uma rotina em c1_svc_hook; o desvio é por BX, então
 * a rotina roda como se fosse o próprio tratador: LR = EXC_RETURN e SP no
 * quadro empilhado. main zera o gancho depois de cada vetor.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.SVC_Handler, "ax", %progbits
    .global SVC_Handler
    .type SVC_Handler, %function
    .thumb_func
SVC_Handler:
    ldr     r3, =c1_svc_hook
    ldr     r3, [r3]
    cbz     r3, 1f
    bx      r3                          @ gancho = tratador (LR, SP intactos)
1:  bx      lr                          @ tratador vazio
    .size SVC_Handler, . - SVC_Handler
    .ltorg

/*
 * c1_svc_record: gancho genérico (FEN-01, FEN-02). Grava em c1_svc_out:
 *   [0..7] o quadro empilhado (R0–R3, R12, LR, PC, xPSR), lido do MSP ou do
 *   PSP conforme EXC_RETURN[2]; [8] EXC_RETURN; [9] IPSR; [10] endereço do
 *   quadro (a rotina o converte em SP antes − quadro).
 */
    .section .text.c1_svc_record, "ax", %progbits
    .global c1_svc_record
    .type c1_svc_record, %function
    .thumb_func
c1_svc_record:
    ldr     r2, =c1_svc_out
    ldr     r2, [r2]
    tst     lr, #4
    ite     eq
    mrseq   r0, msp
    mrsne   r0, psp
    .set k, 0
    .rept 8
    ldr     r3, [r0, #(k * 4)]
    str     r3, [r2, #(k * 4)]
    .set k, k + 1
    .endr
    str     lr, [r2, #32]
    mrs     r3, ipsr
    str     r3, [r2, #36]
    str     r0, [r2, #40]
    bx      lr
    .size c1_svc_record, . - c1_svc_record
    .ltorg

    .section .bss.c1_svc_hook, "aw", %nobits
    .global c1_svc_hook, c1_svc_out
    .p2align 2
c1_svc_hook:
    .space  4
c1_svc_out:                         @ ponteiro out do vetor corrente (para os ganchos)
    .space  4
