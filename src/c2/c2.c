/*
 * src/c2/c2.c — C2, interrupts and timer. Cases in order: each one relies on the
 * results of the ones before it. One case per boot (selected_case).
 *
 *   Rules of the NVIC and of an exception (document oracle, Renode)
 *    1  c2_01_pending_and_enable        per point: pending, active, services before and after the enable; exception; active in the handler
 *    2  c2_02_priority_and_tie          per point: service order
 *    3  c2_03_nested_preemption         per point: service order, EXC_RETURN of the second handler
 *    4  c2_04_masks                     PRIMASK points; BASEPRI and BASEPRI_MAX: value read | served priorities << 8
 *    5  c2_05_wfi_and_primask           services after each wake-up and after clearing PRIMASK
 *    6  c2_06_tail_chaining             exceptions served; instruction counts from the hooks
 *   Cost of an exception (board oracle: the same binary in Renode and on the board)
 *    7  c2_07_exception_cost            ticks of the entry, of the return and of the chaining
 *   Timers as the source (document oracle, Renode)
 *    8  c2_08_timer_period              instants from the hooks
 *    9  c2_09_repeated_request          requests during the service and with the flag still set
 *   What only the board answers (board oracle)
 *   10  c2_10_timer_tie                 per point: service order
 *   11  c2_11_coalescence               per window: DWT at the mask and at the release, last entry; entries
 *   12  c2_12_timer_count_at_entry      per event: DWT before and after the NOP sled; entries
 *   13  c2_13_flag_clear_before_return  per tail: first and last entry index; entries
 *
 * Entries = the number of entries, then (TIM2_CNT, DWT_CYCCNT) of each one.
 * The point tables are repeated in scripts/c2.py, in the same order.
 * Clock: HSI 8 MHz, AHB/APB1/APB2 ÷ 1, flash 0 wait states with prefetch, so one
 * cycle = one tick of DWT_CYCCNT and of the timers. No pin is driven.
 * What the board measures is fixed in assembly: registers, encoding and offset in
 * the 64-bit flash line, on which the cost of an instruction depends.
 */
#include "case.h"
#include "stm32f1xx.h"
#include "stm32f1xx_ll_bus.h"
#include "stm32f1xx_ll_rcc.h"
#include "stm32f1xx_ll_system.h"
#include "stm32f1xx_ll_tim.h"

extern uint32_t _estack[];

#define N_OF(a)             (sizeof(a) / sizeof((a)[0]))
#define IRQ_LINES           43U     /* IRQ 0..42 of the medium-density family (RM0008 Tab. 63) */
#define EXCEPTIONS          (16U + IRQ_LINES)
#define SERVICE_LOG_SIZE    8U      /* circular; a case reads at most 4 services at a time */
#define DEFAULT_PRIORITY    8U
#define TIM2_EXCEPTION      (16U + (uint32_t)TIM2_IRQn)
#define TIM3_EXCEPTION      (16U + (uint32_t)TIM3_IRQn)

/* Written only by the handlers; main only reads them. The cases that use the
 * order of the log request at fixed points, and appending is the first work of
 * a handler, so no preemption falls in the middle of an append. Each count is
 * written only by the handler of its own exception. */
static volatile uint32_t service_log[SERVICE_LOG_SIZE];
static volatile uint32_t service_total;
static volatile uint32_t service_count[EXCEPTIONS];
static volatile uint32_t round_ready;       /* round main is in; only main writes, the monitor reads */

/* ─────────────────────────── common steps ─────────────────────────── */

/* ARM recommendation after writing to the NVIC or to the masks: the effect holds
 * in the following instructions. */
static inline void barrier(void)
{
    __DSB();
    __ISB();
}

/* Line disabled, with no pending request and with the given priority. */
static void prepare_line(uint32_t line, uint32_t priority)
{
    IRQn_Type irq = (IRQn_Type)line;
    NVIC_DisableIRQ(irq);
    NVIC_ClearPendingIRQ(irq);
    NVIC_SetPriority(irq, priority);
    barrier();
}

static void spin(uint32_t iterations)
{
    for (volatile uint32_t i = 0U; i < iterations; i++) {
    }
}

/* Wait until the log has `target` services (or give up: the record shows it). */
static void wait_for_services(uint32_t target)
{
    for (uint32_t i = 0U; i < 1000U && service_total < target; i++) {
    }
}

static void wait_for_ticks(uint32_t ticks)
{
    uint32_t start = DWT->CYCCNT;
    while (DWT->CYCCNT - start < ticks) {
    }
}

/* Append the running exception to the log and count the service. */
static inline uint32_t note_service(void)
{
    uint32_t exception = __get_IPSR() & 0x1FFU;
    uint32_t total = service_total;
    service_log[total % SERVICE_LOG_SIZE] = exception;
    service_total = total + 1U;
    service_count[exception]++;
    return exception;
}

static inline uint32_t served_exception(uint32_t total_before)
{
    return service_log[total_before % SERVICE_LOG_SIZE];
}

/* Up to 3 services from `total_before`, 9 bits each, and the total in bits 27..31. */
static uint32_t service_order(uint32_t total_before)
{
    uint32_t total = service_total - total_before;
    uint32_t word = (total < 31U ? total : 31U) << 27;
    for (uint32_t k = 0U; k < total && k < 3U; k++) {
        word |= (served_exception(total_before + k) & 0x1FFU) << (9U * k);
    }
    return word;
}

