/**
 * @file    src/c1/common/c1.c
 * @brief   Registro C1S1 (ver c1.h): início, resultados, término.
 */
#include "c1.h"

#define STACK_PAINT UINT32_C(0xA5A5A5A5)
#define STACK_GUARD 64U          /* bytes abaixo do SP atual que não pintamos */

_Alignas(8) volatile C1Snapshot c1_snapshot;
volatile C1Host c1_host;
volatile C1Fault c1_fault;
volatile uint32_t c1_terminal;

static volatile uint32_t c1_open;

static void paint_stack(void)
{
    uint32_t *p = &_sstack;
    uint32_t *limit = (uint32_t *)(__get_MSP() - STACK_GUARD);
    while (p < limit) {
        *(volatile uint32_t *)p = STACK_PAINT;
        ++p;
    }
}

static uint32_t unused_stack_bytes(void)
{
    const volatile uint32_t *p = &_sstack;
    while (p < (const volatile uint32_t *)&_estack && *p == STACK_PAINT) {
        ++p;
    }
    return (uint32_t)((uintptr_t)p - (uintptr_t)&_sstack);
}

static uint32_t min_observer_ticks(void)
{
    uint32_t best = UINT32_MAX;
    for (uint32_t i = 0U; i < 8U; ++i) {
        uint32_t a = c1_now();
        uint32_t b = c1_now();
        if ((b - a) < best) {
            best = b - a;
        }
    }
    return best;
}

void c1_clear_fault(void)
{
    c1_fault.cfsr = 0U;
    c1_fault.hfsr = 0U;
    c1_fault.mmfar = 0U;
    c1_fault.bfar = 0U;
    c1_fault.pc = 0U;
    c1_fault.xpsr = 0U;
    c1_fault.exc_return = 0U;
    c1_fault.landing = 0U;
    c1_fault.ipsr = 0U;
    c1_fault.count = 0U;
}

void c1_enable_fault_handlers(void)
{
    SCB->SHCSR |= SCB_SHCSR_USGFAULTENA_Msk | SCB_SHCSR_BUSFAULTENA_Msk |
                  SCB_SHCSR_MEMFAULTENA_Msk;
    __DSB();
    __ISB();
}

void c1_init(uint32_t preset, uint32_t catalog_hash, uint32_t record_planned)
{
    volatile uint32_t *w = (volatile uint32_t *)&c1_snapshot;
    for (uint32_t i = 0U; i < sizeof(C1Snapshot) / 4U; ++i) {
        w[i] = 0U;
    }
    c1_open = 0U;
    c1_terminal = 0U;
    c1_clear_fault();
    paint_stack();

    /* Nenhuma fonte de exceção assíncrona: NVIC todo desabilitado, SysTick
     * desligado. Interrupções ficam DESMASCARADAS (PRIMASK = 0) porque SVC e
     * faltas com PRIMASK = 1 escalariam para HardFault (§B1.5.14). */
    for (uint32_t i = 0U; i < 8U; ++i) {
        NVIC->ICER[i] = 0xFFFFFFFFU;
        NVIC->ICPR[i] = 0xFFFFFFFFU;
    }
    SysTick->CTRL = 0U;

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    __DSB();
    __ISB();

    volatile C1Header *h = &c1_snapshot.header;
    h->magic = C1_MAGIC;
    h->abi_version = C1_ABI_VERSION;
    h->snapshot_bytes = sizeof(C1Snapshot);
    h->preset = preset;
    h->catalog_hash = catalog_hash;
    h->record_capacity = C1_MAX_RECORDS;
    h->word_capacity = C1_MAX_WORDS;
    h->record_planned = record_planned;
    if (c1_host.magic == C1_HOST_MAGIC) {
        h->nonce = c1_host.nonce;
        h->batch = c1_host.batch;
        h->iters = c1_host.iters;
        h->host_flags = c1_host.flags;
    } else {
        h->error |= C1_ERR_HOST;   /* run sem host (depuração): nunca é evidência */
    }
    h->cpuid = SCB->CPUID;
    h->rcc_cr = RCC->CR;
    h->rcc_cfgr = RCC->CFGR;
    h->flash_acr = FLASH->ACR;
    for (uint32_t i = 0U; i < C1_RESET_WORDS; ++i) {
        h->reset[i] = ((const volatile uint32_t *)&c1_reset_capture)[i];
    }
    h->observer_ticks = min_observer_ticks();
    __DMB();
    h->state = C1_STATE_RUNNING;
}

