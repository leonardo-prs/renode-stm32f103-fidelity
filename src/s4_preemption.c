/**
 * @file    src/s4_preemption.c
 * @brief   S4 — preempção vs arbitragem (cenário 4 da ABI fidelity v1).
 *
 * Prova o comportamento ARQUITETURAL do NVIC (PM0056 §2.3.5–7) com IRQs
 * software-pended (TIM2_IRQn + TIM3_IRQn, sem estímulo de periférico): não
 * é latência de evento externo. Condições (códigos exatos do contrato
 * RESULT_CONTRACT[4] em scripts/fidelity_analyze.py):
 *   1 positive_preempt   — L (requester) fraco, H (requested) forte → H
 *                          PREEMPTA L;
 *   2 neg_same_group_sub — mesmo grupo [7:5], sub [4] diferente → sem
 *                          preempção (H corre após L);
 *   3 neg_equal_priority — prioridades idênticas → sem preempção;
 *   4 swap_preempt       — roles físicos trocados (L=TIM3, H=TIM2): prova
 *                          que a preempção segue a prioridade, não a identidade;
 *   5 arbitration        — ambos pended simultâneos, liberação em tail-chain
 *                          pela prioridade (ordem de arbitragem, não preempção).
 *
 * Agrupamento OBRIGATÓRIO: AIRCR PRIGROUP = 4 → 3 bits de grupo [7:5] + 1
 * bit de subprioridade [4]. A condição 2 só é expressível com bit de
 * subprioridade nos 4 bits implementados do F1. NÃO usar o
 * NVIC_PRIORITYGROUP_4 (0x3) do board.h — esse é o split 4:0, sem sub.
 *
 * Canais FÍSICOS fixos (nunca trocar com roles): TIM2_IRQHandler →
 * FIDELITY_IRQ_A (1); TIM3_IRQHandler → FIDELITY_IRQ_B (2). Na condição 4
 * os roles L/H invertem-se; os canais mantêm-se.
 *
 * Cadeia por ensaio (validada como S4_ORDER pelo analyzer):
 *   L: LENTER(0x400) → REQUEST(0x401) → pend H → RESUME(0x404) → LEXIT(0x405)
 *   H: HENTER(0x402) → HEXIT(0x403)
 *   Préempção: LENTER<REQUEST<HENTER<HEXIT<RESUME<LEXIT (H aninhado).
 *   Negativos: HENTER/HEXIT após LEXIT (sem aninhamento).
 *   Condição 5: ARB_ENTER(0x406) no 1º handler, ARB_EXIT(0x407) no 2º.
 *
 * Rows (a..f) = order_ok, low_active_at_henter, ipsr_at_henter, msp_delta
 * (MSP em LENTER − MSP em HENTER), h_pending_after (bit ISPR de H em LEXIT),
 * 0. 2 trials × 5 condições = 10 rows, trial ids globais 1..10.
 * Trace: 48 eventos de cadeia + 4 ARB + BOOT = 53 (≤128 por writer).
 */

#include "board.h"
#include "fidelity.h"

#define S4_SEED           123U
#define S4_TIMEOUT_TICKS 80000U              /* ~10 ms @ 8 MHz */
#define S4_TRIALS_PER_COND 2U
/* PRIGROUP = 4: 3 bits de grupo [7:5] + 1 bit de subprioridade [4]. */
#define S4_PRIGROUP      4U

/* Valores do parâmetro de NVIC_SetPriority (byte de registo = v << 4). */
#define S4_PRIO_G1_SUB0  2U                  /* 0x20: grupo 001, sub 0 */
#define S4_PRIO_G1_SUB1  3U                  /* 0x30: grupo 001, sub 1 */
#define S4_PRIO_G3_SUB0  6U                  /* 0x60: grupo 011, sub 0 */

typedef struct {
    uint32_t cond;
    uint32_t l_is_tim3;   /* 0: L=TIM2/H=TIM3 · 1: L=TIM3/H=TIM2 */
    uint32_t prio_tim2;
    uint32_t prio_tim3;
    uint32_t arb_expect;  /* condição 5: 2=TIM2 primeiro · 3=TIM3 primeiro */
} S4Cfg;