/* The handler of cases that only need the service noted. */
static void note_service_handler(void)
{
    (void)note_service();
}

/* ───────────── rules of the NVIC and of an exception ───────────── */

/* First, middle and last line with no source on the project platform
 * (renode/stm32f103_hsi8.repl): the same behaviour along the NVIC. */
static const uint8_t THREE_LINES[] = {0, 20, 42};

/* C2-01: a line requested while disabled stays pending and is not served; once
 * enabled it is served once, active during the service. Through both request paths. */
static volatile uint32_t active_in_handler;

static void line_state_handler(void)
{
    uint32_t exception = note_service();
    active_in_handler = NVIC_GetActive((IRQn_Type)(exception - 16U));
}

static void record_line_state(IRQn_Type irq, uint32_t total_before)
{
    record_value(NVIC_GetPendingIRQ(irq));
    record_value(NVIC_GetActive(irq));
    record_value(service_total - total_before);
}

static void c2_01_pending_and_enable(void)
{
    for (uint32_t i = 0U; i < N_OF(THREE_LINES); i++) {
        for (uint32_t through_ispr = 0U; through_ispr < 2U; through_ispr++) {
            uint32_t line = THREE_LINES[i];
            IRQn_Type irq = (IRQn_Type)line;
            prepare_line(line, DEFAULT_PRIORITY);
            uint32_t total_before = service_total;
            if (through_ispr != 0U) {
                NVIC_SetPendingIRQ(irq);
            } else {
                NVIC->STIR = line;
            }
            barrier();
            spin(16U);
            record_line_state(irq, total_before);
            NVIC_EnableIRQ(irq);
            barrier();
            spin(16U);
            record_line_state(irq, total_before);
            record_value(served_exception(total_before));
            record_value(active_in_handler);
            NVIC_DisableIRQ(irq);
        }
    }
}

/* C2-02: priorities of THREE_LINES. 6 strict orders, 6 ties of two lines (below
 * and above the third), a tie of three in the middle and at both ends. */
static const uint8_t PRIORITY_TRIPLES[][3] = {
    {0, 7, 15}, {0, 15, 7}, {7, 0, 15}, {7, 15, 0}, {15, 0, 7}, {15, 7, 0},
    {7, 7, 0}, {7, 7, 15}, {7, 0, 7}, {7, 15, 7}, {0, 7, 7}, {15, 7, 7},
    {8, 8, 8}, {0, 0, 0}, {15, 15, 15},
};
/* (PRIGROUP, priorities) with subpriorities: same group, different subpriority; then a full tie. */
static const uint8_t GROUPED_TRIPLES[][4] = {{5U, 5U, 4U, 6U}, {5U, 5U, 5U, 4U}};

static void serve_three_lines(const uint8_t priorities[3])
{
    __disable_irq();
    for (uint32_t k = 0U; k < N_OF(THREE_LINES); k++) {
        prepare_line(THREE_LINES[k], priorities[k]);
        NVIC_EnableIRQ((IRQn_Type)THREE_LINES[k]);
    }
    uint32_t total_before = service_total;
    for (uint32_t k = 0U; k < N_OF(THREE_LINES); k++) {
        NVIC_SetPendingIRQ((IRQn_Type)THREE_LINES[k]);
    }
    barrier();
    __enable_irq();
    __ISB();
    wait_for_services(total_before + 3U);
    record_value(service_order(total_before));
}

static void c2_02_priority_and_tie(void)
{
    for (uint32_t i = 0U; i < N_OF(PRIORITY_TRIPLES); i++) {
        serve_three_lines(PRIORITY_TRIPLES[i]);
    }
    for (uint32_t i = 0U; i < N_OF(GROUPED_TRIPLES); i++) {
        NVIC_SetPriorityGrouping(GROUPED_TRIPLES[i][0]);
        serve_three_lines(&GROUPED_TRIPLES[i][1]);
    }
    NVIC_SetPriorityGrouping(0U);
}

/* C2-03: the handler of A requests B and then notes A | AFTER_NESTED_REQUEST. Pairs
 * (priority of A, priority of B): B higher by one, equal, lower by one, at both
 * ends and in the middle; each pair in both roles. */
#define AFTER_NESTED_REQUEST 0x100U
static const uint8_t TWO_LINES[] = {0, 42};     /* the ends of the NVIC */
static const uint8_t PRIORITY_PAIRS[][2] = {
    {1, 0}, {8, 7}, {15, 14}, {0, 0}, {8, 8}, {15, 15}, {0, 1}, {8, 9}, {14, 15},
};
/* (PRIGROUP, A, B): only the group priority preempts (ARMv7-M §B1.5.4). B lower in value
 * inside the group of A and in a higher group, with 2 bits, 3 bits and no bit of group. */
static const uint8_t GROUPED_PAIRS[][3] = {
    {5U, 5U, 4U}, {5U, 8U, 7U}, {4U, 3U, 2U}, {4U, 8U, 7U}, {7U, 8U, 7U},
};

/* Written only by main, with neither line active. */
static volatile uint32_t nesting_exception;
static volatile uint32_t nested_line;
static volatile uint32_t nested_exc_return;     /* of B: to the handler of A if it preempted, else to Thread */

