/*
 * src/q01/startup.S — vetores e Reset_Handler do firmware Q-01.
 *
 * Só o necessário: copia .data, zera .bss e chama main. SVC e PendSV são os
 * tratadores com pontos marcados (q01.S); qualquer outra exceção cai em
 * q01_fault, que o coletor também observa por gancho (execução inválida).
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .isr_vector, "a", %progbits
    .global q01_vectors
q01_vectors:
    .word   _estack                 @  0: MSP inicial
    .word   Reset_Handler           @  1
    .rept   9                       @  2..10: NMI, faltas, reservados
    .word   q01_fault
    .endr
    .word   SVC_Handler             @ 11
    .word   q01_fault               @ 12: DebugMon
    .word   q01_fault               @ 13: reservado
    .word   PendSV_Handler          @ 14
    .rept   44                      @ 15: SysTick; 16..58: IRQ0..IRQ42
    .word   q01_fault
    .endr

    .text
    .global Reset_Handler
    .type Reset_Handler, %function
    .thumb_func
Reset_Handler:
    ldr     r0, =_sdata
    ldr     r1, =_edata
    ldr     r2, =_sidata
1:  cmp     r0, r1
    bhs     2f
    ldr     r3, [r2], #4
    str     r3, [r0], #4
    b       1b
2:  ldr     r0, =_sbss
    ldr     r1, =_ebss
    movs    r3, #0
3:  cmp     r0, r1
    bhs     4f
    str     r3, [r0], #4
    b       3b
4:  bl      main
    b       q01_fault
    .size Reset_Handler, . - Reset_Handler

/* Rótulo simples (sem .thumb_func): o símbolo vale o endereço exato, que é
 * onde o coletor põe o gancho. */
    .global q01_fault
    .type q01_fault, %function
    .thumb_func
q01_fault:
    b       q01_fault
    .size q01_fault, . - q01_fault
    .ltorg
