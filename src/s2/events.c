/**
 * @file    src/s2/events.c
 * @brief   S2B — semântica de eventos TIM2 → NVIC (testes de registrador).
 *
 * Cada condição é um teste pequeno com resultado esperado no HW derivado do
 * manual (RM0008 §15 TIM2-5; PM0056 §4.2 NVIC). O mesmo ELF roda no Renode;
 * divergências são achados de fidelidade FUNCIONAL do modelo.
 *
 *  1 uif_no_uie       UIE=0, timer correndo 3,5 períodos → UIF, pendente NVIC
 *  2 coalesce         UIE=1, IRQ desabilitada no NVIC por 5,5 períodos, depois
 *                     habilitada → nº de entradas na ISR (coalescência)
 *  3 clear_both       como 2, mas limpa UIF E ICPR antes de habilitar
 *  4 stale_pending    como 2, limpa só UIF (pendência do NVIC fica latched)
 *  5 late_clear       ISR limpa UIF como ÚLTIMO acesso (APB1 /1), 16 updates
 *  6 late_clear_apb2  idem com APB1 /2 (escrita mais lenta) → ISR dupla?
 *  7 late_clear_dsb   idem 6 + DSB após limpar (correção documentada)
 *  8 psc_buffered     PSC 0→1 escrito no meio do período (bufferizado no HW)
 *  9 ug_uif           UIE=0, EGR.UG → UIF? (URS=0)
 * 10 arr_preload      ARPE=1, ARR 999→1999 no meio do período
 * 11 late_clear_rb    idem 6, com leitura de volta do SR após limpar
 *
 * Observado (HW, 2026-10-07): limpar UIF como último acesso reentra a ISR
 * uma vez por evento mesmo com DSB; a 1ª execução de cada caminho em flash
 * é mais lenta (ver S1A) — por isso 2 trials e comparação pelo trial 2.
 *
 * Rows: trial 1..2 por condição; v0..v5 conforme firmware.py.
 */
#include "board.h"
#include "periph.h"
#include "fidelity.h"

#define S2B_SEED     0x5EED0022U
#define S2B_TRIALS   2U
#define S2B_ARR      999U          /* período = 1000 ciclos (PSC = 0) */
#define S2B_STORM    64U           /* guarda contra tempestade de IRQ */

enum { ISR_EARLY = 0, ISR_LATE = 1, ISR_LATE_DSB = 2, ISR_LATE_READBACK = 3 };

void TIM2_IRQHandler(void);

static volatile uint32_t s_mode;
static volatile uint32_t s_entries;
static volatile uint32_t s_spurious;
static volatile uint32_t s_first_sr;
static volatile uint32_t s_sink;

void TIM2_IRQHandler(void)
{
    uint32_t sr = TIM2->SR;
    if (s_mode == ISR_EARLY) {
        TIM2->SR = ~TIM_SR_UIF;      /* limpa logo na entrada */
    }
    uint32_t n = s_entries;
    if (n == 0U) {
        s_first_sr = sr;
    }
    if ((sr & TIM_SR_UIF) == 0U) {
        s_spurious = s_spurious + 1U;
    }
    s_entries = n + 1U;
    if (n + 1U >= S2B_STORM) {
        TIM2->DIER = 0U;
    }
    switch (s_mode) {
    case ISR_LATE:
        s_sink = sr;                 /* algum trabalho antes de limpar */
        TIM2->SR = ~TIM_SR_UIF;      /* último acesso antes do retorno */
        break;
    case ISR_LATE_DSB:
        s_sink = sr;
        TIM2->SR = ~TIM_SR_UIF;
        __DSB();
        break;
    case ISR_LATE_READBACK:
        s_sink = sr;
        TIM2->SR = ~TIM_SR_UIF;
        (void)TIM2->SR;              /* leitura de volta pela ponte APB */
        break;
    default:
        break;
    }
}

static void wait_ticks(uint32_t ticks)
{
    uint32_t t0 = fidelity_now();
    while ((fidelity_now() - t0) < ticks) {
    }
}

static void tim_stop_clear(void)
{
    TIM2->CR1 = 0U;
    TIM2->DIER = 0U;
    NVIC_DisableIRQ(TIM2_IRQn);
    TIM2->SR = 0U;
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    TIM2->PSC = 0U;
    TIM2->ARR = S2B_ARR;
    TIM2->EGR = TIM_EGR_UG;          /* carrega PSC/ARR */
    TIM2->SR = 0U;
    TIM2->CNT = 0U;
    s_entries = 0U;
    s_spurious = 0U;
    s_first_sr = 0xFFFFFFFFU;
    s_mode = ISR_EARLY;
}

/* Espera o próximo UIF por polling; devolve DWT do instante observado. */
static uint32_t poll_uif(void)
{
    uint32_t t0 = fidelity_now();
    while ((TIM2->SR & TIM_SR_UIF) == 0U) {
        if ((fidelity_now() - t0) > 100000U) {
            fidelity_flag(FIDELITY_ERR_TIMEOUT);
            break;
        }
    }
    uint32_t t = fidelity_now();
    TIM2->SR = 0U;
    return t;
}

