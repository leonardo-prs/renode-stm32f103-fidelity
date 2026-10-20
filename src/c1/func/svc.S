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

    .section .bss.c1_svc_hook, "aw", %nobits
    .global c1_svc_hook
    .p2align 2
c1_svc_hook:
    .space  4
