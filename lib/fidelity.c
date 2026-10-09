/**
 * @file    lib/fidelity.c
 * @brief   Implementação da ABI v3 (ver inc/fidelity.h).
 */
#include "fidelity.h"

#define STACK_PAINT   UINT32_C(0xA5A5A5A5)
#define STACK_GUARD   64U        /* bytes abaixo do SP atual que não pintamos */

/* Símbolos do linker script (vendor/STM32F103XX_FLASH.ld). */
extern uint32_t _ebss;
extern uint32_t _estack;

_Alignas(16) volatile FidSnapshot fid_snapshot;
volatile uint32_t fid_host_nonce;

/* Caso corrente: escrito só por MAIN, lido pelos loggers (inclusive ISRs). */
static volatile uint32_t fid_case_id;
static volatile uint32_t fid_case_open;

static void paint_stack(void)
{
    uint32_t *p = &_ebss;
    uint32_t *limit = (uint32_t *)(__get_MSP() - STACK_GUARD);
    while (p < limit) {
        *p = STACK_PAINT;
        ++p;
    }
}

static uint32_t unused_stack_bytes(void)
{
    const uint32_t *p = &_ebss;
    while (p < &_estack && *p == STACK_PAINT) {
        ++p;
    }
    return (uint32_t)((uintptr_t)p - (uintptr_t)&_ebss);
}

static void store_event(uint32_t writer, uint32_t ticks, uint32_t ticket,
                        uint32_t event, uint32_t arg)
{
    volatile FidHeader *h = &fid_snapshot.header;
    if (writer >= FID_WRITERS) {
        h->error |= FID_ERR_WRITER;
        return;
    }
    /* Anel circular: head conta tudo que já foi escrito; o host sabe quantos
     * registros antigos foram sobrescritos (head - capacidade). A entrada é
     * escrita inteira ANTES de o head avançar (DMB), então um registro
     * contado nunca está pela metade. */
    uint32_t head = h->ring_head[writer];
    volatile FidEvent *e = &fid_snapshot.ring[writer][head & (FID_RING - 1U)];
    e->ticks = ticks;
    e->ticket = ticket;
    e->event = (uint16_t)event;
    e->case_id = (uint16_t)fid_case_id;
    e->arg = arg;
    __DMB();
    h->ring_head[writer] = head + 1U;
}

void fid_log(uint32_t writer, uint32_t event, uint32_t arg)
{
    uint32_t ticket;
    uint32_t now;
    do {
        ticket = __LDREXW(&fid_snapshot.header.ticket_next);
        now = fid_now();
    } while (__STREXW(ticket + 1U, &fid_snapshot.header.ticket_next) != 0U);
    store_event(writer, now, ticket, event, arg);
}

void fid_log_at(uint32_t writer, uint32_t ticks, uint32_t event, uint32_t arg)
{
    uint32_t ticket;
    do {
        ticket = __LDREXW(&fid_snapshot.header.ticket_next);
    } while (__STREXW(ticket + 1U, &fid_snapshot.header.ticket_next) != 0U);
    store_event(writer, ticks, ticket, event, arg);
}

static uint32_t min_observer_ticks(void)
{
    uint32_t best = UINT32_MAX;
    for (uint32_t i = 0U; i < 8U; ++i) {
        uint32_t a = fid_now();
        uint32_t b = fid_now();
        if ((b - a) < best) {
            best = b - a;
        }
    }
    return best;
}

/* Custo de um fid_log: diferença mínima entre timestamps de registros
 * consecutivos. Os 8 eventos ficam no anel MAIN (o host os ignora). */
static uint32_t min_log_ticks(void)
{
    uint32_t best = UINT32_MAX;
    for (uint32_t i = 0U; i < 4U; ++i) {
        uint32_t head = fid_snapshot.header.ring_head[FID_MAIN];
        fid_log(FID_MAIN, FID_EV_CALIBRATE, i);
        fid_log(FID_MAIN, FID_EV_CALIBRATE, i);
        uint32_t a = fid_snapshot.ring[FID_MAIN][head & (FID_RING - 1U)].ticks;
        uint32_t b = fid_snapshot.ring[FID_MAIN][(head + 1U) & (FID_RING - 1U)].ticks;
        if ((b - a) < best) {
            best = b - a;
        }
    }
    return best;
}