static void nested_request_handler(void)
{
    uint32_t exc_return;
    __asm volatile("mov %0, lr" : "=r"(exc_return));
    uint32_t exception = note_service();
    if (exception == nesting_exception) {
        NVIC->STIR = nested_line;
        barrier();
        uint32_t total = service_total;
        service_log[total % SERVICE_LOG_SIZE] = exception | AFTER_NESTED_REQUEST;
        service_total = total + 1U;
    } else {
        nested_exc_return = exc_return;
    }
}

static void request_nested(uint32_t line_a, uint32_t line_b, uint32_t priority_a, uint32_t priority_b)
{
    prepare_line(line_a, priority_a);
    prepare_line(line_b, priority_b);
    NVIC_EnableIRQ((IRQn_Type)line_a);
    NVIC_EnableIRQ((IRQn_Type)line_b);
    nested_line = line_b;
    nesting_exception = 16U + line_a;
    barrier();
    uint32_t total_before = service_total;
    NVIC->STIR = line_a;
    barrier();
    wait_for_services(total_before + 3U);
    record_value(service_order(total_before));
    record_value(nested_exc_return);
    nesting_exception = 0U;
    NVIC_DisableIRQ((IRQn_Type)line_a);
    NVIC_DisableIRQ((IRQn_Type)line_b);
}

static void c2_03_nested_preemption(void)
{
    for (uint32_t role = 0U; role < 2U; role++) {
        for (uint32_t i = 0U; i < N_OF(PRIORITY_PAIRS); i++) {
            request_nested(TWO_LINES[role], TWO_LINES[1U - role], PRIORITY_PAIRS[i][0], PRIORITY_PAIRS[i][1]);
        }
    }
    for (uint32_t i = 0U; i < N_OF(GROUPED_PAIRS); i++) {
        NVIC_SetPriorityGrouping(GROUPED_PAIRS[i][0]);
        request_nested(TWO_LINES[0], TWO_LINES[1], GROUPED_PAIRS[i][1], GROUPED_PAIRS[i][2]);
    }
    NVIC_SetPriorityGrouping(0U);
}

/* C2-04: PRIMASK on a priority; BASEPRI = value; BASEPRI = priority << 4, then
 * BASEPRI_MAX = value. Values at and around the implemented bits (7:4). With
 * subpriorities BASEPRI counts only through its group bits (ARMv7-M §B1.5.4). */
#define MASKS_LINE 0U
static const uint8_t PRIMASK_PRIORITIES[] = {0, 8, 15};    /* highest, middle, lowest: PRIMASK holds every priority */
static const uint8_t BASEPRI_VALUES[] = {0x00, 0x0F, 0x10, 0x1F, 0x80, 0x8F, 0xF0, 0xFF};
static const uint8_t BASEPRI_MAX_POINTS[][2] = {
    {0, 0x00}, {0, 0x80}, {0, 0x8F},                            /* no mask yet: 0 changes nothing, any other value sets it */
    {8, 0x00}, {8, 0x70}, {8, 0x7F}, {8, 0x80}, {8, 0x8F}, {8, 0x90},   /* mask at 8: 0, above it, equal to it, below it */
};
static const uint8_t GROUPED_BASEPRI_POINTS[][2] = {{4U, 0x50}, {5U, 0x50}, {7U, 0x50}};   /* (PRIGROUP, BASEPRI): 3, 2 and no bit of group */

/* The effect of the current mask on the 16 priorities. Bit p = 1: priority p was served. */
static uint32_t served_priorities(void)
{
    uint32_t served = 0U;
    for (uint32_t priority = 0U; priority < 16U; priority++) {
        NVIC_SetPriority((IRQn_Type)MASKS_LINE, priority);
        uint32_t total_before = service_total;
        NVIC_SetPendingIRQ((IRQn_Type)MASKS_LINE);
        barrier();
        spin(4U);
        if (service_total != total_before) {
            served |= 1U << priority;
        }
        NVIC_ClearPendingIRQ((IRQn_Type)MASKS_LINE);
        barrier();
    }
    return served;
}

static void record_basepri_effect(void)
{
    barrier();
    uint32_t value_read = __get_BASEPRI();
    record_value(value_read | (served_priorities() << 8));
    __set_BASEPRI(0U);
    barrier();
}

static void c2_04_masks(void)
{
    prepare_line(MASKS_LINE, 0U);
    for (uint32_t k = 0U; k < N_OF(PRIMASK_PRIORITIES); k++) {
        NVIC_SetPriority((IRQn_Type)MASKS_LINE, PRIMASK_PRIORITIES[k]);
        NVIC_EnableIRQ((IRQn_Type)MASKS_LINE);
        __disable_irq();
        uint32_t total_before = service_total;
        NVIC_SetPendingIRQ((IRQn_Type)MASKS_LINE);
        barrier();
        spin(4U);
        uint32_t served_while_masked = service_total - total_before;
        uint32_t pending = NVIC_GetPendingIRQ((IRQn_Type)MASKS_LINE);
        __enable_irq();
        __ISB();
        spin(4U);
        record_value(served_while_masked | (pending << 4) | ((service_total - total_before) << 8));
    }
    NVIC_EnableIRQ((IRQn_Type)MASKS_LINE);
    for (uint32_t k = 0U; k < N_OF(BASEPRI_VALUES); k++) {
        __set_BASEPRI(BASEPRI_VALUES[k]);
        record_basepri_effect();
    }
    for (uint32_t k = 0U; k < N_OF(BASEPRI_MAX_POINTS); k++) {
        __set_BASEPRI((uint32_t)BASEPRI_MAX_POINTS[k][0] << 4);
        __set_BASEPRI_MAX(BASEPRI_MAX_POINTS[k][1]);
        record_basepri_effect();
    }
    for (uint32_t k = 0U; k < N_OF(GROUPED_BASEPRI_POINTS); k++) {
        NVIC_SetPriorityGrouping(GROUPED_BASEPRI_POINTS[k][0]);
        __set_BASEPRI(GROUPED_BASEPRI_POINTS[k][1]);
        record_basepri_effect();
    }
    NVIC_SetPriorityGrouping(0U);
    NVIC_DisableIRQ((IRQn_Type)MASKS_LINE);
}

