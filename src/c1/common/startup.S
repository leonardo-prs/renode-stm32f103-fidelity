/*
 * src/c1/common/startup.S — tabela de vetores e Reset_Handler do C1.
 *
 * Substitui o startup do vendor (que chama SystemInit, e o SystemInit
 * escreve no VTOR). Aqui as PRIMEIRAS instruções depois do reset gravam o
 * estado do núcleo e do SCB em c1_reset_capture (.noinit), antes de
 * qualquer escrita (casos FID-03 e FID-04). Só depois disso vem a
 * inicialização comum: copia .data e .ramfunc da flash para a SRAM, zera
 * .bss e chama main (sequência do TRM r1p1, Tab. 5-8).
 *
 * Offsets de c1_reset_capture: ver C1ResetCapture em c1.h.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

/* ─────────────────────────── tabela de vetores ─────────────────────────── */
    .section .isr_vector, "a", %progbits
    .global c1_vectors
    .type c1_vectors, %object
c1_vectors:
    .word   _estack                 @  0: SP inicial (MSP)
    .word   Reset_Handler           @  1
    .word   NMI_Handler             @  2
    .word   HardFault_Handler       @  3
    .word   MemManage_Handler       @  4
    .word   BusFault_Handler        @  5
    .word   UsageFault_Handler      @  6
    .word   0, 0, 0, 0              @  7..10: reservados
    .word   SVC_Handler             @ 11
    .word   DebugMon_Handler        @ 12
    .word   0                       @ 13: reservado
    .word   PendSV_Handler          @ 14
    .word   SysTick_Handler         @ 15
    .rept   43                      @ 16..58: IRQ0..IRQ42 (densidade média)
    .word   c1_unexpected_irq
    .endr
    .size c1_vectors, . - c1_vectors

/* Faltas: um tratador único (fault.S). Demais exceções: inesperadas. */
    .thumb_set HardFault_Handler,  c1_fault_entry
    .thumb_set MemManage_Handler,  c1_fault_entry
    .thumb_set BusFault_Handler,   c1_fault_entry
    .thumb_set UsageFault_Handler, c1_fault_entry
    .weak NMI_Handler, DebugMon_Handler, PendSV_Handler, SysTick_Handler
    .thumb_set NMI_Handler,      c1_unexpected_irq
    .thumb_set DebugMon_Handler, c1_unexpected_irq
    .thumb_set PendSV_Handler,   c1_unexpected_irq
    .thumb_set SysTick_Handler,  c1_unexpected_irq
/* SVC: cada preset pode definir o seu; o padrão é o tratador vazio. */
    .weak SVC_Handler
    .thumb_set SVC_Handler, c1_svc_empty

/* ───────────────────────────── Reset_Handler ───────────────────────────── */
    .section .text.Reset_Handler, "ax", %progbits
    .global Reset_Handler
    .type Reset_Handler, %function
    .thumb_func
Reset_Handler:
    ldr     r0, =c1_reset_capture   @ .noinit: a inicialização não toca
    str     lr, [r0, #0]            @ LR no reset (B1.5.5: 0xFFFFFFFF)
    mov     r1, sp
    str     r1, [r0, #4]            @ SP = palavra 0 da tabela AND ~3
    mrs     r1, control
    str     r1, [r0, #8]
    mrs     r1, primask
    str     r1, [r0, #12]
    mrs     r1, faultmask
    str     r1, [r0, #16]
    mrs     r1, basepri
    str     r1, [r0, #20]
    mrs     r1, ipsr
    str     r1, [r0, #24]
    ldr     r2, =0xE000ED00         @ base do SCB
    ldr     r1, [r2, #0x08]
    str     r1, [r0, #28]           @ VTOR
    ldr     r1, [r2, #0x0C]
    str     r1, [r0, #32]           @ AIRCR (leitura inclui VECTKEYSTAT)
    ldr     r1, [r2, #0x10]
    str     r1, [r0, #36]           @ SCR
    ldr     r1, [r2, #0x14]
    str     r1, [r0, #40]           @ CCR
    ldr     r1, [r2, #0x18]
    str     r1, [r0, #44]           @ SHPR1
    ldr     r1, [r2, #0x1C]
    str     r1, [r0, #48]           @ SHPR2
    ldr     r1, [r2, #0x20]
    str     r1, [r0, #52]           @ SHPR3
    ldr     r1, [r2, #0x24]
    str     r1, [r0, #56]           @ SHCSR
    ldr     r1, [r2, #0x28]
    str     r1, [r0, #60]           @ CFSR
    ldr     r1, [r2, #0x2C]
    str     r1, [r0, #64]           @ HFSR
    ldr     r2, =0xE0001000
    ldr     r1, [r2]
    str     r1, [r0, #68]           @ DWT_CTRL
    ldr     r2, =0xE000EDFC
    ldr     r1, [r2]
    str     r1, [r0, #72]           @ DEMCR (o depurador pode ter escrito)
    ldr     r2, =0x40022000
    ldr     r1, [r2]
    str     r1, [r0, #76]           @ FLASH_ACR
    ldr     r2, =0x40021000
    ldr     r1, [r2, #0]
    str     r1, [r0, #80]           @ RCC_CR
    ldr     r1, [r2, #4]
    str     r1, [r0, #84]           @ RCC_CFGR
    ldr     r1, [r0, #88]
    adds    r1, r1, #1
    str     r1, [r0, #88]           @ contador de boots (sem significado no 1º)
    ldr     r1, =0x31545352
    str     r1, [r0, #92]           @ C1_RESET_MAGIC: captura completa

    @ .data e .ramfunc: cópia LMA (flash) → VMA (SRAM), palavra a palavra
    ldr     r0, =_sdata
    ldr     r1, =_edata
    ldr     r2, =_sidata
    bl      c1_copy_words
    ldr     r0, =_sramfunc
    ldr     r1, =_eramfunc
    ldr     r2, =_siramfunc
    bl      c1_copy_words
    @ .bss: zera
    ldr     r0, =_sbss
    ldr     r1, =_ebss
    movs    r2, #0
1:  cmp     r0, r1
    bhs     2f
    str     r2, [r0], #4
    b       1b
2:  bl      main
3:  b       3b                      @ main nunca retorna (c1_finish)
    .size Reset_Handler, . - Reset_Handler

@ c1_copy_words(dst = r0, end = r1, src = r2)
    .type c1_copy_words, %function
    .thumb_func
c1_copy_words:
1:  cmp     r0, r1
    bhs     2f
    ldr     r3, [r2], #4
    str     r3, [r0], #4
    b       1b
2:  bx      lr
    .size c1_copy_words, . - c1_copy_words
    .ltorg

/* Tratador de SVC vazio (padrão): só retorna. */
    .section .text.c1_svc_empty, "ax", %progbits
    .global c1_svc_empty
    .type c1_svc_empty, %function
    .thumb_func
c1_svc_empty:
    bx      lr
    .size c1_svc_empty, . - c1_svc_empty

/* Captura do reset: .noinit (não zerada; ver c1.ld). */
    .section .noinit.c1_reset_capture, "aw", %nobits
    .global c1_reset_capture
    .type c1_reset_capture, %object
    .p2align 2
c1_reset_capture:
    .space  96
    .size c1_reset_capture, . - c1_reset_capture
