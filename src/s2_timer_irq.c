/**
 * @file    src/s2_timer_irq.c
 * @brief   S2 — timer→IRQ (cenário 2 da ABI fidelity v1).
 *
 * Mede serviço de IRQ periódica do TIM2 (1 kHz) sob diferentes condições de
 * carga/máscara. Condições (códigos exatos do contrato RESULT_CONTRACT[2] em
 * scripts/fidelity_analyze.py):
 *   1 busy_leisurely       — fundo busy (volatile), serviço normal;
 *   2 wfi_leisurely        — MAIN em __WFI() entre serviços;
 *   3 busy_masked_release  — fundo busy; IRQ mascarada (NVIC) ≥5 períodos e
 *                            depois libertada (coalescência de UIF);
 *   4 wfi_masked_release   — idem com __WFI() na janela mascarada;
 *   5 disabled_source      — controlo negativo: IRQ NVIC desabilitada o ensaio
 *                            inteiro; serviced tem de ser 0.
 *
 * Rows (a..f) = serviced, expected, coalesced, min_gap_ticks, max_gap_ticks,
 * flags_end. expected mede-se pela janela DWT (elapsed/8000, ±1 de
 * quantização) de forma INDEPENDENTE do contador do ISR; coalesced =
 * expected − serviced por construção (invariante do analyzer).
 *
 * Eventos: S2_ENTER/S2_EXIT por serviço (writer FIDELITY_IRQ_A) só nos
 * primeiros 3 serviços de cada ensaio; S2_MASK/S2_RELEASE (writer
 * FIDELITY_MAIN) nas condições 3/4. Budget: IRQ_A 5×3×3×2=90;
 * MAIN 2×3×2+BOOT=13 (≤128 por writer).
 *
 * Trial ids globais 1..15 (3 trials × 5 condições).
 */

#include "board.h"
#include "periph.h"
#include "fidelity.h"

#define S2_SEED             123U
#define S2_PERIOD_TICKS     8000U              /* 1 kHz @ HSI 8 MHz */
#define S2_WINDOW_PERIODS   64U
#define S2_WINDOW_TICKS     (S2_WINDOW_PERIODS * S2_PERIOD_TICKS)
#define S2_MASK_TICKS       (5U * S2_PERIOD_TICKS)
#define S2_TRIALS_PER_COND  3U
#define S2_TRACE_SERVICES   3U                 /* serviços instrumentados/ensaio */

/* ── estado partilhado ISR↔MAIN (volatile) ── */
static volatile uint32_t s_serviced;
static volatile uint32_t s_prev_ticks;
static volatile uint32_t s_min_gap;
static volatile uint32_t s_max_gap;
static volatile uint32_t s_traced;
static volatile uint32_t s_trial;
static volatile uint32_t s_spin;

/**
 * @brief ISR única do TIM2: limpa UIF, atualiza estatística de gaps (DWT) e
 *        instrumenta S2_ENTER/S2_EXIT só nos primeiros S2_TRACE_SERVICES
 *        serviços de cada ensaio. Writer físico fixo: FIDELITY_IRQ_A.
 */
void TIM2_IRQHandler(void);

void TIM2_IRQHandler(void)
{
    uint32_t now = fidelity_ticks();
    uint32_t do_trace = (s_traced < S2_TRACE_SERVICES) ? 1U : 0U;

    if (do_trace != 0U) {
        fidelity_trace(FIDELITY_IRQ_A, FIDELITY_S2_ENTER, s_trial, s_serviced);
        s_traced = s_traced + 1U;
    }

    LL_TIM_ClearFlag_UPDATE(TIM2);

    if (s_serviced != 0U) {
        uint32_t gap = now - s_prev_ticks;
        if (gap < s_min_gap) {
            s_min_gap = gap;
        }
        if (gap > s_max_gap) {
            s_max_gap = gap;
        }
    }
    s_prev_ticks = now;

    if (do_trace != 0U) {
        fidelity_trace(FIDELITY_IRQ_A, FIDELITY_S2_EXIT, s_trial, s_serviced);
    }
    s_serviced = s_serviced + 1U;
}

/* Espera busy com carga real num contador volatile. */
static void busy_wait_ticks(uint32_t ticks)
{
    uint32_t t0 = fidelity_ticks();
    do {
        s_spin = s_spin + 1U;
    } while ((fidelity_ticks() - t0) < ticks);
}