static const S4Cfg s_cfg[5] = {
    { 1U, 0U, S4_PRIO_G3_SUB0, S4_PRIO_G1_SUB0, 0U },
    { 2U, 0U, S4_PRIO_G1_SUB0, S4_PRIO_G1_SUB1, 0U },
    { 3U, 0U, S4_PRIO_G1_SUB0, S4_PRIO_G1_SUB0, 0U },
    { 4U, 1U, S4_PRIO_G1_SUB0, S4_PRIO_G3_SUB0, 0U },
    { 5U, 0U, S4_PRIO_G1_SUB0, S4_PRIO_G3_SUB0, 2U },
};

/* ── estado partilhado ISR↔MAIN (volatile) ── */
static volatile uint32_t s_trial;
static volatile uint32_t s_mode_arb;
static volatile uint32_t s_h_is_tim2;
static volatile uint32_t s_low_active;
static volatile uint32_t s_low_done;
static volatile uint32_t s_high_done;
static volatile uint32_t s_arb_first;
static volatile uint32_t s_arb_exits;
/* Evidência (timestamps DWT + leituras nos handlers). */
static volatile uint32_t s_t_lenter, s_t_request, s_t_resume, s_t_lexit;
static volatile uint32_t s_t_henter, s_t_hexit;
static volatile uint32_t s_msp_lenter, s_msp_henter;
static volatile uint32_t s_ipsr_henter;
static volatile uint32_t s_low_active_at_henter;
static volatile uint32_t s_h_pending_after;

void TIM2_IRQHandler(void);
void TIM3_IRQHandler(void);

/* ── caminhos por role ── */

static void low_handler(uint32_t writer, uint32_t h_is_tim2)
{
    IRQn_Type h_irqn = h_is_tim2 ? TIM2_IRQn : TIM3_IRQn;

    s_msp_lenter = __get_MSP();
    s_t_lenter = fidelity_ticks();
    fidelity_trace(writer, FIDELITY_S4_LENTER, s_trial, 0U);

    s_low_active = 1U;
    s_t_request = fidelity_ticks();
    fidelity_trace(writer, FIDELITY_S4_REQUEST, s_trial, 0U);
    NVIC_SetPendingIRQ(h_irqn);
    /* Se H preempta, já correu quando as próximas instruções executam. */
    s_t_resume = fidelity_ticks();
    fidelity_trace(writer, FIDELITY_S4_RESUME, s_trial, 0U);

    s_t_lexit = fidelity_ticks();
    fidelity_trace(writer, FIDELITY_S4_LEXIT, s_trial, 0U);
    /* Em LEXIT: 1 nos negativos (H ainda pendente), 0 na preempção. */
    s_h_pending_after = (NVIC_GetPendingIRQ(h_irqn) != 0U) ? 1U : 0U;
    s_low_active = 0U;
    s_low_done = 1U;
}

static void high_handler(uint32_t writer)
{
    s_msp_henter = __get_MSP();
    s_t_henter = fidelity_ticks();
    s_ipsr_henter = __get_IPSR();
    s_low_active_at_henter = s_low_active;
    fidelity_trace(writer, FIDELITY_S4_HENTER, s_trial, 0U);

    s_t_hexit = fidelity_ticks();
    fidelity_trace(writer, FIDELITY_S4_HEXIT, s_trial, 0U);
    s_high_done = 1U;
}

static void arb_handler(uint32_t writer, uint32_t self_is_tim2)
{
    if (s_arb_first == 0U) {
        s_arb_first = self_is_tim2 ? 2U : 3U;
        s_ipsr_henter = __get_IPSR();
        fidelity_trace(writer, FIDELITY_S4_ARB_ENTER, s_trial, 0U);
    }
    s_arb_exits = s_arb_exits + 1U;
    if (s_arb_exits == 2U) {
        fidelity_trace(writer, FIDELITY_S4_ARB_EXIT, s_trial, 0U);
    }
}

/* Canais físicos fixos: TIM2 → IRQ_A, TIM3 → IRQ_B. */
void TIM2_IRQHandler(void)
{
    if (s_mode_arb != 0U) {
        arb_handler(FIDELITY_IRQ_A, 1U);
    } else if (s_h_is_tim2 != 0U) {
        high_handler(FIDELITY_IRQ_A);
    } else {
        low_handler(FIDELITY_IRQ_A, 0U);
    }
}

void TIM3_IRQHandler(void)
{
    if (s_mode_arb != 0U) {
        arb_handler(FIDELITY_IRQ_B, 0U);
    } else if (s_h_is_tim2 != 0U) {
        low_handler(FIDELITY_IRQ_B, 1U);
    } else {
        high_handler(FIDELITY_IRQ_B);
    }
}

