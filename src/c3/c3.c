/*
 * src/c3/c3.c — C3, GPIO and EXTI: how an external event reaches the firmware. Cases in
 * order, each one relies on the ones before it. One case per boot (selected_case).
 *
 * Bench: L2 PA6 → PA0, L3 PA7 → PA1, L4 PA5 → PB0 (wires on the board, GPIO links in
 * Renode, renode/c3_links.repl). PA3 and PA4 have nothing attached. The destination pins
 * are always inputs.
 *
 *   Document oracle (Renode)
 *   1  c3_01_output_registers  ODR read back per write; per level change: IDR4 before,
 *                              after; per path: IDR0 before, after the write to the input PA6
 *   2  c3_02_input_pull        per level change: IDR4 before, after
 *   3  c3_03_driven_line       per link and level: IDR of the source, IDR of the destination
 *   4  c3_04_exti_routing      per point: entries after the rise, after the fall
 *   5  c3_05_exti_pending      per point: see c3_05_exti_pending; per event with the core
 *                              in WFI: entries at the wake-up, ticks to the first read
 *   Board oracle (the same binary in Renode and on the board)
 *   6  c3_06_input_capture     (a) per point: flags, capture difference, DWT difference;
 *                              (b) per point: TIM2_SR
 *   7  c3_07_event_response    per measure and event: value, capture flags, valid
 *
 * The point tables are repeated in scripts/c3.py, in the same order.
 * Clock: HSI 8 MHz, AHB/APB1/APB2 ÷ 1, flash 0 wait states with prefetch, so one
 * cycle = one tick of DWT_CYCCNT and of the timers (PSC = 0).
 * What the board measures is fixed in assembly: registers, encoding and offset in the
 * 64-bit flash line, on which the cost of an instruction depends.
 */
#include "case.h"
#include "stm32f1xx.h"
#include "stm32f1xx_ll_bus.h"
#include "stm32f1xx_ll_exti.h"
#include "stm32f1xx_ll_gpio.h"
#include "stm32f1xx_ll_rcc.h"
#include "stm32f1xx_ll_system.h"
#include "stm32f1xx_ll_tim.h"

extern uint32_t _estack[];

#define N_OF(a)         (sizeof(a) / sizeof((a)[0]))
#define BIT(pin)        (1UL << (pin))          /* the LL_GPIO_PIN_x of the F1 are not bit masks */
#define SETTLE_TICKS    800U                    /* 100 µs after every pin change */
#define DEFAULT_PRIORITY 8U
#define VECTORS         (16U + 43U)             /* system exceptions and IRQ 0..42 of the medium-density family (RM0008 Tab. 63) */

static volatile uint32_t exti0_entries;         /* main writes it only with the line disabled */

/* ─────────────────────────── common steps ─────────────────────────── */

/* ARM recommendation after writing to the NVIC: the effect holds in the following instructions. */
static inline void barrier(void)
{
    __DSB();
    __ISB();
}

static void wait_ticks(uint32_t ticks)
{
    uint32_t start = DWT->CYCCNT;
    while (DWT->CYCCNT - start < ticks) {
    }
}

static void wait_settle(void)
{
    wait_ticks(SETTLE_TICKS);
}

/* Output data bit of one pin of port A through the whole ODR, keeping the others. */
static void write_odr_bit(uint32_t pin, uint32_t level)
{
    uint32_t others = LL_GPIO_ReadOutputPort(GPIOA) & ~BIT(pin);
    LL_GPIO_WriteOutputPort(GPIOA, others | (level << pin));
}

/* Level first: enabling the output never makes a rise on the line. Written again as an
 * output, so the pin is low whatever it held before. */
static void set_output_low(uint32_t ll_pin)
{
    LL_GPIO_ResetOutputPin(GPIOA, ll_pin);
    LL_GPIO_SetPinMode(GPIOA, ll_pin, LL_GPIO_MODE_OUTPUT);
    LL_GPIO_SetPinSpeed(GPIOA, ll_pin, LL_GPIO_SPEED_FREQ_HIGH);
    LL_GPIO_SetPinOutputType(GPIOA, ll_pin, LL_GPIO_OUTPUT_PUSHPULL);
    LL_GPIO_ResetOutputPin(GPIOA, ll_pin);
}

/* Clears the pending bit of line 0 (write 1, RM0008 §10.3.6) and reads it back, so the
 * clear completes before what follows. */
static void clear_exti0_pending(void)
{
    LL_EXTI_ClearFlag_0_31(LL_EXTI_LINE_0);
    (void)LL_EXTI_ReadFlag_0_31(LL_EXTI_LINE_0);
}

