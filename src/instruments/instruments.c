/*
 * src/instruments/instruments.c — verification of the Renode instruments
 * (Renode only).
 *
 * Produces known events and records what it saw, so scripts/instruments.py
 * can check each Renode instrument against a reference independent of it.
 * It uses only the core (SCB, NVIC, SysTick, DWT), so no peripheral model is
 * involved. It uses the case protocol of every firmware (src/common/case.h),
 * so that path is verified too.
 *
 * Record: DWT_CYCCNT at each mark(), then the fields of record_results().
 */
#include <stdint.h>

#include "case.h"
#include "stm32f1xx.h"

/* Exception numbers (IPSR). The external line is IRQ 0 (the WWDG line; the
 * peripheral is unused: only STIR and the monitor request it). */
#define EXC_PENDSV    14U
#define EXC_SYSTICK   15U
#define EXC_EXTERNAL  16U
#define EXTERNAL_LINE ((IRQn_Type)0)

/* Situations of the return matrix. */
#define SIMPLE 0U               /* request with nothing else pending */
#define CHAIN  1U               /* two pending with PRIMASK = 1: the 2nd chains */
#define NESTED 2U               /* the handler of the other exception requests the target */

extern uint32_t _estack[];

void PendSV_Handler(void);
void SysTick_Handler(void);
void External_Handler(void);
__attribute__((noipa)) void mark(void);
__attribute__((noipa)) void store(volatile uint32_t *address, uint32_t value);
__attribute__((noipa)) void trigger(void);
__attribute__((noipa)) void stress(void);
__attribute__((noipa)) void phase_mark(uint32_t phase);

__attribute__((section(".isr_vector"), used))
void (*const vectors[17])(void) = {
    (void (*)(void))_estack,
    Reset_Handler,
    [2 ... 13] = unexpected_exception,                  /* NMI, faults, SVC, DebugMon, reserved */
    [14] = PendSV_Handler,
    [15] = SysTick_Handler,
    [16] = External_Handler,                            /* IRQ 0 */
};

/* Written from outside: by the watched writes, the hook at trigger(), the monitor. */
__attribute__((section(".noinit"))) volatile uint32_t sink;   /* .noinit: Reset_Handler does not write it */
volatile uint32_t hook_mailbox;
volatile uint32_t mailbox;

/* What the firmware saw (recorded at the end). Writers: the handlers count
 * their own entries; main writes the rest. */
volatile uint32_t n_pendsv, n_systick, n_external;
volatile uint32_t hook_seen;
volatile uint32_t pause_value[3];       /* mailbox at the end of each wait for the monitor */
volatile uint32_t wait_rounds[2];       /* rounds of the first two waits */

/* Control of the return matrix (only writer: main). */
volatile uint32_t nest;                 /* 1: PendSV requests SysTick inside its handler */
volatile uint32_t nested_outer;         /* NESTED: exception whose handler requests nested_target */
volatile uint32_t nested_target;        /* NESTED: exception requested inside nested_outer */
volatile uint32_t monitor_wait;         /* 1: PendSV waits for the monitor's next pause */

/* ───────── hook points: each is a call, the hook sits at its 1st instruction ───────── */

/* Marked point: records DWT_CYCCNT. */
void mark(void)
{
    record_value(DWT->CYCCNT);
}

/* The only write to the watched addresses (sink and ICSR): the write hook
 * must report this instruction, with the address and value in R0 and R1. */
void store(volatile uint32_t *address, uint32_t value)
{
    *address = value;
}

void trigger(void) { }                     /* the hook here writes hook_mailbox */
void stress(void) { }                      /* load on one address hook */
void phase_mark(uint32_t phase) { (void)phase; }   /* R0 = matrix cell exercised next */

/* ───────── requests ───────── */

/* The barriers make the request take effect before the next instruction. */
static void pend(uint32_t icsr_bits)
{
    store(&SCB->ICSR, icsr_bits);
    __DSB();
    __ISB();
}

static void request_external_by_stir(void)
{
    NVIC->STIR = (uint32_t)EXTERNAL_LINE;
    __DSB();
    __ISB();
}

static void request_exception(uint32_t exception)
{
    if (exception == EXC_PENDSV) {
        pend(SCB_ICSR_PENDSVSET_Msk);
    } else if (exception == EXC_SYSTICK) {
        pend(SCB_ICSR_PENDSTSET_Msk);
    } else {
        request_external_by_stir();
    }
}

static void set_priority(uint32_t exception, uint32_t priority)
{
    IRQn_Type line = exception == EXC_PENDSV ? PendSV_IRQn : exception == EXC_SYSTICK ? SysTick_IRQn : EXTERNAL_LINE;
    NVIC_SetPriority(line, priority);
}

/* Waits until the monitor writes a new value to mailbox; returns the rounds. */
static uint32_t wait_for_monitor(uint32_t old)
{
    uint32_t rounds = 0U;
    while (mailbox == old) {
        rounds++;
    }
    return rounds;
}

/* ───────── handlers ───────── */

/* Called by every handler: NESTED requests the target from inside nested_outer;
 * in the monitor's nesting phase, PendSV stays active until the next pause. */
static void nested_request(uint32_t exception)
{
    if (nested_outer == exception) {
        request_exception(nested_target);
    }
    if (exception == EXC_PENDSV && monitor_wait != 0U) {
        (void)wait_for_monitor(pause_value[1]);
    }
}

