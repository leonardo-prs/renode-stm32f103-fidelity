/**
 * @file    src/c2_irq_baseline.c
 * @brief   C2 single-event reactivity baseline: TIM2 @1 kHz, minimal ISR.
 *
 * Stack: HSI 8 MHz, STM32 LL only, no HAL, no printf. Bare-metal C17 GNU
 * for STM32F103C8T6 (Cortex-M3). TIM2 timing (PSC=7, ARR=999) is set by
 * tim_1khz_init() (lib/periph.c); nominal period = 1000 timer ticks = 8000
 * CPU cycles @8 MHz.
 *
 * Peripherals ON: TIM2 only (+ DWT). NVIC: TIM2_IRQn only, priority 2.
 * Build variant C2_BUSY_LOOP -> build/c2busy/firmware.elf.
 *
 * Buffer layout: c2_results[2048] holds 1024 interleaved pairs —
 *   [2k]   = DWT CYCCNT sampled at ISR entry (first instruction),
 *   [2k+1] = TIM2->CNT sampled immediately after (second instruction).
 * c2_n = 2048 once full; c2_done = 1 signals completion (GDB: `p c2_done`,
 * then dump c2_results). c2_done = 0xFE = DWT NOCYCCNT error park.
 *
 * Latency inference (post-processed off-target): lat_est = (1000 - cnt) * 8
 * cycles (8 CPU cycles per PSC tick: 8 MHz / (7+1) = 1 MHz timer clock).
 * Theoretical IRQ-entry floor is 12 cycles (Yiu, Cortex-M3 TRM). Period
 * nominal = 8000 cycles; jitter = max-min over CYCCNT deltas. Ref H2
 * (deterministic single-event latency; V1 sleep vs V2 busy-loop load).
 */

#include "board.h"
#include "periph.h"                     /* tim_1khz_init() */
#include "trace.h"                      /* trace_init()/trace_emit(): ISR 0x10/0x11, WFI 0x12/0x13 */

/* Trace overhead (documentado): cada trace_emit = 1 load (base do ring) +
 * escrita no ring buffer em SRAM, ~10-20 ciclos. O marker 0x10 precede a
 * amostra CYCCNT na ISR por instrucoes — deslocamento constante, removido
 * offline na analise (pares CYCCNT/CNT preservados). */

/* GDB-visible results: 1024 interleaved (CYCCNT, TIM2->CNT) pairs. */
volatile uint32_t c2_results[2048U];
volatile uint32_t c2_n    = 0U;
volatile uint8_t  c2_done = 0U;

/* Write index into pairs (0..1024); V2 main-loop sink (busy-loop load). */
static volatile uint32_t g_idx  = 0U;
static volatile uint32_t g_sink = 0U;

/* File-scope prototypes (required by -Wmissing-prototypes).
 * noinline: handler and hook used to live in different TUs; keep the call. */
void c2_tim2_hook(void) __attribute__((noinline));
void TIM2_IRQHandler(void);

/**
 * @brief TIM2 update IRQ (overrides the weak alias in the startup file).
 *
 * Kept as handler -> hook (one call level) to preserve the exact code path
 * of the pre-migration build (CubeMX stm32f1xx_it.c called c2_tim2_hook()
 * from TIM2_IRQHandler), so data collected before/after remain comparable.
 */
void TIM2_IRQHandler(void)
{
    trace_emit(0x10U);                    /* ISR enter (primeira instrucao) */
    c2_tim2_hook();
    trace_emit(0x11U);                    /* ISR exit (ultima antes do return) */
}

/**
 * @brief Minimal TIM2 update ISR body, called from TIM2_IRQHandler
 *        (first instruction of handler).
 */
void c2_tim2_hook(void)
{
    uint32_t cyc = DWT->CYCCNT;
    uint32_t cnt = LL_TIM_GetCounter(TIM2);
    uint32_t idx = g_idx;

    c2_results[2U * idx]        = cyc;
    c2_results[2U * idx + 1U]   = cnt;
    LL_TIM_ClearFlag_UPDATE(TIM2);

    g_idx = idx + 1U;
    if (g_idx >= 1024U)
    {
        LL_TIM_DisableCounter(TIM2);
        NVIC_DisableIRQ(TIM2_IRQn);
        c2_n = 2048U;
        __DSB();
        c2_done = 1U;
    }
}

/**
 * @brief C2 entry (build/c2/firmware.elf, build/c2busy/firmware.elf).
 *        Never returns.
 */
int main(void)
{
    board_init();
    trace_init();                       /* ring de trace antes de qualquer emit */

    /* ── Only peripheral of this scenario: TIM2 @1 kHz, IRQ prio 2 ── */
    tim_1khz_init(TIM2);
    NVIC_SetPriority(TIM2_IRQn, NVIC_EncodePriority(NVIC_GetPriorityGrouping(), 2, 0));
    NVIC_EnableIRQ(TIM2_IRQn);

    /* SysTick off (defensive; reset state): no 1 ms tick noise. */
    SysTick->CTRL = 0U;

    /* ── DWT cycle counter on ── */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    if ((DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk) != 0U)
    {
        c2_done = 0xFEU;
        for (;;)
        {
            __WFI();
        }
    }
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    /* ── Fresh acquisition state ── */
    g_idx   = 0U;
    g_sink  = 0U;
    c2_n    = 0U;
    c2_done = 0U;

    /* ── Arm TIM2 @1 kHz (UIF already set by UG in LL_TIM_Init: clear first) ── */
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_EnableIT_UPDATE(TIM2);
    LL_TIM_EnableCounter(TIM2);

#ifdef C2_BUSY_LOOP
    /* V2: saturated ALU load; must not touch TIM2/DWT. */
    for (;;)
    {
        g_sink += g_sink + 1U;
    }
#else
    /* V1 (default): sleep between events. */
    for (;;)
    {
        trace_emit(0x12U);                /* WFI enter */
        __WFI();
        trace_emit(0x13U);                /* WFI exit (wakeup) */
    }
#endif
}