/* C2-05: the monitor requests the line while the core is in WFI: with PRIMASK = 0
 * it is served; with PRIMASK = 1 the core wakes and it stays pending until PRIMASK
 * is cleared. */
#define WFI_LINE 20U    /* a line without a source, away from the ends of the NVIC */

static void c2_05_wfi_and_primask(void)
{
    prepare_line(WFI_LINE, DEFAULT_PRIORITY);
    NVIC_EnableIRQ((IRQn_Type)WFI_LINE);
    barrier();
    round_ready = 1U;
    __WFI();
    record_value(service_count[16U + WFI_LINE]);
    __disable_irq();
    barrier();
    round_ready = 2U;
    __WFI();
    record_value(service_count[16U + WFI_LINE]);
    __enable_irq();
    __ISB();
    record_value(service_count[16U + WFI_LINE]);
}

/* C2-06: pending lines with PRIMASK = 1 and distinct priorities (first round: the
 * last line highest; second round: the first line highest), then released. The hooks
 * count the main-flow instructions between the handlers. */
static const uint8_t CHAIN_LINES[] = {0, 20, 35, 42};  /* ascending: the ends of the NVIC, two in each of its first two words */

static void pend_chain_lines(uint32_t first_line_highest)
{
    uint32_t lines = N_OF(CHAIN_LINES);
    __disable_irq();
    for (uint32_t i = 0U; i < lines; i++) {
        prepare_line(CHAIN_LINES[i], first_line_highest != 0U ? i : lines - 1U - i);
        NVIC_EnableIRQ((IRQn_Type)CHAIN_LINES[i]);
    }
    for (uint32_t i = 0U; i < lines; i++) {
        NVIC_SetPendingIRQ((IRQn_Type)CHAIN_LINES[i]);
    }
    barrier();
}

static void disable_chain_lines(void)
{
    for (uint32_t i = 0U; i < N_OF(CHAIN_LINES); i++) {
        NVIC_DisableIRQ((IRQn_Type)CHAIN_LINES[i]);
    }
}

static void c2_06_tail_chaining(void)
{
    for (uint32_t round = 0U; round < 2U; round++) {
        uint32_t total_before = service_total;
        pend_chain_lines(round);
        __enable_irq();
        __ISB();
        wait_for_services(total_before + N_OF(CHAIN_LINES));
        for (uint32_t k = 0U; k < N_OF(CHAIN_LINES); k++) {
            record_value(served_exception(total_before + k));
        }
        disable_chain_lines();
    }
}

/* ───────────────────────── cost of an exception ───────────────────────── */

/* C2-07: the handler reads DWT_CYCCNT first and marks it last, so the board and Renode
 * give the ticks of the entry (request to first read), of the return (mark to the read
 * after it) and of the chaining (mark to the first read of the next handler). */
#define COST_ENTRIES N_OF(CHAIN_LINES)

static volatile uint32_t cost_total;
static volatile uint32_t cost_entry_time[COST_ENTRIES];
static volatile uint32_t cost_previous_mark[COST_ENTRIES];
__attribute__((used)) static volatile uint32_t cost_mark;

__attribute__((used, noipa)) static void store_cost_entry(uint32_t time)
{
    uint32_t total = cost_total;
    if (total < COST_ENTRIES) {
        cost_entry_time[total] = time;
        cost_previous_mark[total] = cost_mark;
        cost_total = total + 1U;
    }
}

__attribute__((naked, aligned(8))) static void exception_cost_handler(void)
{
    __asm volatile("ldr r2, =0xE0001004\n\t"        /* DWT_CYCCNT */
                   "ldr r0, [r2]\n\t"
                   "push {r3, lr}\n\t"
                   "bl store_cost_entry\n\t"
                   "pop {r3, lr}\n\t"
                   "ldr r1, =cost_mark\n\t"
                   "ldr r2, =0xE0001004\n\t"
                   "ldr r3, [r2]\n\t"
                   "str r3, [r1]\n\t"
                   "bx lr\n\t"
                   ".ltorg");
}

/* DWT read, the request through STIR, then NOPs: a single-cycle instruction is interrupted. */
__attribute__((noipa)) static uint32_t read_then_request(uint32_t line)
{
    register uint32_t time __asm("r0");
    register uint32_t requested __asm("r1") = line;
    register volatile uint32_t *software_trigger __asm("r2") = &NVIC->STIR;
    register const volatile uint32_t *cycle_counter __asm("r3") = &DWT->CYCCNT;
    __asm volatile(".balign 8\n\t"
                   "ldr r0, [r3]\n\t"
                   "str r1, [r2]\n\t"
                   ".rept 32\n\tnop.n\n\t.endr"
                   : "=&r"(time)
                   : "r"(requested), "r"(software_trigger), "r"(cycle_counter)
                   : "memory");
    return time;
}

