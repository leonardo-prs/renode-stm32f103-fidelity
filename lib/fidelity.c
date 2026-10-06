#include "fidelity.h"
#include "stm32f1xx.h"

_Alignas(16) volatile FidelitySnapshot fidelity_snapshot;

void fidelity_init(uint32_t scenario, uint32_t seed)
{
    /* Character accesses may alias the complete object without crossing
     * uint32_t subobjects; volatile stores avoid heap/libc dependencies.
     * Experiment sources must remain quiescent throughout initialization.
     */
    volatile unsigned char *bytes = (volatile unsigned char *)&fidelity_snapshot;
    for (uint32_t i = 0U; i < sizeof(FidelitySnapshot); ++i) {
        bytes[i] = 0U;
    }

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL &= ~DWT_CTRL_CYCCNTENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    __DSB();
    __ISB();

    fidelity_snapshot.header.magic = FIDELITY_MAGIC;
    fidelity_snapshot.header.version = FIDELITY_VERSION;
    fidelity_snapshot.header.scenario = scenario;
    fidelity_snapshot.header.core_hz = FIDELITY_CORE_HZ;
    fidelity_snapshot.header.trace_capacity = FIDELITY_TRACE_CAPACITY;
    fidelity_snapshot.header.result_capacity = FIDELITY_RESULT_CAPACITY;
    fidelity_snapshot.header.trace_enabled = 1U;
    fidelity_snapshot.header.seed = seed;
    __DMB();
    fidelity_snapshot.header.state = FIDELITY_RUNNING;
    fidelity_trace(FIDELITY_MAIN, FIDELITY_BOOT, 0U, scenario);
}

uint32_t fidelity_ticks(void)
{
    return DWT->CYCCNT;
}

void fidelity_trace(uint32_t writer, uint32_t event, uint32_t trial, uint32_t arg)
{
    /* Valid channel ownership is a caller contract, not role-based routing.
     * No interrupt mask is used: each channel has exactly one writer.
     */
    if (writer >= FIDELITY_WRITER_COUNT ||
        fidelity_snapshot.header.state != FIDELITY_RUNNING ||
        fidelity_snapshot.header.trace_enabled == 0U) {
        return;
    }
    uint32_t index = fidelity_snapshot.header.trace_count[writer];
    if (index >= FIDELITY_TRACE_CAPACITY) {
        fidelity_snapshot.header.trace_drop[writer]++;
        return;
    }
    volatile FidelityTraceEntry *entry = &fidelity_snapshot.trace[writer][index];
    entry->ticks = fidelity_ticks();
    entry->event = event;
    entry->trial = trial;
    entry->arg = arg;
    __DMB();
    fidelity_snapshot.header.trace_count[writer] = index + 1U;
}

void fidelity_result(uint32_t trial, uint32_t condition,
                     uint32_t a, uint32_t b, uint32_t c,
                     uint32_t d, uint32_t e, uint32_t f)
{
    if (fidelity_snapshot.header.state != FIDELITY_RUNNING) {
        return;
    }
    uint32_t index = fidelity_snapshot.header.result_count;
    if (index >= FIDELITY_RESULT_CAPACITY) {
        fidelity_snapshot.header.error |= FIDELITY_ERROR_RESULT_OVERFLOW;
        return;
    }
    volatile uint32_t *row = fidelity_snapshot.results[index];
    row[0] = trial;
    row[1] = condition;
    row[2] = a;
    row[3] = b;
    row[4] = c;
    row[5] = d;
    row[6] = e;
    row[7] = f;
    __DMB();
    fidelity_snapshot.header.result_count = index + 1U;
}

_Noreturn void fidelity_finish(uint32_t error)
{
    /* Scenario has already stopped peripheral sources and all writers. */
    __disable_irq();
    __DSB();
    fidelity_snapshot.header.rcc_cr = RCC->CR;
    fidelity_snapshot.header.rcc_cfgr = RCC->CFGR;
    fidelity_snapshot.header.flash_acr = FLASH->ACR;
    fidelity_snapshot.header.dwt_ctrl = DWT->CTRL;
    fidelity_snapshot.header.prigroup = NVIC_GetPriorityGrouping();
    fidelity_snapshot.header.error |= error;
    __DMB();
    fidelity_snapshot.header.state = fidelity_snapshot.header.error == 0U
                                  ? FIDELITY_DONE : FIDELITY_FAILED;
    __DSB();
    fidelity_complete();
}

_Noreturn void fidelity_complete(void)
{
    /* Deliberately no BKPT: a debugger is optional, snapshot is frozen. */
    for (;;) {
        __NOP();
    }
}