void fid_init(uint32_t firmware_id, uint32_t case_planned)
{
    /* Zera o objeto inteiro (acesso volatile byte a byte, sem libc). */
    volatile uint8_t *bytes = (volatile uint8_t *)&fid_snapshot;
    for (uint32_t i = 0U; i < sizeof(FidSnapshot); ++i) {
        bytes[i] = 0U;
    }
    fid_case_id = 0U;
    fid_case_open = 0U;
    paint_stack();

    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL &= ~DWT_CTRL_CYCCNTENA_Msk;
    DWT->CYCCNT = FID_DWT_START;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    __DSB();
    __ISB();

    volatile FidHeader *h = &fid_snapshot.header;
    h->magic = FID_MAGIC;
    h->abi_version = FID_ABI_VERSION;
    h->snapshot_bytes = sizeof(FidSnapshot);
    h->firmware_id = firmware_id;
    h->run_nonce = fid_host_nonce;
    h->case_planned = case_planned;
    h->case_capacity = FID_MAX_CASES;
    h->word_capacity = FID_MAX_WORDS;
    h->ring_capacity = FID_RING;
    h->writer_count = FID_WRITERS;
    h->dwt_start = FID_DWT_START;
    h->core_hz = FID_CORE_HZ;
    h->cpuid = SCB->CPUID;
    h->idcode = DBGMCU->IDCODE;
    h->flash_kb = *(const volatile uint16_t *)FLASHSIZE_BASE;
    h->uid[0] = *(const volatile uint32_t *)(UID_BASE + 0U);
    h->uid[1] = *(const volatile uint32_t *)(UID_BASE + 4U);
    h->uid[2] = *(const volatile uint32_t *)(UID_BASE + 8U);
    __DMB();
    h->state = FID_STATE_RUNNING;

    h->observer_ticks = min_observer_ticks();
    h->log_ticks = min_log_ticks();
    fid_log(FID_MAIN, FID_EV_BOOT, firmware_id);
}

void fid_case_begin(uint32_t case_id)
{
    volatile FidHeader *h = &fid_snapshot.header;
    if (fid_case_open != 0U) {
        h->error |= FID_ERR_PROTOCOL;
    }
    if (h->case_count >= FID_MAX_CASES) {
        h->error |= FID_ERR_CASES_FULL;
        fid_case_open = 0U;
        return;
    }
    volatile FidCase *c = &fid_snapshot.cases[h->case_count];
    c->case_id = case_id;
    c->status = FID_CASE_OPEN;
    c->first_word = h->word_count;
    c->word_count = 0U;
    fid_case_id = case_id;
    fid_case_open = 1U;
    fid_log(FID_MAIN, FID_EV_CASE_BEGIN, case_id);
}

void fid_put(uint32_t value)
{
    volatile FidHeader *h = &fid_snapshot.header;
    if (fid_case_open == 0U) {
        h->error |= FID_ERR_PROTOCOL;
        return;
    }
    if (h->word_count >= FID_MAX_WORDS) {
        h->error |= FID_ERR_WORDS_FULL;
        return;
    }
    fid_snapshot.words[h->word_count] = value;
    h->word_count = h->word_count + 1U;
    volatile FidCase *c = &fid_snapshot.cases[h->case_count];
    c->word_count = c->word_count + 1U;
}

void fid_case_end(uint32_t status)
{
    volatile FidHeader *h = &fid_snapshot.header;
    if (fid_case_open == 0U) {
        h->error |= FID_ERR_PROTOCOL;
        return;
    }
    fid_log(FID_MAIN, FID_EV_CASE_END, status);
    fid_snapshot.cases[h->case_count].status = status;
    __DMB();
    h->case_count = h->case_count + 1U;
    fid_case_open = 0U;
}

static void capture_context(void)
{
    volatile FidHeader *h = &fid_snapshot.header;
    h->dwt_end = fid_now();
    h->rcc_cr = RCC->CR;
    h->rcc_cfgr = RCC->CFGR;
    h->flash_acr = FLASH->ACR;
    h->dbgmcu_cr = DBGMCU->CR;
    h->aircr = SCB->AIRCR;
    h->stack_free = unused_stack_bytes();
    if (h->stack_free == 0U) {
        h->error |= FID_ERR_STACK;
    }
}

_Noreturn void fid_finish(void)
{
    volatile FidHeader *h = &fid_snapshot.header;
    if (fid_case_open != 0U) {
        h->error |= FID_ERR_PROTOCOL;
    }
    if (h->case_count != h->case_planned) {
        h->error |= FID_ERR_PLAN;
    }
    fid_log(FID_MAIN, FID_EV_FINISH, h->case_count);
    __disable_irq();
    for (uint32_t i = 0U; i < 8U; ++i) {
        NVIC->ICER[i] = 0xFFFFFFFFU;
    }
    __DSB();
    capture_context();
    __DMB();
    h->state = (h->error == 0U) ? FID_STATE_DONE : FID_STATE_FAILED;
    __DSB();
    fid_complete();
}

_Noreturn void fid_complete(void)
{
    /* Sem BKPT: o host usa hbreak aqui; sem debugger, o alvo fica parado. */
    for (;;) {
        __NOP();
    }
}

/* ───────────── falhas: registram FAILED em vez de travar ───────────── */

void fid_fault(const uint32_t *frame);

void fid_fault(const uint32_t *frame)
{
    volatile FidHeader *h = &fid_snapshot.header;
    h->error |= FID_ERR_FAULT;
    h->fault_pc = frame[6];              /* R0-R3, R12, LR, PC, xPSR */
    h->fault_cfsr = SCB->CFSR;
    capture_context();
    __DMB();
    h->state = FID_STATE_FAILED;
    __DSB();
    fid_complete();
}

/* Só o HardFault: MemManage/BusFault/UsageFault ficam desabilitados (reset
 * de SHCSR) e escalam para ele. Todos os cenários usam apenas o MSP (sem RTOS,
 * sem PSP), então o MSP aponta para a moldura empilhada pela exceção. */
__attribute__((naked)) void HardFault_Handler(void);
__attribute__((naked)) void HardFault_Handler(void)
{
    __asm volatile("mrs r0, msp\n\tb fid_fault\n");
}