/* EXTI line 0 masked, from `port`, on the selected edges, with nothing pending. */
static void prepare_exti0(uint32_t port, uint32_t rising, uint32_t falling)
{
    NVIC_DisableIRQ(EXTI0_IRQn);
    LL_EXTI_DisableIT_0_31(LL_EXTI_LINE_0);
    LL_GPIO_AF_SetEXTISource(port, LL_GPIO_AF_EXTI_LINE0);
    if (rising != 0U) {
        LL_EXTI_EnableRisingTrig_0_31(LL_EXTI_LINE_0);
    } else {
        LL_EXTI_DisableRisingTrig_0_31(LL_EXTI_LINE_0);
    }
    if (falling != 0U) {
        LL_EXTI_EnableFallingTrig_0_31(LL_EXTI_LINE_0);
    } else {
        LL_EXTI_DisableFallingTrig_0_31(LL_EXTI_LINE_0);
    }
    clear_exti0_pending();
    NVIC_ClearPendingIRQ(EXTI0_IRQn);
    NVIC_SetPriority(EXTI0_IRQn, DEFAULT_PRIORITY);
    exti0_entries = 0U;
    barrier();
}

static void enable_exti0_in_nvic(void)
{
    NVIC_EnableIRQ(EXTI0_IRQn);
    barrier();
}

/* ─────────────────── C3-01: c3_01_output_registers ─────────────────── */

/* The two write paths of the output data (RM0008 §9.1.2): the whole ODR, or BSRR/BRR. */
#define BY_ODR      0U
#define BY_BSRR_BRR 1U

static void write_pa4(uint32_t path, uint32_t level)
{
    if (path == BY_ODR) {
        write_odr_bit(4U, level);
    } else if (level != 0U) {
        LL_GPIO_SetOutputPin(GPIOA, LL_GPIO_PIN_4);
    } else {
        LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_4);
    }
    wait_settle();
}

/* Each direction of the change by each path. The previous level always comes from BSRR/BRR,
 * so a path without effect shows: the level stays, and the pair is not the expected one. */
static const uint8_t LEVEL_PREVIOUS[4] = {0U, 1U, 0U, 1U};
static const uint8_t LEVEL_PATHS[4] = {BY_ODR, BY_ODR, BY_BSRR_BRR, BY_BSRR_BRR};

static void record_level_changes(void)
{
    for (uint32_t k = 0U; k < N_OF(LEVEL_PREVIOUS); k++) {
        write_pa4(BY_BSRR_BRR, LEVEL_PREVIOUS[k]);
        record_value(LL_GPIO_IsInputPinSet(GPIOA, LL_GPIO_PIN_4));
        write_pa4(LEVEL_PATHS[k], LEVEL_PREVIOUS[k] ^ 1U);
        record_value(LL_GPIO_IsInputPinSet(GPIOA, LL_GPIO_PIN_4));
    }
}

/* PA6 is an input, so its output buffer is off (RM0008 §9.1.7): writing its output data
 * does not reach PA0, held at 0 by its pull-down. PA6 was driven to 0 first, so the line
 * starts at 0 on both paths. */
static void record_input_isolation(uint32_t path)
{
    set_output_low(LL_GPIO_PIN_6);
    wait_settle();
    write_odr_bit(0U, 0U);
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_0, LL_GPIO_MODE_INPUT);
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_6, LL_GPIO_MODE_FLOATING);
    wait_settle();
    record_value(LL_GPIO_IsInputPinSet(GPIOA, LL_GPIO_PIN_0));
    if (path == BY_ODR) {
        write_odr_bit(6U, 1U);
    } else {
        LL_GPIO_SetOutputPin(GPIOA, LL_GPIO_PIN_6);
    }
    wait_settle();
    record_value(LL_GPIO_IsInputPinSet(GPIOA, LL_GPIO_PIN_0));
}

static void c3_01_output_registers(void)
{
    set_output_low(LL_GPIO_PIN_3);
    set_output_low(LL_GPIO_PIN_4);
    uint32_t both = BIT(3U) | BIT(4U);

    LL_GPIO_WriteOutputPort(GPIOA, both);               /* ODR: the value written is read back */
    record_value(LL_GPIO_ReadOutputPort(GPIOA) & both);
    LL_GPIO_WriteOutputPort(GPIOA, BIT(3U));            /* one bit down: not a fixed answer */
    record_value(LL_GPIO_ReadOutputPort(GPIOA) & both);
    LL_GPIO_SetOutputPin(GPIOA, LL_GPIO_PIN_4);         /* BSRR: PA3 stays */
    record_value(LL_GPIO_ReadOutputPort(GPIOA) & both);
    LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_3);       /* BRR: PA4 stays */
    record_value(LL_GPIO_ReadOutputPort(GPIOA) & both);
    LL_GPIO_WriteOutputPort(GPIOA, 0U);
    GPIOA->BSRR = BIT(4U) | BIT(4U + 16U);              /* set and reset of one bit: BS has priority (§9.2.5) */
    record_value(LL_GPIO_ReadOutputPort(GPIOA) & both);

    record_level_changes();                             /* no wire: the pin is sampled into IDR every APB2 cycle (§9.1.8) */
    record_input_isolation(BY_ODR);
    record_input_isolation(BY_BSRR_BRR);
}

