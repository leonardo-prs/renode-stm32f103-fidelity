/*
 * src/c1/common/fault.S — "falta e retoma" (material-base, cap. Método).
 *
 * Tratador ÚNICO de HardFault, MemManage, BusFault e UsageFault. Um caso que
 * DEVE falhar publica antes, em c1_fault.landing, o endereço de instrução
 * em que o experimento continua (a aterrissagem). O tratador:
 *
 *   1. grava CFSR, HFSR, MMFAR, BFAR (lidos ANTES de limpar), PC e xPSR
 *      empilhados, EXC_RETURN, IPSR e incrementa o contador de faltas;
 *   2. limpa CFSR e HFSR escrevendo 1 nos bits lidos (W1C: PM0056 §4.4.10,
 *      ARM ARM §B3.2.16) — sem isso o caso seguinte herdaria os bits;
 *   3. troca o PC empilhado pela aterrissagem com bit 0 = 0 (o PC empilhado é
 *      endereço de instrução: bit 0 = 1 tornaria o retorno UNPREDICTABLE,
 *      §B1.5.8 PopStack), põe T = 1 e zera o ITSTATE no xPSR empilhado
 *      (bits [26:25] e [15:10]): PC, T e ITSTATE ficam coerentes (§B1.5.6);
 *      o bit 9 (ajuste de alinhamento do quadro) é preservado;
 *   4. apaga a aterrissagem (uso único) e retorna com o EXC_RETURN recebido.
 *
 * Aterrissagem vazia = falta INESPERADA (ou caso terminal): o registro fica
 * gravado e c1_fault_stop (c1.c) decide. Todo caso com falta roda com a pilha
 * principal (MSP), então o quadro está sempre no MSP.
 *
 * O tratador só acessa a SRAM e o SCB, que não falham: uma falta dentro do
 * HardFault levaria a lockup (PM0056 §2.4.4).
 *
 * Gancho opcional (c1_fault_hook): se não nulo, é chamado ANTES do registro,
 * no próprio modo Handler da falta. Só um caso o usa (FSY-03 (b): CPSID F
 * dentro do HardFault); main o zera depois de cada vetor.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .text.c1_fault_entry, "ax", %progbits
    .global c1_fault_entry
    .type c1_fault_entry, %function
    .thumb_func
c1_fault_entry:
    ldr     r1, =c1_fault_hook
    ldr     r1, [r1]
    cbz     r1, 1f
    push    {r4, lr}                    @ preserva EXC_RETURN (e o alinhamento)
    blx     r1
    pop     {r4, lr}
1:  mrs     r0, msp                     @ r0 = quadro (casos com falta usam só MSP)
    ldr     r1, =c1_fault
    ldr     r2, =0xE000ED28             @ r2 = &CFSR
    ldr     r3, [r2, #0]
    str     r3, [r1, #0]                @ CFSR
    ldr     r3, [r2, #4]
    str     r3, [r1, #4]                @ HFSR   (0xE000ED2C)
    ldr     r3, [r2, #12]
    str     r3, [r1, #8]                @ MMFAR  (0xE000ED34), antes de limpar
    ldr     r3, [r2, #16]
    str     r3, [r1, #12]               @ BFAR   (0xE000ED38), antes de limpar
    ldr     r3, [r0, #24]
    str     r3, [r1, #16]               @ PC empilhado
    ldr     r3, [r0, #28]
    str     r3, [r1, #20]               @ xPSR empilhado
    str     lr, [r1, #24]               @ EXC_RETURN
    mrs     r3, ipsr
    str     r3, [r1, #32]               @ exceção que atendeu (3 = HardFault, 4..6)
    ldr     r3, [r1, #36]
    adds    r3, r3, #1
    str     r3, [r1, #36]               @ contador: o host espera exatamente 1
    ldr     r3, [r1, #0]
    str     r3, [r2, #0]                @ limpa CFSR (1 nos bits lidos)
    ldr     r3, [r1, #4]
    str     r3, [r2, #4]                @ limpa HFSR (idem)
    ldr     r3, [r1, #28]               @ aterrissagem publicada pelo caso
    cbz     r3, c1_fault_unexpected     @ vazia: falta inesperada ou caso terminal
    bic     r3, r3, #1                  @ PC empilhado sempre com bit 0 = 0
    str     r3, [r0, #24]
    ldr     r3, [r0, #28]
    ldr     r2, =0x0600FC00             @ ITSTATE no xPSR: [26:25] e [15:10]
    bic     r3, r3, r2                  @ a aterrissagem fica fora de bloco IT
    orr     r3, r3, #0x01000000         @ T = 1 (estado Thumb)
    str     r3, [r0, #28]
    movs    r3, #0
    str     r3, [r1, #28]               @ aterrissagem é de uso único
    bx      lr                          @ retorno de exceção normal
c1_fault_unexpected:
    b       c1_fault_stop               @ c1.c: terminal → resultado; senão inválido
    .size c1_fault_entry, . - c1_fault_entry
    .ltorg

/*
 * Exceções que o C1 nunca provoca (NMI, PendSV, SysTick, IRQs): grava o
 * número da exceção e encerra o run como EVIDÊNCIA INVÁLIDA.
 */
    .section .text.c1_unexpected_irq, "ax", %progbits
    .global c1_unexpected_irq
    .type c1_unexpected_irq, %function
    .thumb_func
c1_unexpected_irq:
    ldr     r1, =c1_snapshot
    mrs     r0, ipsr
    str     r0, [r1, #(27 * 4)]         @ header.fault_ipsr
    movs    r0, #(1 << 7)               @ C1_ERR_IRQ
    b       c1_fail
    .size c1_unexpected_irq, . - c1_unexpected_irq
    .ltorg