/* SVC is synchronous: the exception returns exactly to the read after it. */
__attribute__((noipa)) static uint32_t call_then_read(void)
{
    register uint32_t time __asm("r0");
    register const volatile uint32_t *cycle_counter __asm("r3") = &DWT->CYCCNT;
    __asm volatile(".balign 8\n\t"
                   "svc 0\n\t"
                   "ldr r0, [r3]"
                   : "=&r"(time)
                   : "r"(cycle_counter)
                   : "memory");
    return time;
}

static void c2_07_exception_cost(void)
{
    for (uint32_t i = 0U; i < N_OF(THREE_LINES); i++) {
        uint32_t line = THREE_LINES[i];
        prepare_line(line, DEFAULT_PRIORITY);
        NVIC_EnableIRQ((IRQn_Type)line);
        barrier();
        cost_total = 0U;
        uint32_t requested_at = read_then_request(line);
        record_value(cost_entry_time[0] - requested_at);
        NVIC_DisableIRQ((IRQn_Type)line);
    }
    for (uint32_t i = 0U; i < N_OF(THREE_LINES); i++) {
        cost_total = 0U;
        uint32_t returned_at = call_then_read();
        record_value(returned_at - cost_mark);
    }
    cost_total = 0U;
    pend_chain_lines(0U);
    __enable_irq();
    __ISB();
    wait_for_ticks(1000U);
    for (uint32_t k = 1U; k < COST_ENTRIES; k++) {
        record_value(cost_entry_time[k] - cost_previous_mark[k]);
    }
    disable_chain_lines();
}

/* ─────────────────────── timers as the source ─────────────────────── */

/* Stopped, counting up, PSC and ARR loaded by the update generation, flag and pending
 * request cleared, update interrupt enabled, ARR preload on. URS = 1 keeps that update
 * generation from setting the flag (RM0008 §15.3.2); the clear is read back so that it
 * reaches the timer before the NVIC clear (on the board the request would come back). */
static void prepare_timer(TIM_TypeDef *timer, IRQn_Type irq, uint32_t prescaler, uint32_t auto_reload)
{
    LL_TIM_DisableCounter(timer);
    LL_TIM_DisableIT_UPDATE(timer);
    LL_TIM_SetUpdateSource(timer, LL_TIM_UPDATESOURCE_COUNTER);
    LL_TIM_SetPrescaler(timer, prescaler);
    LL_TIM_SetAutoReload(timer, auto_reload);
    LL_TIM_SetCounter(timer, 0U);
    LL_TIM_GenerateEvent_UPDATE(timer);
    LL_TIM_ClearFlag_UPDATE(timer);
    (void)LL_TIM_ReadReg(timer, SR);
    NVIC_ClearPendingIRQ(irq);
    NVIC_SetPriority(irq, DEFAULT_PRIORITY);
    LL_TIM_SetUpdateSource(timer, LL_TIM_UPDATESOURCE_REGULAR);
    LL_TIM_EnableIT_UPDATE(timer);
    LL_TIM_EnableARRPreload(timer);
    NVIC_EnableIRQ(irq);
    barrier();
}

static void stop_timer(TIM_TypeDef *timer, IRQn_Type irq)
{
    LL_TIM_DisableCounter(timer);
    LL_TIM_DisableIT_UPDATE(timer);
    LL_TIM_ClearFlag_UPDATE(timer);
    (void)LL_TIM_ReadReg(timer, SR);
    NVIC_DisableIRQ(irq);
    NVIC_ClearPendingIRQ(irq);
    barrier();
}

static void timer_service_handler(void)
{
    uint32_t exception = __get_IPSR() & 0x1FFU;
    if (exception == TIM2_EXCEPTION) {
        LL_TIM_ClearFlag_UPDATE(TIM2);
    } else if (exception == TIM3_EXCEPTION) {
        LL_TIM_ClearFlag_UPDATE(TIM3);
    }
    (void)note_service();
}

/* C2-08: (PSC, ARR) of the same product, at the ends and in the middle; then ARR small,
 * and one more product with a large ARR. */
#define SERVICES_PER_PAIR 4U            /* 3 periods */
static const uint16_t TIMER_PAIRS[][2] = {{0U, 999U}, {9U, 99U}, {99U, 9U}, {99U, 3U}, {99U, 1U}, {7U, 999U}};

static void c2_08_timer_period(void)
{
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    for (uint32_t k = 0U; k < N_OF(TIMER_PAIRS); k++) {
        prepare_timer(TIM2, TIM2_IRQn, TIMER_PAIRS[k][0], TIMER_PAIRS[k][1]);
        uint32_t count_before = service_count[TIM2_EXCEPTION];
        LL_TIM_EnableCounter(TIM2);
        while (service_count[TIM2_EXCEPTION] < count_before + SERVICES_PER_PAIR) {
        }
        stop_timer(TIM2, TIM2_IRQn);
    }
}

/* C2-09: a request during the service (PM0056 §4.3.9, TRM §8.3). Software: the handler
 * pends its own line, which becomes active and pending and runs once more. Level: the
 * handler leaves the flag set, so the request stays asserted and the handler re-enters
 * until it clears the flag; and a clear of the pending state does not hold while the
 * signal is asserted. */
#define REPEAT_LINE         20U
#define LEVEL_ENTRIES       4U
#define LEVEL_AUTO_RELOAD   999U
#define LEVEL_WINDOW_TICKS  1500U       /* the first update event, before the second */