/* ────────────────────── C3-02: c3_02_input_pull ────────────────────── */

/* The same level changes on an input: the output data bit selects the pull (RM0008 Tab. 20). */
static void c3_02_input_pull(void)
{
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_4, LL_GPIO_MODE_INPUT);
    record_level_changes();
}

/* ────────────────────── C3-03: c3_03_driven_line ────────────────────── */

/* Every link of the bench: the source in push-pull at 0, 1, 0 (RM0008 §9.1.7, §9.1.8). */
struct link {
    uint32_t source;
    GPIO_TypeDef *destination_port;
    uint32_t destination;
};

static const struct link LINKS[3] = {
    {LL_GPIO_PIN_6, GPIOA, LL_GPIO_PIN_0},      /* L2 */
    {LL_GPIO_PIN_7, GPIOA, LL_GPIO_PIN_1},      /* L3 */
    {LL_GPIO_PIN_5, GPIOB, LL_GPIO_PIN_0},      /* L4 */
};

static void record_link_levels(const struct link *link)
{
    wait_settle();
    record_value(LL_GPIO_IsInputPinSet(GPIOA, link->source));
    record_value(LL_GPIO_IsInputPinSet(link->destination_port, link->destination));
}

static void c3_03_driven_line(void)
{
    for (uint32_t k = 0U; k < N_OF(LINKS); k++) {
        const struct link *link = &LINKS[k];
        set_output_low(link->source);
        record_link_levels(link);
        LL_GPIO_SetOutputPin(GPIOA, link->source);
        record_link_levels(link);
        LL_GPIO_ResetOutputPin(GPIOA, link->source);
        record_link_levels(link);
    }
}

/* ─────────────────────── EXTI0 handlers of C3-04, C3-05 ─────────────────────── */

static void counting_handler(void)
{
    clear_exti0_pending();
    exti0_entries = exti0_entries + 1U;
}

/* Another rise on PA0, at a settled level, inside the first entry. */
static void make_rise_on_pa0(void)
{
    LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_6);
    wait_settle();
    LL_GPIO_SetOutputPin(GPIOA, LL_GPIO_PIN_6);
    wait_settle();
}

/* The new edge finds the pending bit already set, and the clear removes both: one entry. */
static void rise_before_clear_handler(void)
{
    exti0_entries = exti0_entries + 1U;
    if (exti0_entries == 1U) {
        make_rise_on_pa0();
    }
    clear_exti0_pending();
    wait_settle();
}

/* The new edge sets the bit again while the line is active: the NVIC keeps it pending and
 * enters once more at the return (Yiu §7.6). The wait after the clear keeps the edge away
 * from the moment the clear reaches the peripheral. */
static void rise_after_clear_handler(void)
{
    exti0_entries = exti0_entries + 1U;
    clear_exti0_pending();
    wait_settle();
    if (exti0_entries == 1U) {
        make_rise_on_pa0();
    }
}

/* ────────────────────── C3-04: c3_04_exti_routing ────────────────────── */

/* EXTICR1 selects the port of line 0; the trigger registers the edges (RM0008 §9.4.3,
 * §10.2.4, §10.2.5). Each edge pin is tried with its port and with the other one. */
struct routing_point {
    uint32_t port;
    uint32_t rising;
    uint32_t falling;
    uint32_t edge_pin;
};

static const struct routing_point ROUTING_POINTS[6] = {
    {LL_GPIO_AF_EXTI_PORTA, 1U, 0U, LL_GPIO_PIN_6},     /* rising only */
    {LL_GPIO_AF_EXTI_PORTA, 0U, 1U, LL_GPIO_PIN_6},     /* falling only */
    {LL_GPIO_AF_EXTI_PORTA, 1U, 1U, LL_GPIO_PIN_6},     /* both */
    {LL_GPIO_AF_EXTI_PORTA, 1U, 1U, LL_GPIO_PIN_5},     /* port A selected, edge on PB0: no entry */
    {LL_GPIO_AF_EXTI_PORTB, 1U, 1U, LL_GPIO_PIN_5},     /* port B selected, edge on PB0 */
    {LL_GPIO_AF_EXTI_PORTB, 1U, 1U, LL_GPIO_PIN_6},     /* port B selected, edge on PA0: no entry */
};

static void c3_04_exti_routing(void)
{
    set_output_low(LL_GPIO_PIN_6);
    set_output_low(LL_GPIO_PIN_5);
    wait_settle();
    __enable_irq();
    for (uint32_t k = 0U; k < N_OF(ROUTING_POINTS); k++) {
        const struct routing_point *point = &ROUTING_POINTS[k];
        prepare_exti0(point->port, point->rising, point->falling);
        LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
        enable_exti0_in_nvic();
        LL_GPIO_SetOutputPin(GPIOA, point->edge_pin);
        wait_settle();
        record_value(exti0_entries);
        uint32_t after_rise = exti0_entries;
        LL_GPIO_ResetOutputPin(GPIOA, point->edge_pin);
        wait_settle();
        record_value(exti0_entries - after_rise);
    }
}

