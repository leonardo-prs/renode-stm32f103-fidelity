/*
 * src/q/q.c — caso Q-01: verificação dos instrumentos do Renode
 * (03-quadro-comum.typ, família Q). Roda só no Renode.
 *
 * Usa só o núcleo, a SRAM e o SCS/DWT. Produz eventos conhecidos (pontos
 * marcados, escritas, exceções, espera por valores gravados de fora) e grava
 * em q_rec o que viu. scripts/q.py confere os instrumentos contra isso.
 *
 * O que scripts/q.py usa, pelo nome do símbolo:
 *   q_mark     ponto marcado: grava o DWT_CYCCNT em q_rec
 *   q_store    a única escrita nos endereços vigiados (q_sink e ICSR)
 *   q_trigger  o gancho neste endereço grava um valor em q_mbox2
 *   q_done     fim: o gancho neste endereço despeja q_rec
 *   q_fault    qualquer exceção inesperada (execução inválida)
 *   q_magic    gravado pelo monitor antes da partida
 *   q_mbox     gravado pelo monitor nas pausas
 *   q_rec      registro do firmware (ordem dos campos: enum abaixo)
 */
#include <stdint.h>

#include "stm32f1xx.h"

/* Campos de q_rec. A mesma ordem está em scripts/q.py (REC). */
enum {
    R_STATUS,                   /* 1 = chegou ao fim */
    R_MAGIC,                    /* q_magic como o firmware o leu */
    R_N_PENDSV,                 /* entradas no tratador do PendSV */
    R_N_SYSTICK,                /* entradas no tratador do SysTick */
    R_HOOK_SEEN,                /* q_mbox2 depois de q_trigger */
    R_PAUSE0, R_PAUSE1,         /* q_mbox ao fim de cada espera */
    R_WAIT0, R_WAIT1,           /* voltas de cada espera */
    R_N_MARK,                   /* pontos marcados executados */
    R_CYC,                      /* DWT_CYCCNT em cada ponto marcado */
    R_WORDS = R_CYC + 16
};

#define Q_PASSES 2U             /* a 1ª passagem traduz o código; a 2ª reutiliza */

extern uint32_t _estack[], _sdata[], _edata[], _sidata[], _sbss[], _ebss[];

int main(void);
__attribute__((noreturn)) void Reset_Handler(void);
__attribute__((noreturn)) void q_fault(void);
__attribute__((noipa, noreturn)) void q_done(void);
__attribute__((noipa)) void q_mark(void);
__attribute__((noipa)) void q_store(volatile uint32_t *addr, uint32_t value);
__attribute__((noipa)) void q_trigger(void);
void PendSV_Handler(void);
void SysTick_Handler(void);

__attribute__((section(".isr_vector"), used))
void (*const q_vectors[16])(void) = {
    (void (*)(void))_estack,
    Reset_Handler,
    q_fault, q_fault, q_fault, q_fault, q_fault,   /*  2..6  NMI, HardFault, MemManage, BusFault, UsageFault */
    q_fault, q_fault, q_fault, q_fault,            /*  7..10 reservados */
    q_fault, q_fault, q_fault,                     /* 11..13 SVC, DebugMon, reservado */
    PendSV_Handler,                                /* 14 */
    SysTick_Handler,                               /* 15 */
};

__attribute__((section(".noinit"))) volatile uint32_t q_magic;
__attribute__((section(".noinit"))) volatile uint32_t q_sink;  /* .noinit: o Reset_Handler não escreve nele */
volatile uint32_t q_mbox;
volatile uint32_t q_mbox2;
volatile uint32_t q_nest;       /* único escritor: main */
volatile uint32_t q_rec[R_WORDS];

void Reset_Handler(void)
{
    const uint32_t *src = _sidata;
    for (uint32_t *dst = _sdata; dst < _edata; dst++) {
        *dst = *src++;
    }
    for (uint32_t *dst = _sbss; dst < _ebss; dst++) {
        *dst = 0U;
    }
    (void)main();
    q_fault();
}

void q_fault(void)
{
    for (;;) {
    }
}

void q_done(void)
{
    for (;;) {
    }
}

void q_mark(void)
{
    uint32_t n = q_rec[R_N_MARK];
    if (n < R_WORDS - R_CYC) {
        q_rec[R_CYC + n] = DWT->CYCCNT;
    }
    q_rec[R_N_MARK] = n + 1U;
}

void q_store(volatile uint32_t *addr, uint32_t value)
{
    *addr = value;
}

void q_trigger(void)
{
}

static void pend(uint32_t bits)
{
    q_store(&SCB->ICSR, bits);
    __DSB();
    __ISB();
}

static uint32_t wait_change(uint32_t old)
{
    uint32_t n = 0U;
    while (q_mbox == old) {
        n++;
    }
    return n;
}

void PendSV_Handler(void)
{
    q_rec[R_N_PENDSV]++;
    if (q_nest != 0U) {
        pend(SCB_ICSR_PENDSTSET_Msk);       /* SysTick (prioridade maior) preempta aqui */
    }
}

void SysTick_Handler(void)
{
    q_rec[R_N_SYSTICK]++;
}

int main(void)
{
    SCB->VTOR = (uint32_t)q_vectors;
    NVIC_SetPriority(PendSV_IRQn, 15U);
    NVIC_SetPriority(SysTick_IRQn, 8U);
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    q_rec[R_MAGIC] = q_magic;

    for (uint32_t pass = 0U; pass < Q_PASSES; pass++) {
        q_mark();
        for (volatile uint32_t i = 0U; i < 10U; i++) {     /* laço */
        }
        q_mark();
        q_store(&q_sink, 0x11111111U + pass);              /* escritas vigiadas */
        q_store(&q_sink, 0xA5A5A5A5U);
        q_mark();
        pend(SCB_ICSR_PENDSVSET_Msk);                      /* entrada simples */
        q_mark();
        __disable_irq();                                   /* SysTick, depois PendSV encadeado */
        q_store(&SCB->ICSR, SCB_ICSR_PENDSVSET_Msk | SCB_ICSR_PENDSTSET_Msk);
        __enable_irq();
        __ISB();
        q_mark();
        q_nest = 1U;                                       /* aninhamento */
        pend(SCB_ICSR_PENDSVSET_Msk);
        q_nest = 0U;
        q_mark();
    }

    q_trigger();                                           /* gancho grava q_mbox2 */
    q_rec[R_HOOK_SEEN] = q_mbox2;
    q_mark();
    q_rec[R_WAIT0] = wait_change(0U);                      /* monitor grava q_mbox nas pausas */
    q_rec[R_PAUSE0] = q_mbox;
    q_rec[R_WAIT1] = wait_change(q_rec[R_PAUSE0]);
    q_rec[R_PAUSE1] = q_mbox;
    q_mark();

    q_rec[R_STATUS] = 1U;
    q_done();
}