static volatile uint32_t pending_in_handler;
static volatile uint32_t active_in_repeated_handler;

static void repeated_request_handler(void)
{
    uint32_t exception = note_service();
    if (exception == TIM2_EXCEPTION) {
        if (service_count[exception] >= LEVEL_ENTRIES) {
            LL_TIM_ClearFlag_UPDATE(TIM2);
            (void)LL_TIM_ReadReg(TIM2, SR);
        }
    } else if (service_count[exception] == 1U) {
        IRQn_Type irq = (IRQn_Type)(exception - 16U);
        NVIC_SetPendingIRQ(irq);
        barrier();
        pending_in_handler = NVIC_GetPendingIRQ(irq);
        active_in_repeated_handler = NVIC_GetActive(irq);
    }
}

static void c2_09_repeated_request(void)
{
    prepare_line(REPEAT_LINE, DEFAULT_PRIORITY);
    NVIC_EnableIRQ((IRQn_Type)REPEAT_LINE);
    NVIC->STIR = REPEAT_LINE;
    barrier();
    spin(16U);
    record_value(pending_in_handler);
    record_value(active_in_repeated_handler);
    record_value(service_count[16U + REPEAT_LINE]);
    NVIC_DisableIRQ((IRQn_Type)REPEAT_LINE);

    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    prepare_timer(TIM2, TIM2_IRQn, 0U, LEVEL_AUTO_RELOAD);
    LL_TIM_EnableCounter(TIM2);
    wait_for_ticks(LEVEL_WINDOW_TICKS);
    record_value(service_count[TIM2_EXCEPTION]);
    stop_timer(TIM2, TIM2_IRQn);

    uint32_t count_before = service_count[TIM2_EXCEPTION];
    __disable_irq();
    prepare_timer(TIM2, TIM2_IRQn, 0U, LEVEL_AUTO_RELOAD);
    LL_TIM_EnableCounter(TIM2);
    wait_for_ticks(LEVEL_WINDOW_TICKS);
    LL_TIM_DisableCounter(TIM2);
    record_value(NVIC_GetPendingIRQ(TIM2_IRQn));
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    barrier();
    record_value(NVIC_GetPendingIRQ(TIM2_IRQn));
    LL_TIM_ClearFlag_UPDATE(TIM2);
    (void)LL_TIM_ReadReg(TIM2, SR);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    barrier();
    record_value(NVIC_GetPendingIRQ(TIM2_IRQn));
    __enable_irq();
    __ISB();
    spin(16U);
    record_value(service_count[TIM2_EXCEPTION] - count_before);
    stop_timer(TIM2, TIM2_IRQn);
}

/* C2-10: the same request from two peripherals. Both pending under PRIMASK, started in
 * either order; then a start synchronized by hardware, in both master roles, the only tie
 * a firmware reaches with the masks off: two writes to the counters are at least 2 ticks
 * apart, and the first to arrive is served first. Lower exception number first (TIM2). */
#define TIE_AUTO_RELOAD   999U
#define TIE_WINDOW_TICKS  1500U     /* the first update events, before the second */

static void prepare_tie(void)
{
    prepare_timer(TIM2, TIM2_IRQn, 0U, TIE_AUTO_RELOAD);
    prepare_timer(TIM3, TIM3_IRQn, 0U, TIE_AUTO_RELOAD);
}

static void record_order_and_stop_tie(uint32_t total_before)
{
    record_value(service_order(total_before));
    stop_timer(TIM2, TIM2_IRQn);
    stop_timer(TIM3, TIM3_IRQn);
}

static void tie_under_mask(TIM_TypeDef *first, TIM_TypeDef *second)
{
    __disable_irq();
    prepare_tie();
    uint32_t total_before = service_total;
    LL_TIM_EnableCounter(first);
    LL_TIM_EnableCounter(second);
    wait_for_ticks(TIE_WINDOW_TICKS);
    __enable_irq();
    __ISB();
    wait_for_services(total_before + 2U);
    record_order_and_stop_tie(total_before);
}

/* The master gives its enable as trigger output; the slave starts on it (RM0008 §15.3.15). */
__attribute__((noipa)) static void tie_of_synchronized_start(TIM_TypeDef *master, TIM_TypeDef *slave, uint32_t trigger)
{
    prepare_tie();
    uint32_t total_before = service_total;
    LL_TIM_SetTriggerOutput(master, LL_TIM_TRGO_ENABLE);
    LL_TIM_SetTriggerInput(slave, trigger);
    LL_TIM_SetSlaveMode(slave, LL_TIM_SLAVEMODE_TRIGGER);
    LL_TIM_EnableCounter(master);
    wait_for_ticks(TIE_WINDOW_TICKS);
    LL_TIM_SetSlaveMode(slave, LL_TIM_SLAVEMODE_DISABLED);
    LL_TIM_SetTriggerOutput(master, LL_TIM_TRGO_RESET);
    record_order_and_stop_tie(total_before);
}

static void c2_10_timer_tie(void)
{
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2 | LL_APB1_GRP1_PERIPH_TIM3);
    tie_under_mask(TIM2, TIM3);
    tie_under_mask(TIM3, TIM2);
    tie_of_synchronized_start(TIM2, TIM3, LL_TIM_TS_ITR1);      /* TIM3: ITR1 = TIM2 */
    tie_of_synchronized_start(TIM3, TIM2, LL_TIM_TS_ITR2);      /* TIM2: ITR2 = TIM3 */
}

