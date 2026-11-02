/*
 * src/q02/q02.c — Q-02: verificação dos instrumentos genéricos do Renode
 * (03-quadro-comum.typ, família Q).
 *
 * Só núcleo, SRAM e SCS: nenhum periférico do chip é tocado (o gate confere
 * que não há literal na faixa de periféricos). As exceções usadas são as do
 * próprio núcleo, pedidas por escrita no ICSR: PendSV (PENDSVSET) e SysTick
 * (PENDSTSET, sem ligar o timer SysTick). O firmware não julga o núcleo; ele
 * produz eventos conhecidos e registra o que viu (q02_rec), para a análise
 * conferir os instrumentos contra essa visão interna e contra o traço.
 *
 * Contrato com o host (scripts/q02/spec.py → build/q02/gen/q02_spec.h):
 *   q02_magic   .noinit; gravado pelo monitor com a simulação parada, antes da partida
 *   q02_point   ponto marcado: o gancho no endereço lê o id em R0
 *   q02_store   única instrução que escreve nos endereços vigiados (q02_sink[0], ICSR)
 *   q02_trigger o gancho de estímulo neste endereço grava Q02_HOOK_VALUE em q02_mbox2
 *   q02_wait    espera q02_mbox == valor (gravado pelo monitor numa pausa)
 *   q02_done    fim: o gancho lê q02_rec
 */
#include <stdint.h>

#include "stm32f1xx.h"
#include "q02_spec.h"

#define Q02_N_IRQ 43U

typedef void (*q02_handler_t)(void);
typedef struct {
    uint32_t *initial_sp;
    q02_handler_t vector[15U + Q02_N_IRQ];
} q02_vectors_t;

extern uint32_t _estack[], _sdata[], _edata[], _sidata[], _sbss[], _ebss[];

int main(void);
__attribute__((noreturn)) void Reset_Handler(void);
__attribute__((noreturn)) void q02_fault(void);
__attribute__((noipa, noreturn)) void q02_done(void);
__attribute__((noipa)) void q02_point(uint32_t id);
__attribute__((noipa)) void q02_store(volatile uint32_t *addr, uint32_t value);
__attribute__((noipa)) void q02_trigger(void);
__attribute__((noipa)) uint32_t q02_wait(uint32_t want);
void PendSV_Handler(void);
void SysTick_Handler(void);

#define Q02_FAULT_X5 q02_fault, q02_fault, q02_fault, q02_fault, q02_fault
#define Q02_FAULT_X10 Q02_FAULT_X5, Q02_FAULT_X5

__attribute__((section(".isr_vector"), used))
const q02_vectors_t q02_vectors = {
    _estack,
    {
        Reset_Handler,                                     /*  1 Reset */
        q02_fault, q02_fault, q02_fault, q02_fault, q02_fault, /*  2..6 NMI, HardFault, MemManage, BusFault, UsageFault */
        q02_fault, q02_fault, q02_fault, q02_fault,        /*  7..10 reservados */
        q02_fault, q02_fault, q02_fault,                   /* 11..13 SVC, DebugMon, reservado */
        PendSV_Handler,                                    /* 14 PendSV */
        SysTick_Handler,                                   /* 15 SysTick */
        Q02_FAULT_X10, Q02_FAULT_X10, Q02_FAULT_X10, Q02_FAULT_X10, /* IRQ0..IRQ39 */
        q02_fault, q02_fault, q02_fault,                   /* IRQ40..IRQ42 */
    },
};

__attribute__((section(".noinit"))) volatile uint32_t q02_magic;
volatile uint32_t q02_sink[2];          /* [0] vigiada; [1] vizinha, não vigiada */
volatile uint32_t q02_mbox;             /* escrita pelo monitor nas pausas */
volatile uint32_t q02_mbox2;            /* escrita pelo gancho de estímulo */
volatile uint32_t q02_echo;             /* escrita pelo firmware; lida pelo monitor */
volatile uint32_t q02_mode;             /* único escritor: main; lida pelos tratadores */
volatile q02_rec_t q02_rec;

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
    q02_fault();
}

void q02_fault(void)
{
    for (;;) {
    }
}

void q02_done(void)
{
    for (;;) {
    }
}

void q02_point(uint32_t id)
{
    (void)id;
}

void q02_store(volatile uint32_t *addr, uint32_t value)
{
    *addr = value;
}

void q02_trigger(void)
{
}

uint32_t q02_wait(uint32_t want)
{
    uint32_t n = 0U;
    while (q02_mbox != want) {
        n++;
    }
    return n;
}

/* Escrita vigiada feita pela thread: registrada antes de acontecer. */
static void logged_store(volatile uint32_t *addr, uint32_t value)
{
    uint32_t k = q02_rec.wlog_n;
    if (k < Q02_N_WLOG) {
        q02_rec.wlog[k][0] = (uint32_t)addr;
        q02_rec.wlog[k][1] = value;
        q02_rec.wlog_n = k + 1U;
    }
    q02_store(addr, value);
}