/* ────────────────────── C3-05: c3_05_exti_pending ────────────────────── */

/* A rise on PA6 reaches PA0; the line has the rising trigger and starts with nothing pending.
 * RM0008 §10.2.2 Fig. 20, §10.2.4, §10.3.6; Yiu §7.6. */
static void prepare_pending_point(void (*const *vectors)(void))
{
    LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_6);
    wait_settle();
    SCB->VTOR = (uint32_t)vectors;
    prepare_exti0(LL_GPIO_AF_EXTI_PORTA, 1U, 0U);
}

static void rise_and_settle(void)
{
    LL_GPIO_SetOutputPin(GPIOA, LL_GPIO_PIN_6);
    wait_settle();
}

static void fall_and_settle(void)
{
    LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_6);
    wait_settle();
}

static void enable_in_nvic_and_settle(void)
{
    enable_exti0_in_nvic();
    wait_settle();
}

static void record_wake_from_wfi(void);

static void (*const counting_vectors[VECTORS])(void);
static void (*const rise_before_clear_vectors[VECTORS])(void);
static void (*const rise_after_clear_vectors[VECTORS])(void);

static void c3_05_exti_pending(void)
{
    set_output_low(LL_GPIO_PIN_6);
    __enable_irq();

    /* Masked line: the pending register is after the AND with IMR (RM0008 §10.2.2 Fig. 20; the
     * text of §10.3.6 alone does not say). Words: PR; entries once unmasked. */
    prepare_pending_point(counting_vectors);
    enable_exti0_in_nvic();
    rise_and_settle();
    record_value(LL_EXTI_ReadFlag_0_31(LL_EXTI_LINE_0));
    LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
    wait_settle();
    record_value(exti0_entries);

    /* NVIC disabled: the event stays in PR, and is served once enabled. Words: PR; entries before; after. */
    prepare_pending_point(counting_vectors);
    LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
    rise_and_settle();
    record_value(LL_EXTI_ReadFlag_0_31(LL_EXTI_LINE_0));
    record_value(exti0_entries);
    enable_in_nvic_and_settle();
    record_value(exti0_entries);

    /* A pulse already over: the event stays after the signal is gone. Words: PR; IDR0; entries once enabled. */
    prepare_pending_point(counting_vectors);
    LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
    rise_and_settle();
    fall_and_settle();
    record_value(LL_EXTI_ReadFlag_0_31(LL_EXTI_LINE_0));
    record_value(LL_GPIO_IsInputPinSet(GPIOA, LL_GPIO_PIN_0));
    enable_in_nvic_and_settle();
    record_value(exti0_entries);

    /* Two rises with the NVIC disabled: one pending bit, one entry. Word: entries once enabled. */
    prepare_pending_point(counting_vectors);
    LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
    rise_and_settle();
    fall_and_settle();
    rise_and_settle();
    enable_in_nvic_and_settle();
    record_value(exti0_entries);

    /* A rise in the handler before the clear is lost; after the clear it enters again. Word: entries. */
    prepare_pending_point(rise_before_clear_vectors);
    LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
    enable_exti0_in_nvic();
    rise_and_settle();
    wait_ticks(4U * SETTLE_TICKS);
    record_value(exti0_entries);

    prepare_pending_point(rise_after_clear_vectors);
    LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
    enable_exti0_in_nvic();
    rise_and_settle();
    wait_ticks(4U * SETTLE_TICKS);
    record_value(exti0_entries);

    /* An edge wakes the core from WFI, and with PRIMASK = 0 the handler runs before the code
     * after it (Yiu §9.2.4, Tab. 9.4). */
    fall_and_settle();
    record_wake_from_wfi();
    __disable_irq();
}

/* ────────────────────── C3-06: c3_06_input_capture ────────────────────── */

#define CAPTURE_FLAGS (TIM_SR_CC1IF | TIM_SR_CC2IF)

/* TIM2 stopped, at f_CK_INT (PSC = 0). The widest point stays far from the end of the
 * count, so no difference crosses a wrap. */
static void prepare_capture_timer(void)
{
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_CC_DisableChannel(TIM2, LL_TIM_CHANNEL_CH1 | LL_TIM_CHANNEL_CH2);    /* the input is configured with CCxE = 0 */
    LL_TIM_SetPrescaler(TIM2, 0U);
    LL_TIM_SetAutoReload(TIM2, 0xFFFFU);
    LL_TIM_GenerateEvent_UPDATE(TIM2);          /* loads PSC and clears the counter */
}

static void start_capture_timer(void)
{
    LL_TIM_ClearFlag_CC1(TIM2);
    LL_TIM_ClearFlag_CC2(TIM2);
    LL_TIM_CC_EnableChannel(TIM2, LL_TIM_CHANNEL_CH1 | LL_TIM_CHANNEL_CH2);
    LL_TIM_EnableCounter(TIM2);
}

