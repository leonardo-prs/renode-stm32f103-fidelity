/*
 * src/c1/func/fbb.S — grupo FBB: bit-band (TRM §4.2, RM0008 §3.3.2).
 *
 * alias = base_alias + deslocamento_do_byte × 32 + bit × 4; escrever no alias
 * faz ler-modificar-escrever do bit usando só o bit 0 do valor; ler devolve
 * 0 ou 1. Todos os vetores têm aterrissagem: se um ambiente não mapear o
 * alias, a BusFault vira dado, e o run continua. Oráculo: scripts/c1/func/fbb.py.
 */
#include "moldes.inc"

@ ALIAS rd, raddr, rbit: rd = 0x22000000 + (raddr − 0x20000000)·32 + rbit·4
.macro ALIAS rd, raddr, rbit
    sub     \rd, \raddr, #0x20000000
    lsl     \rd, \rd, #5
    add     \rd, \rd, \rbit, lsl #2
    add     \rd, \rd, #0x22000000
.endm

/* FBB-01: escrita no alias do byte c1_scratch + 13. in = {byte inicial, bit,
 * valor escrito}  out = {byte depois} + janela + faltas */
FUNC v_fbb01
    push    {r4, lr}
    LAND    r2, r3, 9f
    ldr     r2, =c1_scratch + 13
    ldr     r3, [r0, #0]
    strb    r3, [r2]
    ldr     r3, [r0, #4]
    ALIAS   r4, r2, r3
    ldr     r3, [r0, #8]
X v_fbb01
    str     r3, [r4]
LANDING v_fbb01
9:  ldrb    r3, [r2]
    str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fbb01

/* FBB-02: leitura do alias. in = {byte, bit}  out = {lido} + faltas */
FUNC v_fbb02
    push    {r4, lr}
    LAND    r2, r3, 9f
    ldr     r2, =c1_scratch + 13
    ldr     r3, [r0, #0]
    strb    r3, [r2]
    ldr     r3, [r0, #4]
    ALIAS   r4, r2, r3
    ldr     r3, =0xDEADBEEF
X v_fbb02
    ldr     r3, [r4]
LANDING v_fbb02
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fbb02

/* FBB-03: a fórmula nos endereços fixos do RM0008 e dos extremos da SRAM
 * (alias explícito no vetor). O byte é salvo, recebe 0x5A, o bit é ligado e
 * desligado pelo alias e o byte original é restaurado (o endereço pode ser
 * de dados vivos: snapshot ou topo da pilha, sem uso durante a rotina).
 * in = {endereço, alias}  out = {byte com o bit ligado, byte com o bit
 * desligado} + faltas */
FUNC v_fbb03
    push    {r4, r5, r6, lr}
    LAND    r2, r3, 9f
    ldr     r2, [r0, #0]
    ldr     r4, [r0, #4]
    ldrb    r5, [r2]                @ byte original
    movs    r3, #0x5A
    strb    r3, [r2]
    movs    r3, #1
    mov.w   r6, #0xDEAD
X v_fbb03, 0
    str     r3, [r4]
    ldrb    r6, [r2]
    str     r6, [r1, #0]
    movs    r3, #0
X v_fbb03, 1
    str     r3, [r4]
LANDING v_fbb03
9:  ldrb    r6, [r2]
    str     r6, [r1, #4]
    strb    r5, [r2]                @ restaura
    pop     {r4, r5, r6, pc}
ENDF v_fbb03

/* FBB-04: alias de periférico. Liga o relógio do GPIOB pelo alias de
 * RCC_APB2ENR.IOPBEN (0x4242030C), alterna GPIOB_ODR[5] pelo alias
 * 0x42218194, e restaura. PB5 fica como entrada (CRL de reset): a escrita
 * no ODR não muda pino algum. out = {APB2ENR, ODR com bit, ODR sem bit,
 * APB2ENR restaurado} + faltas */
FUNC v_fbb04
    push    {r4, r5, r6, lr}
    LAND    r2, r3, 9f
    ldr     r4, =0x40021018         @ RCC_APB2ENR
    ldr     r5, =0x40010C0C         @ GPIOB_ODR
    ldr     r2, =0x4242030C
    ldr     r6, =0x42218194
    mov.w   r3, #1
X v_fbb04, 0
    str     r3, [r2]                @ IOPBEN = 1 (alias)
    dsb
    ldr     r12, [r4]
    str     r12, [r1, #0]
X v_fbb04, 1
    str     r3, [r6]                @ ODR5 = 1 (alias)
    ldr     r12, [r5]
    str     r12, [r1, #4]
    mov.w   r3, #0
    str     r3, [r6]                @ ODR5 = 0
    ldr     r12, [r5]
    str     r12, [r1, #8]
    str     r3, [r2]                @ IOPBEN = 0
    dsb
    ldr     r12, [r4]
LANDING v_fbb04
9:  str     r12, [r1, #12]
    pop     {r4, r5, r6, pc}
ENDF v_fbb04

/* FBB-05: acesso direto (não alias) a 0x20000300 = SRAM comum. O valor é
 * salvo e restaurado. in = {valor}  out = {lido} */
FUNC v_fbb05
    push    {r4, lr}
    ldr     r2, =0x20000300
    ldr     r4, [r2]
    ldr     r3, [r0, #0]
X v_fbb05
    str     r3, [r2]
    ldr     r3, [r2]
    str     r3, [r1, #0]
    str     r4, [r2]
    pop     {r4, pc}
ENDF v_fbb05