static void cond_uif_no_uie(uint32_t trial)
{
    tim_stop_clear();
    TIM2->CR1 = TIM_CR1_CEN;
    wait_ticks(3500U);
    uint32_t uif = TIM2->SR & TIM_SR_UIF;
    uint32_t pend = NVIC_GetPendingIRQ(TIM2_IRQn);
    TIM2->CR1 = 0U;
    fidelity_row(trial, 1U, uif, pend, 0U, 0U, 0U, 0U);
}

static void cond_coalesce(uint32_t trial, uint32_t cond)
{
    tim_stop_clear();
    TIM2->DIER = TIM_DIER_UIE;
    TIM2->CR1 = TIM_CR1_CEN;
    wait_ticks(5500U);                /* 5 updates com a IRQ desabilitada */
    TIM2->CR1 = 0U;
    uint32_t uif = TIM2->SR & TIM_SR_UIF;
    uint32_t pend = NVIC_GetPendingIRQ(TIM2_IRQn);
    if (cond == 3U) {
        TIM2->SR = 0U;
        NVIC_ClearPendingIRQ(TIM2_IRQn);
    } else if (cond == 4U) {
        TIM2->SR = 0U;
    }
    uint32_t pend_before = NVIC_GetPendingIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(TIM2_IRQn);
    wait_ticks(2000U);
    NVIC_DisableIRQ(TIM2_IRQn);
    fidelity_row(trial, cond, uif, pend, pend_before, s_entries,
                 s_first_sr & 0xFFFFU, s_spurious);
}

static void cond_late_clear(uint32_t trial, uint32_t cond)
{
    tim_stop_clear();
    uint32_t cfgr = RCC->CFGR;
    if (cond != 5U) {
        RCC->CFGR = (cfgr & ~RCC_CFGR_PPRE1) | RCC_CFGR_PPRE1_DIV2;
    }
    uint32_t cfgr_now = RCC->CFGR;
    s_mode = (cond == 7U) ? ISR_LATE_DSB : (cond == 11U) ? ISR_LATE_READBACK : ISR_LATE;
    TIM2->DIER = TIM_DIER_UIE;
    NVIC_EnableIRQ(TIM2_IRQn);
    TIM2->CR1 = TIM_CR1_CEN;
    wait_ticks(16U * 1000U + 500U);   /* 16 updates */
    TIM2->CR1 = 0U;
    TIM2->DIER = 0U;
    NVIC_DisableIRQ(TIM2_IRQn);
    RCC->CFGR = cfgr;
    s_mode = ISR_EARLY;
    fidelity_row(trial, cond, s_entries, s_spurious, (cfgr_now >> 8) & 7U, 0U, 0U, 0U);
}

/* Escreve um registrador de tempo-base no meio do período e mede, por
 * polling de UIF, o intervalo até o próximo update e o período seguinte. */
static void cond_midperiod_write(uint32_t trial, uint32_t cond)
{
    tim_stop_clear();
    if (cond == 10U) {
        TIM2->CR1 = TIM_CR1_ARPE;
    }
    TIM2->CR1 |= TIM_CR1_CEN;
    uint32_t t_prev = poll_uif();                       /* alinha num update */
    uint32_t t_ref = poll_uif();
    uint32_t base_period = t_ref - t_prev;
    while (TIM2->CNT < 500U) {
    }
    uint32_t t_write = fidelity_now();
    if (cond == 8U) {
        TIM2->PSC = 1U;
    } else {
        TIM2->ARR = 1999U;
    }
    uint32_t t1 = poll_uif();
    uint32_t t2 = poll_uif();
    TIM2->CR1 = 0U;
    fidelity_row(trial, cond, base_period, t1 - t_write, t2 - t1, t_write - t_ref, 0U, 0U);
}

static void cond_ug_uif(uint32_t trial)
{
    tim_stop_clear();
    TIM2->SR = 0U;
    uint32_t before = TIM2->SR & TIM_SR_UIF;
    TIM2->EGR = TIM_EGR_UG;
    wait_ticks(64U);                 /* deixa a escrita/flag assentarem */
    uint32_t after = TIM2->SR & TIM_SR_UIF;
    uint32_t cnt = TIM2->CNT;
    fidelity_row(trial, 9U, before, after, cnt, 0U, 0U, 0U);
}

int main(void)
{
    board_init();
    fidelity_init(2U, 2U, S2B_SEED);
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    NVIC_SetPriority(TIM2_IRQn, 4U);

    for (uint32_t trial = 1U; trial <= S2B_TRIALS; ++trial) {
        fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_BEGIN, trial, 0U);
        cond_uif_no_uie(trial);
        cond_coalesce(trial, 2U);
        cond_coalesce(trial, 3U);
        cond_coalesce(trial, 4U);
        cond_late_clear(trial, 5U);
        cond_late_clear(trial, 6U);
        cond_late_clear(trial, 7U);
        cond_midperiod_write(trial, 8U);
        cond_ug_uif(trial);
        cond_midperiod_write(trial, 10U);
        cond_late_clear(trial, 11U);
        fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_END, trial, 0U);
    }
    tim_stop_clear();
    fidelity_finish();
}
