/**
 * @file    lib/fidelity.c
 * @brief   Implementação da ABI v2 (ver inc/fidelity.h).
 */
#include "fidelity.h"

_Alignas(16) volatile FidelitySnapshot fidelity_snapshot;

void fidelity_init(uint32_t scenario, uint32_t variant, uint32_t seed)
{
    /* Acesso byte a byte volatile: zera o objeto inteiro sem libc. */
    volatile uint8_t *bytes = (volatile uint8_t *)&fidelity_snapshot;
    for (uint32_t i = 0U; i < sizeof(FidelitySnapshot); ++i) {
        bytes[i] = 0U;
    }

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL &= ~DWT_CTRL_CYCCNTENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    __DSB();
    __ISB();

    /* Custo do observador: menor diferença entre duas leituras seguidas. */
    uint32_t best = UINT32_MAX;
    for (uint32_t i = 0U; i < 8U; ++i) {
        uint32_t a = fidelity_now();
        uint32_t b = fidelity_now();
        if ((b - a) < best) {
            best = b - a;
        }
    }

    volatile FidelityHeader *h = &fidelity_snapshot.header;
    h->magic = FIDELITY_MAGIC;
    h->version = FIDELITY_VERSION;
    h->scenario = scenario;
    h->variant = variant;
    h->core_hz = FIDELITY_CORE_HZ;
    h->seed = seed;
    h->row_capacity = FIDELITY_ROWS;
    h->trace_capacity = FIDELITY_TRACE;
    h->observer_ticks = best;
    __DMB();
    h->state = FIDELITY_RUNNING;
    fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_BOOT, 0U, (scenario << 8) | variant);
}

void fidelity_trace(uint32_t writer, uint32_t event, uint32_t trial, uint32_t arg)
{
    fidelity_trace_at(writer, fidelity_now(), event, trial, arg);
}

void fidelity_trace_at(uint32_t writer, uint32_t ticks, uint32_t event,
                       uint32_t trial, uint32_t arg)
{
    /* Cada canal tem exatamente um escritor: sem máscara de IRQ, sem head
     * compartilhado. O count publica a entrada inteira (DMB antes). */
    volatile FidelityHeader *h = &fidelity_snapshot.header;
    if (writer >= FIDELITY_WRITERS || h->state != FIDELITY_RUNNING) {
        return;
    }
    uint32_t index = h->trace_count[writer];
    if (index >= FIDELITY_TRACE) {
        h->trace_drop[writer] = h->trace_drop[writer] + 1U;
        return;
    }
    volatile FidelityTraceEntry *e = &fidelity_snapshot.trace[writer][index];
    e->ticks = ticks;
    e->event = event;
    e->trial = trial;
    e->arg = arg;
    __DMB();
    h->trace_count[writer] = index + 1U;
}

void fidelity_row(uint32_t trial, uint32_t condition,
                  uint32_t v0, uint32_t v1, uint32_t v2,
                  uint32_t v3, uint32_t v4, uint32_t v5)
{
    volatile FidelityHeader *h = &fidelity_snapshot.header;
    if (h->state != FIDELITY_RUNNING) {
        return;
    }
    uint32_t index = h->row_count;
    if (index >= FIDELITY_ROWS) {
        h->error |= FIDELITY_ERR_ROWS_FULL;
        return;
    }
    volatile uint32_t *row = fidelity_snapshot.rows[index];
    row[0] = trial;
    row[1] = condition;
    row[2] = v0;
    row[3] = v1;
    row[4] = v2;
    row[5] = v3;
    row[6] = v4;
    row[7] = v5;
    __DMB();
    h->row_count = index + 1U;
}

void fidelity_flag(uint32_t error_bits)
{
    fidelity_snapshot.header.error |= error_bits;
}

_Noreturn void fidelity_finish(void)
{
    __disable_irq();
    __DSB();
    volatile FidelityHeader *h = &fidelity_snapshot.header;
    h->end_ticks = fidelity_now();
    h->cpuid = SCB->CPUID;
    h->rcc_cr = RCC->CR;
    h->rcc_cfgr = RCC->CFGR;
    h->flash_acr = FLASH->ACR;
    h->dwt_ctrl = DWT->CTRL;
    h->aircr = SCB->AIRCR;
    h->dbgmcu_cr = DBGMCU->CR;
    __DMB();
    h->state = (h->error == 0U) ? FIDELITY_DONE : FIDELITY_FAILED;
    __DSB();
    fidelity_complete();
}

_Noreturn void fidelity_complete(void)
{
    /* Sem BKPT: o coletor usa hbreak aqui; sem debugger, fica parado. */
    for (;;) {
        __NOP();
    }
}