/**
 * @brief Executa um ensaio completo da condição @p cond com id @p trial.
 *
 * A máscara da condição 3 usa NVIC_DisableIRQ (fundo busy, sem WFI). A da
 * condição 4 usa PRIMASK (__disable_irq): um IRQ mascarado por PRIMASK
 * continua a acordar o __WFI() (semântica ARM), enquanto um IRQ desabilitado
 * no NVIC poderia não o acordar e penduraria o ensaio. Nos dois casos o
 * periférico mantém-se a contar com UIE ligada — as flags coalescem e o
 * desmascaramento produz um único serviço.
 */
static void run_trial(uint32_t cond, uint32_t trial)
{
    /* Reset determinístico do estado e do TIM2. */
    NVIC_DisableIRQ(TIM2_IRQn);
    LL_TIM_DisableIT_UPDATE(TIM2);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_SetCounter(TIM2, 0U);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    s_serviced = 0U;
    s_prev_ticks = 0U;
    s_traced = 0U;
    s_trial = trial;
    s_min_gap = 0xFFFFFFFFU;
    s_max_gap = 0U;

    LL_TIM_EnableIT_UPDATE(TIM2);
    if (cond != 5U) {
        NVIC_ClearPendingIRQ(TIM2_IRQn);
        NVIC_EnableIRQ(TIM2_IRQn);
    }
    LL_TIM_EnableCounter(TIM2);

    uint32_t t0 = fidelity_ticks();
    uint32_t masked = 0U;

    if (cond == 1U || cond == 3U) {
        while ((fidelity_ticks() - t0) < S2_WINDOW_TICKS) {
            s_spin = s_spin + 1U;
            if (cond == 3U && masked == 0U && s_serviced >= 4U) {
                masked = 1U;
                NVIC_DisableIRQ(TIM2_IRQn);
                fidelity_trace(FIDELITY_MAIN, FIDELITY_S2_MASK, trial, 0U);
                busy_wait_ticks(S2_MASK_TICKS);
                fidelity_trace(FIDELITY_MAIN, FIDELITY_S2_RELEASE, trial, 0U);
                NVIC_ClearPendingIRQ(TIM2_IRQn);
                NVIC_EnableIRQ(TIM2_IRQn);
            }
        }
    } else if (cond == 2U || cond == 4U) {
        while ((fidelity_ticks() - t0) < S2_WINDOW_TICKS) {
            __WFI();
            if (cond == 4U && masked == 0U && s_serviced >= 4U) {
                masked = 1U;
                __disable_irq();
                fidelity_trace(FIDELITY_MAIN, FIDELITY_S2_MASK, trial, 0U);
                uint32_t tm = fidelity_ticks();
                while ((fidelity_ticks() - tm) < S2_MASK_TICKS) {
                    __WFI();
                }
                fidelity_trace(FIDELITY_MAIN, FIDELITY_S2_RELEASE, trial, 0U);
                __enable_irq();
            }
        }
    } else {
        /* Condição 5: janela inteira com IRQ NVIC desabilitada (serviced=0). */
        busy_wait_ticks(S2_WINDOW_TICKS);
    }

    /* Parar fontes antes de medir/registar. */
    uint32_t elapsed = fidelity_ticks() - t0;
    NVIC_DisableIRQ(TIM2_IRQn);
    LL_TIM_DisableIT_UPDATE(TIM2);
    LL_TIM_DisableCounter(TIM2);

    uint32_t serviced = s_serviced;
    uint32_t expected = elapsed / S2_PERIOD_TICKS;
    if (expected < serviced) {
        /* Quantização ±1 do cronómetro: nunca afirmar menos do que observado. */
        expected = serviced;
    }
    uint32_t coalesced = expected - serviced;
    uint32_t min_gap = (serviced >= 2U) ? s_min_gap : 0U;
    uint32_t max_gap = (serviced >= 2U) ? s_max_gap : 0U;
    uint32_t flags_end = TIM2->SR;

    fidelity_result(trial, cond, serviced, expected, coalesced,
                    min_gap, max_gap, flags_end);
}

int main(void)
{
    board_init();
    fidelity_init(2U, S2_SEED);

    NVIC_SetPriority(TIM2_IRQn, 2U);
    tim_1khz_init(TIM2);              /* PSC=7, ARR=999; gera UG — limpar a seguir */
    LL_TIM_ClearFlag_UPDATE(TIM2);

    uint32_t trial = 1U;
    for (uint32_t cond = 1U; cond <= 5U; ++cond) {
        for (uint32_t t = 0U; t < S2_TRIALS_PER_COND; ++t) {
            run_trial(cond, trial);
            ++trial;
        }
    }

    /* Ensaio completo: congela o snapshot (DONE). */
    fidelity_finish(0U);
}