static void pend(uint32_t bit)
{
    logged_store(&SCB->ICSR, bit);
    __DSB();
    __ISB();
}

void PendSV_Handler(void)
{
    uint32_t k = q02_rec.n_pendsv;
    if (k < Q02_N_SAW) {
        q02_rec.pendsv_saw[k] = q02_rec.n_systick;
    }
    q02_rec.n_pendsv = k + 1U;
    if (q02_mode == Q02_MODE_NEST) {
        q02_rec.nest_before = q02_rec.n_systick;
        q02_rec.pendsv_icsr++;
        q02_store(&SCB->ICSR, SCB_ICSR_PENDSTSET_Msk);
        __DSB();
        __ISB();
        q02_rec.nest_after = q02_rec.n_systick;
    }
}

void SysTick_Handler(void)
{
    uint32_t k = q02_rec.n_systick;
    if (k < Q02_N_SAW) {
        q02_rec.systick_saw[k] = q02_rec.n_pendsv;
    }
    q02_rec.n_systick = k + 1U;
    if (q02_mode == Q02_MODE_TAIL) {
        q02_rec.systick_icsr++;
        q02_store(&SCB->ICSR, SCB_ICSR_PENDSVSET_Msk);
    }
}

int main(void)
{
    static const uint32_t sink_values[Q02_N_SINK_VALUES] = Q02_SINK_VALUES;

    SCB->VTOR = (uint32_t)&q02_vectors;
    NVIC_SetPriorityGrouping(0U);
    NVIC_SetPriority(PendSV_IRQn, Q02_PRIO_PENDSV);
    NVIC_SetPriority(SysTick_IRQn, Q02_PRIO_SYSTICK);
    __set_BASEPRI(0U);
    __enable_fault_irq();
    __enable_irq();
    __DSB();
    __ISB();

    q02_rec.status = Q02_ST_RUNNING;
    if (q02_magic != Q02_MAGIC) {
        q02_rec.status = Q02_ST_BAD_PARAM;
        q02_done();
    }

    /* W: escritas de palavra; a do meio vai para a vizinha não vigiada. */
    q02_point(Q02_P_W_BEGIN);
    for (uint32_t i = 0U; i < Q02_N_SINK_VALUES; i++) {
        logged_store(&q02_sink[0], sink_values[i]);
        if (i == 1U) {
            q02_store(&q02_sink[1], Q02_NEIGHBOR_VALUE);
        }
    }
    q02_point(Q02_P_W_END);

    q02_mode = Q02_MODE_NONE;
    q02_point(Q02_P_X_PENDSV_BEGIN);
    pend(SCB_ICSR_PENDSVSET_Msk);
    q02_point(Q02_P_X_PENDSV_END);

    q02_point(Q02_P_X_SYSTICK_BEGIN);
    pend(SCB_ICSR_PENDSTSET_Msk);
    q02_point(Q02_P_X_SYSTICK_END);

    q02_mode = Q02_MODE_TAIL;
    q02_point(Q02_P_X_TAIL_BEGIN);
    pend(SCB_ICSR_PENDSTSET_Msk);
    q02_point(Q02_P_X_TAIL_END);

    q02_mode = Q02_MODE_NEST;
    q02_point(Q02_P_X_NEST_BEGIN);
    pend(SCB_ICSR_PENDSVSET_Msk);
    q02_point(Q02_P_X_NEST_END);

    q02_mode = Q02_MODE_NONE;
    q02_point(Q02_P_X_MASKED_BEGIN);
    __disable_irq();
    pend(SCB_ICSR_PENDSVSET_Msk);
    pend(SCB_ICSR_PENDSTSET_Msk);
    __enable_irq();
    __ISB();
    q02_point(Q02_P_X_MASKED_END);

    q02_point(Q02_P_M_HOOK_BEGIN);
    q02_trigger();
    q02_rec.hook_seen = q02_mbox2;
    q02_point(Q02_P_M_HOOK_END);

    q02_echo = Q02_ECHO_VALUE;
    q02_point(Q02_P_M_PAUSE_BEGIN);
    q02_rec.wait_iters[0] = q02_wait(Q02_PAUSE_VALUE0);
    q02_rec.pause_seen[0] = q02_mbox;
    q02_point(Q02_P_SEEN1);
    q02_rec.wait_iters[1] = q02_wait(Q02_PAUSE_VALUE1);
    q02_rec.pause_seen[1] = q02_mbox;
    q02_point(Q02_P_M_PAUSE_END);

    q02_rec.status = Q02_ST_DONE;
    q02_done();
}