/* CH1 on the rise of TI1 (PA0); CH2 on `ch2_config`. No filter, no prescaler. */
static void configure_capture_channels(uint32_t ch2_config)
{
    LL_TIM_IC_Config(TIM2, LL_TIM_CHANNEL_CH1, LL_TIM_ACTIVEINPUT_DIRECTTI | LL_TIM_ICPSC_DIV1 |
                                                   LL_TIM_IC_FILTER_FDIV1 | LL_TIM_IC_POLARITY_RISING);
    LL_TIM_IC_Config(TIM2, LL_TIM_CHANNEL_CH2, ch2_config | LL_TIM_ICPSC_DIV1 | LL_TIM_IC_FILTER_FDIV1);
}

/* DWT_CYCCNT, then the write to GPIOA_BSRR: the same instructions at the same address for
 * both edges, so what lies between the read and the capture is the same and cancels. */
__attribute__((naked, noipa, aligned(8))) static uint32_t read_time_then_write(uint32_t bsrr_word __attribute__((unused)))
{
    __asm volatile("mov r3, r0\n\t"
                   "ldr r1, =0xE0001004\n\t"        /* DWT_CYCCNT */
                   "ldr r2, =0x40010810\n\t"        /* GPIOA_BSRR */
                   "ldr r0, [r1]\n\t"
                   "str r3, [r2]\n\t"
                   "bx lr\n\t"
                   ".ltorg");
}

/* First and last edge of a point: capture and DWT differences of the same two edges. */
static void record_capture_point(uint32_t first_word, uint32_t second_word, uint32_t ticks)
{
    uint32_t first = read_time_then_write(first_word);
    wait_ticks(ticks);
    uint32_t second = read_time_then_write(second_word);
    wait_settle();
    record_value(LL_TIM_ReadReg(TIM2, SR) & CAPTURE_FLAGS);
    uint32_t ccr1 = LL_TIM_IC_GetCaptureCH1(TIM2);
    uint32_t ccr2 = LL_TIM_IC_GetCaptureCH2(TIM2);
    record_value((ccr2 - ccr1) & 0xFFFFU);
    record_value(second - first);
}

/* Two distances, near and far, to tell an offset from an error of scale. */
static const uint16_t CAPTURE_TICKS[2] = {100U, 10000U};

/* Both edges in TI1 through L2: CH2 on the fall (CC2S = 10, RM0008 §15.3.6). */
static void record_captures_of_one_input(void)
{
    for (uint32_t k = 0U; k < N_OF(CAPTURE_TICKS); k++) {
        prepare_capture_timer();
        configure_capture_channels(LL_TIM_ACTIVEINPUT_INDIRECTTI | LL_TIM_IC_POLARITY_FALLING);
        LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_6);
        wait_settle();
        start_capture_timer();
        record_capture_point(BIT(6U), BIT(6U + 16U), CAPTURE_TICKS[k]);
    }
}

/* CH1 by L2, CH2 by L3 (TI2, CC2S = 01): the two pins C3-07 measures between. */
static void record_captures_of_two_inputs(void)
{
    for (uint32_t k = 0U; k < N_OF(CAPTURE_TICKS); k++) {
        prepare_capture_timer();
        configure_capture_channels(LL_TIM_ACTIVEINPUT_DIRECTTI | LL_TIM_IC_POLARITY_RISING);
        LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_6);
        LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_7);
        wait_settle();
        start_capture_timer();
        record_capture_point(BIT(6U), BIT(7U), CAPTURE_TICKS[k]);
    }
}

/* The widths of the filter points are the object, fixed in assembly: two consecutive
 * stores, and 24 NOPs between the stores (RM0008 §15.3.5, §15.4.7). */
static void pulse_short(void)
{
    __asm volatile(".balign 8\n\t"
                   "str %0, [%2]\n\t"
                   "str %1, [%2]"
                   :
                   : "r"(BIT(6U)), "r"(BIT(6U + 16U)), "r"(&GPIOA->BSRR)
                   : "memory");
}

static void pulse_long(void)
{
    __asm volatile(".balign 8\n\t"
                   "str %0, [%2]\n\t"
                   ".rept 24\n\tnop.n\n\t.endr\n\t"
                   "str %1, [%2]"
                   :
                   : "r"(BIT(6U)), "r"(BIT(6U + 16U)), "r"(&GPIOA->BSRR)
                   : "memory");
}

/* No filter: the control. f_CK_INT, N = 8: wider than the short pulse, narrower than the long one. */
static const uint32_t FILTER_SETTINGS[2] = {LL_TIM_IC_FILTER_FDIV1, LL_TIM_IC_FILTER_FDIV1_N8};
static void (*const FILTER_PULSES[2])(void) = {pulse_short, pulse_long};