void PendSV_Handler(void)
{
    n_pendsv++;
    nested_request(EXC_PENDSV);
    if (nest != 0U) {
        pend(SCB_ICSR_PENDSTSET_Msk);       /* SysTick (higher priority) preempts here */
    }
}

void SysTick_Handler(void)
{
    n_systick++;
    nested_request(EXC_SYSTICK);
}

void External_Handler(void)
{
    n_external++;
    nested_request(EXC_EXTERNAL);
}

/* ───────── the steps of main ───────── */

static void start_cycle_counter(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

/* Marked points around a loop, watched writes, and PendSV/SysTick entries:
 * simple, chained (both pending under PRIMASK) and nested. The 1st pass
 * translates the code, the 2nd reuses the translation. */
static void core_exceptions(uint32_t pass)
{
    mark();
    for (volatile uint32_t i = 0U; i < 10U; i++) {
    }
    mark();
    store(&sink, 0x11111111U + pass);
    store(&sink, 0xA5A5A5A5U);
    mark();
    pend(SCB_ICSR_PENDSVSET_Msk);
    mark();
    __disable_irq();
    store(&SCB->ICSR, SCB_ICSR_PENDSVSET_Msk | SCB_ICSR_PENDSTSET_Msk);
    __enable_irq();
    __ISB();
    mark();
    nest = 1U;
    pend(SCB_ICSR_PENDSVSET_Msk);
    nest = 0U;
    mark();
}

/* Return matrix: each source (PendSV, SysTick, IRQ 0 by STIR, IRQ 0 by the
 * monitor) returns once in each situation (simple, tail-chain, nested).
 * One cell: `target` ends in `situation`; the other exception (lower
 * priority) is PendSV, or SysTick when the target is PendSV. */
static void exercise(uint32_t phase, uint32_t target, uint32_t situation)
{
    uint32_t other = target == EXC_PENDSV ? EXC_SYSTICK : EXC_PENDSV;
    set_priority(target, 4U);
    set_priority(other, 8U);
    nested_outer = 0U;
    nested_target = target;
    phase_mark(phase);
    if (situation == SIMPLE) {
        request_exception(target);
    } else if (situation == CHAIN) {
        __disable_irq();
        request_exception(target);
        request_exception(other);
        __enable_irq();
        __ISB();
    } else {
        nested_outer = other;
        request_exception(other);
        nested_outer = 0U;
    }
}

/* Phases 1..9: PendSV, SysTick and the external line (STIR), each in the three situations. */
static void return_matrix_by_firmware(void)
{
    static const uint32_t sources[3] = {EXC_PENDSV, EXC_SYSTICK, EXC_EXTERNAL};
    for (uint32_t k = 0U; k < 3U; k++) {
        for (uint32_t situation = SIMPLE; situation <= NESTED; situation++) {
            exercise(1U + k * 3U + situation, sources[k], situation);
        }
    }
}

static void address_hook_load(void)
{
    for (uint32_t i = 0U; i < 10000U; i++) {
        stress();
    }
}

static void hook_writes_memory(void)
{
    trigger();
    hook_seen = hook_mailbox;
    mark();
}

/* Phases 10..12: the monitor requests the external line at each of its three
 * pauses; the firmware is waiting (simple), has PendSV pending under PRIMASK
 * (chain) or is inside PendSV (nested). */
static void return_matrix_by_monitor(void)
{
    set_priority(EXC_EXTERNAL, 4U);
    set_priority(EXC_PENDSV, 8U);
    phase_mark(10U);
    wait_rounds[0] = wait_for_monitor(0U);
    pause_value[0] = mailbox;
    __disable_irq();
    pend(SCB_ICSR_PENDSVSET_Msk);
    phase_mark(11U);
    wait_rounds[1] = wait_for_monitor(pause_value[0]);
    pause_value[1] = mailbox;
    __enable_irq();
    __ISB();
    phase_mark(12U);
    monitor_wait = 1U;
    pend(SCB_ICSR_PENDSVSET_Msk);
    monitor_wait = 0U;
    pause_value[2] = mailbox;
    mark();
}

/* After the marked points; same order as FIELDS in scripts/instruments.py. */
static void record_results(void)
{
    record_value(selected_case);
    record_value(hook_seen);
    record_value(pause_value[0]);
    record_value(pause_value[1]);
    record_value(pause_value[2]);
    record_value(wait_rounds[0]);
    record_value(wait_rounds[1]);
    record_value(n_pendsv);
    record_value(n_systick);
    record_value(n_external);
}

int main(void)
{
    SCB->VTOR = (uint32_t)vectors;
    NVIC_SetPriority(PendSV_IRQn, 15U);
    NVIC_SetPriority(SysTick_IRQn, 8U);
    NVIC_SetPriority(EXTERNAL_LINE, 6U);
    NVIC_EnableIRQ(EXTERNAL_LINE);
    start_cycle_counter();

    for (uint32_t pass = 0U; pass < 2U; pass++) {     /* one copy of the code, run twice */
        core_exceptions(pass);
    }
    return_matrix_by_firmware();
    address_hook_load();
    hook_writes_memory();
    return_matrix_by_monitor();

    record_results();
    finish_case();
}
