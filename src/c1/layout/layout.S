/*
 * src/c1/layout/layout.S — rotinas do preset c1-layout que precisam de
 * assembly: leituras guardadas por "falta e retoma", a rotina em .ramfunc
 * (LAY-05) e o tratador de SVC instalado na tabela da SRAM (LAY-06/08).
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

@ uint32_t lay_probe32(uint32_t addr) / lay_probe16: carga com aterrissagem.
@ Se o endereço falhar, o tratador grava a falta e retoma em 9: (r0 fica com
@ a sentinela); o chamador olha c1_fault.count.
.macro PROBE name, op
    .section .text.\name, "ax", %progbits
    .global \name
    .type \name, %function
    .thumb_func
\name:
    ldr     r2, =c1_fault
    adr.w   r3, 9f
    str     r3, [r2, #28]           @ aterrissagem
    mov     r1, r0
    ldr     r0, =0xDEADBEEF
    \op     r0, [r1]
9:  bx      lr
    .size \name, . - \name
    .ltorg
.endm
    PROBE   lay_probe32, ldr
    PROBE   lay_probe16, ldrh

@ LAY-05: rotina com VMA na SRAM e LMA na flash, copiada pelo Reset_Handler.
@ uint32_t lay_ramfunc(uint32_t x, uint32_t *pc_out): devolve 3x + 1 e grava
@ o PC lido por MOV (= endereço da instrução + 4).
    .section .ramfunc.lay_ramfunc, "ax", %progbits
    .global lay_ramfunc, lay_ramfunc_pc
    .type lay_ramfunc, %function
    .thumb_func
lay_ramfunc:
lay_ramfunc_pc:
    mov     r2, pc
    str     r2, [r1]
    add     r0, r0, r0, lsl #1
    adds    r0, r0, #1
    bx      lr
    .size lay_ramfunc, . - lay_ramfunc

@ Tratador de SVC da tabela realocada (LAY-06/08): marca que rodou.
    .section .text.lay_svc_sram, "ax", %progbits
    .global lay_svc_sram
    .type lay_svc_sram, %function
    .thumb_func
    .p2align 2
lay_svc_sram:
    ldr     r0, =lay_svc_marker
    ldr     r1, =0x5AFE
    str     r1, [r0]
    bx      lr
    .size lay_svc_sram, . - lay_svc_sram
    .ltorg