static void record_filter_points(void)
{
    prepare_capture_timer();
    for (uint32_t f = 0U; f < N_OF(FILTER_SETTINGS); f++) {
        LL_TIM_DisableCounter(TIM2);
        LL_TIM_CC_DisableChannel(TIM2, LL_TIM_CHANNEL_CH1 | LL_TIM_CHANNEL_CH2);
        LL_TIM_IC_Config(TIM2, LL_TIM_CHANNEL_CH1, LL_TIM_ACTIVEINPUT_DIRECTTI | LL_TIM_ICPSC_DIV1 |
                                                       FILTER_SETTINGS[f] | LL_TIM_IC_POLARITY_RISING);
        LL_TIM_CC_EnableChannel(TIM2, LL_TIM_CHANNEL_CH1);
        LL_TIM_EnableCounter(TIM2);
        for (uint32_t p = 0U; p < N_OF(FILTER_PULSES); p++) {
            LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_6);
            wait_settle();
            LL_TIM_ClearFlag_CC1(TIM2);
            FILTER_PULSES[p]();
            wait_settle();
            record_value(LL_TIM_ReadReg(TIM2, SR) & TIM_SR_CC1IF);
        }
    }
}

static void c3_06_input_capture(void)
{
    set_output_low(LL_GPIO_PIN_6);
    set_output_low(LL_GPIO_PIN_7);
    record_captures_of_one_input();
    record_captures_of_two_inputs();
    record_filter_points();
    LL_TIM_DisableCounter(TIM2);
}

/* ────────────────────── C3-07: c3_07_event_response ────────────────────── */

/* The rise TIM3 makes on PA6 by hardware (PWM mode 2: high from CNT = CCR1, RM0008 §15.3.9):
 * no instruction produces it. It reaches PA0 by L2, where TIM2_CH1 captures it and EXTI0
 * sees it. Three measures: from the compare to the first read in the handler, by the compare
 * interrupt (IRQ 29) and by the pin (IRQ 6), whose difference is what the path through the pin
 * adds, the entry cancelled; and from pin PA0 to pin PA1, between two captures, with the write
 * to PA7 first in the handler. */
#define RESPONSE_AUTO_RELOAD 999U
#define RESPONSE_EDGE        500U
#define EVENTS_PER_POINT     8U
#define SLED_LEAD_TICKS      40U    /* main enters the sled this close to the edge */
#define CAPTURE_WAIT_TICKS   64U    /* the capture of PA1 is done */

enum response_measure { BY_COMPARE_IRQ, BY_PIN_IRQ, PIN_TO_PIN };

/* Written only by the handlers while the line is enabled. */
static volatile uint32_t response_total;
static volatile uint32_t response_count;        /* TIM3_CNT at the first read */
static volatile uint32_t response_time;         /* DWT_CYCCNT right after it */

__attribute__((used, noipa)) static void note_response_by_pin(uint32_t count, uint32_t time)
{
    response_count = count;
    response_time = time;
    response_total = response_total + 1U;
    clear_exti0_pending();
}

__attribute__((used, noipa)) static void note_response_by_compare(uint32_t count, uint32_t time)
{
    response_count = count;
    response_time = time;
    response_total = response_total + 1U;
    LL_TIM_ClearFlag_CC1(TIM3);
    (void)LL_TIM_ReadReg(TIM3, SR);             /* the clear completes before the return */
}

/* The same instructions up to the first read in both handlers: the difference between the
 * measures is the path (its IRQ line and the place of its vector), not the code. TIM3_CNT
 * first, DWT_CYCCNT after it. */
#define FIRST_READ_HANDLER(name, note)                                  \
    __attribute__((naked, aligned(8))) static void name(void)           \
    {                                                                   \
        __asm volatile("ldr r1, =0x40000400\n\t"    /* TIM3 */          \
                       "ldr r0, [r1, #0x24]\n\t"    /* TIM3_CNT */      \
                       "ldr r2, =0xE0001004\n\t"    /* DWT_CYCCNT */    \
                       "ldr r1, [r2]\n\t"                               \
                       "push {r3, lr}\n\t"                              \
                       "bl " #note "\n\t"                               \
                       "pop {r3, lr}\n\t"                               \
                       "bx lr\n\t"                                      \
                       ".ltorg");                                       \
    }

FIRST_READ_HANDLER(first_read_by_compare_handler, note_response_by_compare)
FIRST_READ_HANDLER(first_read_by_pin_handler, note_response_by_pin)

/* The write to PA7 is the first thing in the handler: no read of a timer before the pin. */
__attribute__((naked, aligned(8))) static void pin_first_handler(void)
{
    __asm volatile("ldr r1, =0x40010810\n\t"        /* GPIOA_BSRR */
                   "movs r0, #0x80\n\t"             /* PA7 */
                   "str r0, [r1]\n\t"
                   "ldr r2, =0xE0001004\n\t"        /* DWT_CYCCNT */
                   "ldr r1, [r2]\n\t"
                   "push {r3, lr}\n\t"
                   "bl note_response_by_pin\n\t"
                   "pop {r3, lr}\n\t"
                   "bx lr\n\t"
                   ".ltorg");
}

