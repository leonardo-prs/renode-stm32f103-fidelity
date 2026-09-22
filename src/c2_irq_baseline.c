/**
 * @file    src/c2_irq_baseline.c
 * @brief   C2 single-event reactivity baseline: TIM2 @1 kHz, minimal ISR.
 *
 * Stack: HSI 8 MHz, STM32 LL only, no HAL, no printf. Bare-metal C17 GNU
 * for STM32F103C8T6 (Cortex-M3). TIM2 timing (PSC=7, ARR=999) is set by
 * CubeMX MX_TIM2_Init(); nominal period = 1000 timer ticks = 8000 CPU
 * cycles @8 MHz.
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

#include "main.h"
#include "tim.h"
#include "stm32f1xx_ll_tim.h"
#include "stm32f1xx_ll_bus.h"

/* GDB-visible results: 1024 interleaved (CYCCNT, TIM2->CNT) pairs. */
volatile uint32_t c2_results[2048U];
volatile uint32_t c2_n    = 0U;
volatile uint8_t  c2_done = 0U;

/* Write index into pairs (0..1024); V2 main-loop sink (busy-loop load). */
static volatile uint32_t g_idx  = 0U;
static volatile uint32_t g_sink = 0U;

/* File-scope prototypes (required by -Wmissing-prototypes). */
void c2_tim2_hook(void);
void c2_irq_baseline_main(void);

/**
 * @brief Minimal TIM2 update ISR body, called from TIM2_IRQHandler
 *        (Core/Src/stm32f1xx_it.c USER CODE, first instruction of handler).
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
 * @brief C2 entry — called by Core/Src/main.c under SCENARIO_C2.
 *        Never returns.
 */
void c2_irq_baseline_main(void)
{
    /* ── Quarantine unused peripherals (MX_*_Init is unconditional) ── */
    NVIC_DisableIRQ(TIM3_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    LL_APB1_GRP1_DisableClock(LL_APB1_GRP1_PERIPH_TIM3);

    NVIC_DisableIRQ(USART1_IRQn);
    NVIC_ClearPendingIRQ(USART1_IRQn);
    LL_APB2_GRP1_DisableClock(LL_APB2_GRP1_PERIPH_USART1);

    /* SysTick off: C2 measures bare TIM2 reactivity, no 1 ms tick noise. */
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

    /* ── Arm TIM2 @1 kHz (IT enable is idempotent; do not rely on MX) ── */
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
        __WFI();
    }
#endif
}