/* ─────────────────── what only the board answers ─────────────────── */

/* TIM2 only: PSC = 0, ARR = 999, one period = 1000 ticks on the board. The firmware
 * observes itself; the analysis reads only the record. */
#define BOARD_AUTO_RELOAD   999U
#define EVENTS_PER_POINT    8U
#define ENTRY_CAPACITY      64U     /* C2-13: 5 tails × 8 events and the re-entries of the board */
#define SLED_LEAD_TICKS     40U     /* C2-12: main enters the sled this close to the update event */

typedef void (*tail_function)(void);

static volatile uint32_t entry_total;
static volatile uint32_t entry_timer_count[ENTRY_CAPACITY];
static volatile uint32_t entry_time[ENTRY_CAPACITY];
static volatile tail_function selected_tail;

/* Keeps the two reads of the entry; returns the tail main selected. */
__attribute__((used, noipa)) static tail_function store_entry(uint32_t timer_count, uint32_t time)
{
    uint32_t total = entry_total;
    if (total < ENTRY_CAPACITY) {
        entry_timer_count[total] = timer_count;
        entry_time[total] = time;
        entry_total = total + 1U;
    }
    return selected_tail;
}

/* Reads TIM2_CNT (C2-12: ticks since the update event) and DWT_CYCCNT first, stores
 * them and goes to the selected tail, which holds the return (LR = EXC_RETURN). */
__attribute__((naked, aligned(8))) static void self_observing_handler(void)
{
    __asm volatile("mov.w r1, #0x40000000\n\t"      /* TIM2 */
                   "ldr r0, [r1, #0x24]\n\t"        /* TIM2_CNT */
                   "ldr r2, =0xE0001004\n\t"        /* DWT_CYCCNT */
                   "ldr r1, [r2]\n\t"
                   "push {r3, lr}\n\t"
                   "bl store_entry\n\t"
                   "pop {r3, lr}\n\t"
                   "bx r0\n\t"
                   ".ltorg");
}

/* Tails: the clear of TIM2_SR at the start of a 64-bit line, then what is measured.
 * C2-13 counts the instructions between the clear and the return. */
#define TAIL(name, after_clear)                                       \
    __attribute__((naked, aligned(8))) static void name(void)         \
    {                                                                 \
        __asm volatile("mov.w r0, #0x40000000\n\t"  /* TIM2 */        \
                       "mvn.w r1, #1\n\t"           /* ~UIF */        \
                       "str r1, [r0, #0x10]\n\t"    /* TIM2_SR */     \
                       after_clear "bx lr");                          \
    }

TAIL(tail_clear_return, "")                                 /* k = 0 */
TAIL(tail_clear_nop_return, "nop.n\n\t")                    /* k = 1 */
TAIL(tail_clear_two_nops_return, "nop.n\n\tnop.n\n\t")      /* k = 2 */
TAIL(tail_clear_dsb_return, "dsb sy\n\t")                   /* the write completes before the return */
TAIL(tail_clear_read_back_return, "ldr r2, [r0, #0x10]\n\t")    /* the same, through a read of the timer; no re-entry spoils a measure */

static void prepare_board_timer(tail_function tail)
{
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    selected_tail = tail;
    prepare_timer(TIM2, TIM2_IRQn, 0U, BOARD_AUTO_RELOAD);
}

static void wait_for_entries(uint32_t total)
{
    while (entry_total < total) {
    }
}

static void record_entries(void)
{
    uint32_t total = entry_total;
    record_value(total);
    for (uint32_t i = 0U; i < total; i++) {
        record_value(entry_timer_count[i]);
        record_value(entry_time[i]);
    }
}

/* C2-11: synchronize on an entry, mask until DWT_CYCCNT advances the window, release
 * and wait for 3 entries. Windows in the middle of a period, away from a boundary:
 * no update event, one, two and three during the mask. */
static const uint16_t MASK_WINDOWS[] = {500U, 1500U, 2500U, 3500U};

static void c2_11_coalescence(void)
{
    prepare_board_timer(tail_clear_read_back_return);
    LL_TIM_EnableCounter(TIM2);
    wait_for_entries(2U);
    for (uint32_t k = 0U; k < N_OF(MASK_WINDOWS); k++) {
        wait_for_entries(entry_total + 1U);
        uint32_t masked_at = DWT->CYCCNT;
        __disable_irq();
        while (DWT->CYCCNT - masked_at < MASK_WINDOWS[k]) {
        }
        uint32_t released_at = DWT->CYCCNT;
        __enable_irq();
        __ISB();
        wait_for_entries(entry_total + 3U);
        record_value(masked_at);
        record_value(released_at);
        record_value(entry_total);
    }
    stop_timer(TIM2, TIM2_IRQn);
    record_entries();
}

/* DWT reads around 64 NOPs, so that the update event interrupts a single-cycle instruction. */
__attribute__((noipa)) static void read_around_nop_sled(uint32_t times[2])
{
    register uint32_t before __asm("r0");
    register uint32_t after __asm("r1");
    register const volatile uint32_t *cycle_counter __asm("r3") = &DWT->CYCCNT;
    __asm volatile(".balign 8\n\t"
                   "ldr r0, [r3]\n\t"
                   ".rept 64\n\tnop.n\n\t.endr\n\t"
                   "ldr r1, [r3]"
                   : "=&r"(before), "=&r"(after)
                   : "r"(cycle_counter)
                   : "memory");
    times[0] = before;
    times[1] = after;
}