/* DWT reads around 64 NOPs, so that the event interrupts a single-cycle instruction. */
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

/* The timers restart from zero at each point, and 8 events stay far from the end of TIM2. */
static void start_response_timers(void)
{
    LL_TIM_GenerateEvent_UPDATE(TIM3);
    LL_TIM_GenerateEvent_UPDATE(TIM2);
    LL_TIM_ClearFlag_CC1(TIM2);
    LL_TIM_ClearFlag_CC2(TIM2);
    LL_TIM_EnableCounter(TIM2);
    LL_TIM_EnableCounter(TIM3);
}

/* Stopped in the low phase of PA6, so the first rise of the next point is an edge. */
static void stop_response_timers(void)
{
    while (LL_TIM_GetCounter(TIM3) >= RESPONSE_EDGE) {
    }
    LL_TIM_DisableCounter(TIM3);
    LL_TIM_DisableCounter(TIM2);
}

static void prepare_response_timers(void)
{
    set_output_low(LL_GPIO_PIN_7);
    LL_TIM_SetPrescaler(TIM2, 0U);
    LL_TIM_SetAutoReload(TIM2, 0xFFFFU);
    configure_capture_channels(LL_TIM_ACTIVEINPUT_DIRECTTI | LL_TIM_IC_POLARITY_RISING);
    LL_TIM_CC_EnableChannel(TIM2, LL_TIM_CHANNEL_CH1 | LL_TIM_CHANNEL_CH2);

    LL_TIM_SetPrescaler(TIM3, 0U);
    LL_TIM_SetAutoReload(TIM3, RESPONSE_AUTO_RELOAD);
    LL_TIM_OC_EnablePreload(TIM3, LL_TIM_CHANNEL_CH1);      /* the user must enable it in PWM mode (RM0008 §15.3.9) */
    LL_TIM_OC_SetCompareCH1(TIM3, RESPONSE_EDGE);
    LL_TIM_GenerateEvent_UPDATE(TIM3);
    /* CCR1 = 500 and CNT = 0 before the mode: PWM mode 2 starts with OC1REF low (§15.4.7). */
    LL_TIM_OC_SetMode(TIM3, LL_TIM_CHANNEL_CH1, LL_TIM_OCMODE_PWM2);
    LL_TIM_CC_EnableChannel(TIM3, LL_TIM_CHANNEL_CH1);

    /* Low output first, so that handing PA6 to TIM3 (TIM3_CH1, no remap) makes no edge. */
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_6, LL_GPIO_MODE_ALTERNATE);
    LL_GPIO_SetPinSpeed(GPIOA, LL_GPIO_PIN_6, LL_GPIO_SPEED_FREQ_HIGH);
    LL_GPIO_SetPinOutputType(GPIOA, LL_GPIO_PIN_6, LL_GPIO_OUTPUT_PUSHPULL);
    wait_settle();
}

static void (*const by_compare_vectors[VECTORS])(void);
static void (*const by_pin_vectors[VECTORS])(void);
static void (*const pin_first_vectors[VECTORS])(void);

/* Only the source of this measure reaches the NVIC. */
static void select_response_source(enum response_measure measure)
{
    prepare_exti0(LL_GPIO_AF_EXTI_PORTA, 1U, 0U);
    LL_TIM_DisableIT_CC1(TIM3);
    NVIC_DisableIRQ(TIM3_IRQn);
    LL_TIM_ClearFlag_CC1(TIM3);
    (void)LL_TIM_ReadReg(TIM3, SR);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    NVIC_SetPriority(TIM3_IRQn, DEFAULT_PRIORITY);
    response_total = 0U;
    if (measure == BY_COMPARE_IRQ) {
        SCB->VTOR = (uint32_t)by_compare_vectors;
        LL_TIM_EnableIT_CC1(TIM3);
        NVIC_EnableIRQ(TIM3_IRQn);
    } else {
        SCB->VTOR = (uint32_t)(measure == BY_PIN_IRQ ? by_pin_vectors : pin_first_vectors);
        LL_EXTI_EnableIT_0_31(LL_EXTI_LINE_0);
        NVIC_EnableIRQ(EXTI0_IRQn);
    }
    barrier();
}

/* Valid: the event fell inside the sled. */
static uint32_t wait_for_one_event(uint32_t total_before)
{
    uint32_t times[2];
    while (LL_TIM_GetCounter(TIM3) >= RESPONSE_EDGE - SLED_LEAD_TICKS) {
    }
    while (LL_TIM_GetCounter(TIM3) < RESPONSE_EDGE - SLED_LEAD_TICKS) {
    }
    read_around_nop_sled(times);
    while (response_total == total_before) {
    }
    return response_time - times[0] < times[1] - times[0] ? 1U : 0U;
}