/* Espera limitada: nunca pendurar se uma IRQ não chegar. */
static uint32_t wait_counter(volatile uint32_t *counter, uint32_t want)
{
    uint32_t t0 = fidelity_ticks();
    while (*counter < want) {
        if ((fidelity_ticks() - t0) > S4_TIMEOUT_TICKS) {
            return 0U;
        }
    }
    return 1U;
}

static void run_trial(const S4Cfg *cfg, uint32_t trial)
{
    s_trial = trial;
    s_mode_arb = 0U;
    s_h_is_tim2 = cfg->l_is_tim3 ? 1U : 0U;
    s_low_active = 0U;
    s_low_done = 0U;
    s_high_done = 0U;
    s_arb_first = 0U;
    s_arb_exits = 0U;
    s_t_lenter = s_t_request = s_t_resume = s_t_lexit = 0U;
    s_t_henter = s_t_hexit = 0U;
    s_msp_lenter = s_msp_henter = 0U;
    s_ipsr_henter = 0U;
    s_low_active_at_henter = 0U;
    s_h_pending_after = 0U;

    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_DisableIRQ(TIM3_IRQn);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    NVIC_SetPriority(TIM2_IRQn, cfg->prio_tim2);
    NVIC_SetPriority(TIM3_IRQn, cfg->prio_tim3);
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(TIM3_IRQn);

    uint32_t order_ok;
    uint32_t low_at_h;
    uint32_t ipsr;
    uint32_t msp_delta;
    uint32_t h_pending;

    if (cfg->cond == 5U) {
        /* Arbitragem: ambos pended do MAIN, nenhum ativo; liberação por
         * prioridade em tail-chain (TIM3 mais fraco pendido primeiro). */
        s_mode_arb = 1U;
        NVIC_SetPendingIRQ(TIM3_IRQn);
        NVIC_SetPendingIRQ(TIM2_IRQn);
        uint32_t ok = wait_counter(&s_arb_exits, 2U);
        order_ok = (ok != 0U && s_arb_first == cfg->arb_expect) ? 1U : 0U;
        low_at_h = 0U;
        ipsr = s_ipsr_henter;
        msp_delta = 0U;
        h_pending = 0U;
    } else {
        s_mode_arb = 0U;
        NVIC_SetPendingIRQ(cfg->l_is_tim3 ? TIM3_IRQn : TIM2_IRQn);
        uint32_t ok_low = wait_counter(&s_low_done, 1U);
        uint32_t ok_high = wait_counter(&s_high_done, 1U);
        uint32_t ok = (ok_low != 0U && ok_high != 0U);
        if (cfg->cond == 1U || cfg->cond == 4U) {
            /* Preempção: H aninhado entre REQUEST e RESUME. */
            order_ok = (ok != 0U &&
                        s_t_lenter < s_t_request && s_t_request < s_t_henter &&
                        s_t_henter < s_t_hexit && s_t_hexit < s_t_resume &&
                        s_t_resume < s_t_lexit) ? 1U : 0U;
        } else {
            /* Negativos: H só depois de LEXIT. */
            order_ok = (ok != 0U &&
                        s_t_request < s_t_lexit && s_t_lexit < s_t_henter) ? 1U : 0U;
        }
        low_at_h = s_low_active_at_henter;
        ipsr = s_ipsr_henter;
        /* Evidência de aninhamento (2 frames): positiva quando H aninhou. */
        msp_delta = s_msp_lenter - s_msp_henter;
        h_pending = s_h_pending_after;
    }

    /* Parar fontes e quiescer antes de registar. */
    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_DisableIRQ(TIM3_IRQn);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);

    fidelity_result(trial, cfg->cond, order_ok, low_at_h, ipsr,
                    msp_delta, h_pending, 0U);
}

int main(void)
{
    board_init();
    /* Sobrepõe o grouping do board_init (4:0): 3 grupo + 1 sub. */
    NVIC_SetPriorityGrouping(S4_PRIGROUP);
    fidelity_init(4U, S4_SEED);

    uint32_t trial = 1U;
    for (uint32_t c = 0U; c < 5U; ++c) {
        for (uint32_t t = 0U; t < S4_TRIALS_PER_COND; ++t) {
            run_trial(&s_cfg[c], trial);
            ++trial;
        }
    }

    /* Ensaio completo: congela o snapshot (DONE). */
    fidelity_finish(0U);
}
