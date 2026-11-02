/*
 * src/q01/q01.S — sequência medida do caso Q-01 (03-quadro-comum.typ,
 * "Verificação do observador externo").
 *
 * Cada ponto marcado q01_pN é um LDR do DWT_CYCCNT seguido do STR do valor
 * no vetor q01_cyc (cursor em r2). O coletor põe um gancho do Renode no
 * endereço do LDR: o gancho roda ANTES do LDR executar e registra o tempo
 * virtual e o PC. O traço de execução do Renode conta as instruções entre
 * dois LDRs. Todo ponto tem a mesma forma, então a convenção de instante
 * (antes/depois do LDR, quando o Renode sincroniza o tempo) se cancela nas
 * DIFERENÇAS entre pontos, que são o que o caso compara.
 *
 * Os segmentos entre pontos cobrem formas de fluxo que o C2 vai usar:
 * linha reta, laço com desvio, chamada, acessos à memória (SRAM, SCB,
 * flash), IT com instruções puladas, exceção síncrona (SVC) e exceção
 * pendente por software (PendSV), com ponto DENTRO de cada tratador.
 *
 * Registradores: r0 = &DWT_CYCCNT e r2 = cursor durante toda a sequência.
 * Os tratadores usam r0/r2 do contexto interrompido (a entrada de exceção
 * não os altera, ARMv7-M B1.5.6) e gravam r2+4 no quadro empilhado, para o
 * cursor avançar qualquer que seja a instrução em que a exceção entrou.
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .equ DWT_CYCCNT, 0xE0001004
    .equ SCB_CPUID,  0xE000ED00
    .equ SCB_ICSR,   0xE000ED04
    .equ PENDSVSET,  (1 << 28)

/* Ponto marcado na thread. */
.macro POINT n
    .global q01_p\n
q01_p\n:
    ldr     r1, [r0]
    str     r1, [r2], #4
.endm

/* Ponto marcado como primeira instrução de um tratador: r2+4 vai para o
 * slot de r2 no quadro empilhado (MSP, 8 palavras: r0 r1 r2 r3 r12 lr pc
 * xPSR), e o retorno da exceção restaura o cursor já avançado. */
.macro POINT_HANDLER n
    .global q01_p\n
q01_p\n:
    ldr     r1, [r0]
    str     r1, [r2], #4
    str     r2, [sp, #8]
.endm

    .text
    .global q01_seq
    .type q01_seq, %function
    .thumb_func
q01_seq:                            @ uint32_t *q01_seq(uint32_t *cursor)
    push    {r4, lr}
    mov     r2, r0
    ldr     r0, =DWT_CYCCNT
    POINT   0
    POINT   1                       @ S01 vazio: só o STR do ponto anterior
    .rept   16
    nop
    .endr
    POINT   2                       @ S02 linha reta: 16 NOPs
    movs    r3, #10
1:  subs    r3, #1
    bne     1b
    POINT   3                       @ S03 laço curto: 10 voltas
    bl      q01_leaf
    POINT   4                       @ S04 chamada e retorno (BL/BX LR)
    ldr     r3, =q01_scratch
    ldr     r4, [r3]
    str     r4, [r3, #4]
    ldr     r4, =SCB_CPUID
    ldr     r4, [r4]
    ldr     r4, =0x5a5aa5a5         @ literal na flash
    POINT   5                       @ S05 memória: SRAM, SCB, flash
    cmp     r3, r3
    it      ne
    addne   r4, #1                  @ pulada (condição falsa)
    ite     eq
    addeq   r4, #1
    addne   r4, #2                  @ pulada
    POINT   6                       @ S06 blocos IT com instruções puladas
    svc     #0                      @ → q01_p7 no tratador
    POINT   8                       @ S07/S08 entrada e retorno do SVC
    ldr     r3, =SCB_ICSR
    ldr     r1, =PENDSVSET
    str     r1, [r3]
    dsb
    isb                             @ PendSV entra até aqui → q01_p9
    POINT   10                      @ S09/S10 PendSV pendente por software
    movs    r3, #100
2:  subs    r3, #1
    bne     2b
    POINT   11                      @ S11 laço longo: 100 voltas
    mov     r0, r2
    pop     {r4, pc}
    .size q01_seq, . - q01_seq
    .ltorg

    .type q01_leaf, %function
    .thumb_func
q01_leaf:
    adds    r3, #1
    bx      lr
    .size q01_leaf, . - q01_leaf

    .global SVC_Handler
    .type SVC_Handler, %function
    .thumb_func
SVC_Handler:
    POINT_HANDLER 7
    bx      lr
    .size SVC_Handler, . - SVC_Handler

    .global PendSV_Handler
    .type PendSV_Handler, %function
    .thumb_func
PendSV_Handler:
    POINT_HANDLER 9
    bx      lr
    .size PendSV_Handler, . - PendSV_Handler

/* Fim da medição: o coletor põe um gancho em q01_done (executado uma vez) e
 * lê q01_count/q01_cyc da memória; depois fica no laço final. */
    .global q01_done
    .type q01_done, %function
    .thumb_func
q01_done:
    nop
1:  b       1b
    .size q01_done, . - q01_done

    .bss
    .align 2
    .global q01_scratch
q01_scratch:
    .space 8