static void c2_12_timer_count_at_entry(void)
{
    prepare_board_timer(tail_clear_read_back_return);
    LL_TIM_EnableCounter(TIM2);
    for (uint32_t k = 0U; k < EVENTS_PER_POINT; k++) {
        uint32_t total_before = entry_total;
        while (LL_TIM_GetCounter(TIM2) < BOARD_AUTO_RELOAD - SLED_LEAD_TICKS) {
        }
        uint32_t times[2];
        read_around_nop_sled(times);
        wait_for_entries(total_before + 1U);
        record_value(times[0]);
        record_value(times[1]);
    }
    stop_timer(TIM2, TIM2_IRQn);
    record_entries();
}

/* A fixed time per tail, so that a re-entry does not change the number of events. */
static const tail_function FLAG_CLEAR_TAILS[] = {
    tail_clear_return, tail_clear_nop_return, tail_clear_two_nops_return,
    tail_clear_dsb_return, tail_clear_read_back_return,
};

static void c2_13_flag_clear_before_return(void)
{
    uint32_t period = BOARD_AUTO_RELOAD + 1U;
    for (uint32_t p = 0U; p < N_OF(FLAG_CLEAR_TAILS); p++) {
        prepare_board_timer(FLAG_CLEAR_TAILS[p]);
        uint32_t first_entry = entry_total;
        LL_TIM_EnableCounter(TIM2);
        wait_for_ticks(EVENTS_PER_POINT * period + period / 2U);
        stop_timer(TIM2, TIM2_IRQn);
        record_value(first_entry);
        record_value(entry_total);
    }
    record_entries();
}

/* ───────────────────────────── boot ───────────────────────────── */

/* Each family of cases has its handler, on SVC and on every line. The table goes in VTOR,
 * which holds bits 29:9 of its address (PM0056 §4.4.4), so it is aligned to 512 bytes. */
#define F unexpected_exception
#define VECTOR_TABLE(name, handler)                                                 \
    __attribute__((aligned(512))) static void (*const name[EXCEPTIONS])(void) = {   \
        (void (*)(void))_estack, Reset_Handler,                                     \
        [2 ... 10] = F, [11] = handler, [12 ... 15] = F,                            \
        [16 ... EXCEPTIONS - 1U] = handler,                                         \
    }

/* What the core reads at reset: no line is enabled until a case selects its table. */
__attribute__((section(".isr_vector"), used))
void (*const boot_vectors[16])(void) = {
    (void (*)(void))_estack, Reset_Handler,
    F, F, F, F, F, F, F, F, F, F, F, F, F, F,
};

VECTOR_TABLE(line_state_vectors, line_state_handler);
VECTOR_TABLE(note_service_vectors, note_service_handler);
VECTOR_TABLE(nested_request_vectors, nested_request_handler);
VECTOR_TABLE(exception_cost_vectors, exception_cost_handler);
VECTOR_TABLE(timer_service_vectors, timer_service_handler);
VECTOR_TABLE(repeated_request_vectors, repeated_request_handler);
VECTOR_TABLE(self_observing_vectors, self_observing_handler);
#undef F

/* selected_case - 1 → the case and its table. */
static const struct {
    void (*run)(void);
    void (*const *vectors)(void);
} CASES[] = {
    {c2_01_pending_and_enable, line_state_vectors},
    {c2_02_priority_and_tie, note_service_vectors},
    {c2_03_nested_preemption, nested_request_vectors},
    {c2_04_masks, note_service_vectors},
    {c2_05_wfi_and_primask, note_service_vectors},
    {c2_06_tail_chaining, note_service_vectors},
    {c2_07_exception_cost, exception_cost_vectors},
    {c2_08_timer_period, timer_service_vectors},
    {c2_09_repeated_request, repeated_request_vectors},
    {c2_10_timer_tie, timer_service_vectors},
    {c2_11_coalescence, self_observing_vectors},
    {c2_12_timer_count_at_entry, self_observing_vectors},
    {c2_13_flag_clear_before_return, self_observing_vectors},
};

static void init_clock(void)
{
    LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_HSI);
    LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
    LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
    LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
    LL_FLASH_SetLatency(LL_FLASH_LATENCY_0);
    LL_FLASH_EnablePrefetch();
}

/* Everything the cases depend on is written explicitly, even at its reset value:
 * PRIGROUP = 0 (the 4 implemented bits are group bits), no mask, all lines disabled
 * and without a pending request. */
static void init_interrupts(void (*const *vectors)(void))
{
    SCB->VTOR = (uint32_t)vectors;
    NVIC_SetPriorityGrouping(0U);
    __set_BASEPRI(0U);
    __enable_fault_irq();
    for (uint32_t k = 0U; k < N_OF(NVIC->ICER); k++) {
        NVIC->ICER[k] = 0xFFFFFFFFU;
        NVIC->ICPR[k] = 0xFFFFFFFFU;
    }
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    barrier();
    __enable_irq();
}

int main(void)
{
    if (selected_case == 0U || selected_case > N_OF(CASES)) {
        unexpected_exception();
    }
    uint32_t index = selected_case - 1U;
    init_clock();
    init_interrupts(CASES[index].vectors);
    CASES[index].run();
    finish_case();
}