/* C3-05: the same edge and the same handler as the measure by the pin, with the core in WFI. */
static void record_wake_from_wfi(void)
{
    prepare_response_timers();
    select_response_source(BY_PIN_IRQ);
    start_response_timers();
    for (uint32_t k = 0U; k < EVENTS_PER_POINT; k++) {
        uint32_t total_before = response_total;
        __WFI();
        record_value(response_total - total_before);
        while (response_total == total_before) {
        }
        record_value(response_count - RESPONSE_EDGE);
    }
    NVIC_DisableIRQ(EXTI0_IRQn);
    barrier();
    stop_response_timers();
}

static void record_response_point(enum response_measure measure)
{
    select_response_source(measure);
    start_response_timers();
    for (uint32_t k = 0U; k < EVENTS_PER_POINT; k++) {
        uint32_t valid = wait_for_one_event(response_total);
        wait_ticks(CAPTURE_WAIT_TICKS);
        uint32_t flags = LL_TIM_ReadReg(TIM2, SR) & CAPTURE_FLAGS;
        uint32_t ccr1 = LL_TIM_IC_GetCaptureCH1(TIM2);
        uint32_t ccr2 = LL_TIM_IC_GetCaptureCH2(TIM2);
        LL_GPIO_ResetOutputPin(GPIOA, LL_GPIO_PIN_7);
        LL_TIM_ClearFlag_CC1(TIM2);
        LL_TIM_ClearFlag_CC2(TIM2);
        record_value(measure == PIN_TO_PIN ? (ccr2 - ccr1) & 0xFFFFU : response_count - RESPONSE_EDGE);
        record_value(flags);
        record_value(valid);
    }
    NVIC_DisableIRQ(EXTI0_IRQn);
    NVIC_DisableIRQ(TIM3_IRQn);
    barrier();
    stop_response_timers();
}

static void c3_07_event_response(void)
{
    static const enum response_measure MEASURES[3] = {BY_COMPARE_IRQ, BY_PIN_IRQ, PIN_TO_PIN};
    prepare_response_timers();
    __enable_irq();
    for (uint32_t m = 0U; m < N_OF(MEASURES); m++) {
        record_response_point(MEASURES[m]);
    }
    __disable_irq();
}

/* ───────────────────────────── boot ───────────────────────────── */

/* A vector table per family of handlers, on EXTI0 (IRQ 6) and TIM3 (IRQ 29). It goes in VTOR,
 * which holds bits 29:9 of its address (PM0056 §4.4.4), so it is aligned to 512 bytes. */
#define F           unexpected_exception
#define VECTOR_TABLE(name, exti0, tim3)                                     \
    __attribute__((aligned(512))) static void (*const name[VECTORS])(void) = {  \
        (void (*)(void))_estack, Reset_Handler,                             \
        [2 ... 21] = F, [22] = exti0, [23 ... 44] = F, [45] = tim3,         \
        [46 ... VECTORS - 1U] = F,                                          \
    }

/* What the core reads at reset: no line is enabled until a case selects its table. */
__attribute__((section(".isr_vector"), used))
void (*const boot_vectors[16])(void) = {
    (void (*)(void))_estack, Reset_Handler,
    F, F, F, F, F, F, F, F, F, F, F, F, F, F,
};

VECTOR_TABLE(counting_vectors, counting_handler, F);
VECTOR_TABLE(rise_before_clear_vectors, rise_before_clear_handler, F);
VECTOR_TABLE(rise_after_clear_vectors, rise_after_clear_handler, F);
VECTOR_TABLE(by_compare_vectors, F, first_read_by_compare_handler);
VECTOR_TABLE(by_pin_vectors, first_read_by_pin_handler, F);
VECTOR_TABLE(pin_first_vectors, pin_first_handler, F);
#undef F

/* selected_case - 1 → the case. */
static void (*const CASES[])(void) = {
    c3_01_output_registers, c3_02_input_pull, c3_03_driven_line, c3_04_exti_routing,
    c3_05_exti_pending, c3_06_input_capture, c3_07_event_response,
};

static void init_clock_and_peripherals(void)
{
    LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_HSI);      /* HSI 8 MHz, written explicitly */
    LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
    LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
    LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
    LL_FLASH_SetLatency(LL_FLASH_LATENCY_0);
    LL_FLASH_EnablePrefetch();
    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_GPIOA | LL_APB2_GRP1_PERIPH_GPIOB | LL_APB2_GRP1_PERIPH_AFIO);
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2 | LL_APB1_GRP1_PERIPH_TIM3);
    /* No remapping (TIM2_CH1/CH2 on PA0/PA1, TIM3_CH1 on PA6), SWJ kept. Not the LL remap
     * calls: they write SWJ_CFG = 111. */
    AFIO->MAPR = 0U;
}

int main(void)
{
    if (selected_case == 0U || selected_case > N_OF(CASES)) {
        unexpected_exception();
    }
    __disable_irq();
    SCB->VTOR = (uint32_t)counting_vectors;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    init_clock_and_peripherals();
    CASES[selected_case - 1U]();
    finish_case();
}