void c1_begin(uint32_t id)
{
    volatile C1Header *h = &c1_snapshot.header;
    if (c1_open != 0U) {
        c1_fail(C1_ERR_PROTOCOL);
    }
    if (h->record_count >= C1_MAX_RECORDS) {
        c1_fail(C1_ERR_RECORDS_FULL);
    }
    volatile C1Record *r = &c1_snapshot.records[h->record_count];
    r->id = id;
    r->status = C1_REC_OPEN;
    r->first_word = h->word_count;
    r->word_count = 0U;
    c1_open = 1U;
}

volatile uint32_t *c1_reserve(uint32_t words)
{
    volatile C1Header *h = &c1_snapshot.header;
    if (c1_open == 0U) {
        c1_fail(C1_ERR_PROTOCOL);
    }
    if (words > C1_MAX_WORDS - h->word_count) {
        c1_fail(C1_ERR_WORDS_FULL);
    }
    volatile uint32_t *p = &c1_snapshot.words[h->word_count];
    for (uint32_t i = 0U; i < words; ++i) {
        p[i] = 0U;
    }
    h->word_count = h->word_count + words;
    c1_snapshot.records[h->record_count].word_count += words;
    return p;
}

void c1_put(uint32_t value)
{
    *c1_reserve(1U) = value;
}

void c1_end(void)
{
    volatile C1Header *h = &c1_snapshot.header;
    if (c1_open == 0U) {
        c1_fail(C1_ERR_PROTOCOL);
    }
    c1_snapshot.records[h->record_count].status = C1_REC_OK;
    __DMB();
    h->record_count = h->record_count + 1U;
    c1_open = 0U;
}

void c1_put_fault(void)
{
    volatile uint32_t *p = c1_reserve(C1_FAULT_WORDS);
    const volatile uint32_t *f = (const volatile uint32_t *)&c1_fault;
    for (uint32_t i = 0U; i < C1_FAULT_WORDS; ++i) {
        p[i] = f[i];
    }
    c1_clear_fault();
}

static void capture_context(void)
{
    volatile C1Header *h = &c1_snapshot.header;
    h->stack_free = unused_stack_bytes();
    if (h->stack_free == 0U) {
        h->error |= C1_ERR_STACK;
    }
}

_Noreturn void c1_finish(void)
{
    volatile C1Header *h = &c1_snapshot.header;
    if (c1_open != 0U) {
        h->error |= C1_ERR_PROTOCOL;
    }
    capture_context();
    __DMB();
    h->state = (h->error == 0U) ? C1_STATE_DONE : C1_STATE_FAILED;
    __DSB();
    c1_complete();
}

_Noreturn void c1_fail(uint32_t error)
{
    c1_snapshot.header.error |= error;
    c1_finish();
}

_Noreturn void c1_fault_stop(void)
{
    volatile C1Header *h = &c1_snapshot.header;
    if (c1_terminal != 0U && c1_open != 0U) {
        /* Caso terminal: a falta sem aterrissagem é o resultado esperado. */
        c1_put_fault();
        c1_end();
        c1_finish();
    }
    const volatile uint32_t *f = (const volatile uint32_t *)&c1_fault;
    for (uint32_t i = 0U; i < C1_FAULT_WORDS; ++i) {
        h->fault[i] = f[i];
    }
    h->fault_ipsr = c1_fault.ipsr;
    c1_fail(C1_ERR_FAULT);
}

_Noreturn void c1_complete(void)
{
    /* Sem BKPT: o host usa hbreak aqui; sem depurador, o alvo fica parado. */
    for (;;) {
        __NOP();
    }
}
