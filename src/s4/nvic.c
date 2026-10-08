/**
 * @file    src/s4/nvic.c
 * @brief   S4A — preempção × arbitragem no NVIC (comportamento arquitetural).
 *
 * IRQs TIM2 (nº 28) e TIM3 (nº 29) disparadas por SOFTWARE (ISPR), sem
 * periférico: isola o NVIC. AIRCR.PRIGROUP = 4 → nos 4 bits implementados
 * do STM32F1, [7:5] = prioridade de grupo (preempção), [4] = subprioridade.
 * Regras (PM0056 §2.3.5–2.3.7, §4.3.5; ARMv7-M B1.5.4):
 *   - só prioridade de GRUPO maior (valor menor) preempta um handler ativo;
 *   - entre PENDENTES, vence o grupo, depois a subprioridade, depois o menor
 *     número de exceção;
 *   - BASEPRI bloqueia exceções de prioridade ≥ BASEPRI.
 *
 * Papéis nas condições de PEDIDO (1..5): L roda primeiro e pende H.
 *   1 preempt          L g3  pende H g1           → H aninha em L
 *   2 same_group_sub   L g1s1 pende H g1s0        → sem preempção (sub só ordena)
 *   3 equal            L g1 pende H g1            → sem preempção
 *   4 preempt_swapped  L = TIM3 g3, H = TIM2 g1   → H aninha (prioridade ≠ nº)
 *   5 lower_requested  L g1 pende H g3            → H depois de L
 * ARBITRAGEM (6..9): os dois pendentes com PRIMASK=1, depois liberados.
 *   6 arb_group        TIM2 g3, TIM3 g1  → TIM3 primeiro
 *   7 arb_sub          TIM2 g1s1, TIM3 g1s0 → TIM3 primeiro (subprioridade)
 *   8 arb_number       iguais → TIM2 primeiro (menor nº de exceção)
 *   9 arb_number_rev   iguais, TIM3 pendido antes → TIM2 primeiro
 * 10 basepri          BASEPRI = g2: pende TIM2 g3 e TIM3 g1 com PRIMASK=0 →
 *                     só TIM3 roda; TIM2 só após BASEPRI = 0
 * 11 self_repend      TIM2 repende a si mesmo na 1ª entrada → roda 2×
 *
 * Eventos (nibbles do código de ordem, seq.h):
 *   1 L_ENTER 2 L_REQ 3 H_ENTER 4 H_EXIT 5 L_RESUME 6 L_EXIT
 *   7 T2_ENTER 8 T2_EXIT 9 T3_ENTER 10 T3_EXIT 11 BASEPRI_CLEARED
 * Rows (trial 1..2 por condição):
 *   v0 = código de ordem, v1 = IPSR no 1º handler de prioridade alta,
 *   v2 = ICSR nesse instante, v3 = NVIC IABR[0] nesse instante,
 *   v4 = MSP(L) − MSP(H) (aninhamento empilha um quadro),
 *   v5 = Δticks (pedido → H_ENTER, ou saída → entrada no encadeamento).
 */
#include "board.h"
#include "fidelity.h"
#include "seq.h"

#define S4A_SEED      0x5EED0041U
#define S4A_TRIALS    2U
#define S4A_TIMEOUT   80000U

/* Prioridade p/ NVIC_SetPriority (4 bits): (grupo << 1) | sub. */
#define PRIO(g, s)    ((((uint32_t)(g)) << 1) | (uint32_t)(s))

enum { EV_L_ENTER = 1, EV_L_REQ, EV_H_ENTER, EV_H_EXIT, EV_L_RESUME, EV_L_EXIT,
       EV_T2_ENTER, EV_T2_EXIT, EV_T3_ENTER, EV_T3_EXIT, EV_BASEPRI_CLR };

enum { MODE_REQUEST = 0, MODE_ARB = 1 };

typedef struct {
    uint32_t cond;
    uint32_t mode;
    uint32_t prio2;
    uint32_t prio3;
    uint32_t l_is_tim3;      /* MODE_REQUEST: quem é L */
    uint32_t pend_tim3_first;
} S4Case;

static const S4Case s_cases[] = {
    {  1U, MODE_REQUEST, PRIO(3, 0), PRIO(1, 0), 0U, 0U },
    {  2U, MODE_REQUEST, PRIO(1, 1), PRIO(1, 0), 0U, 0U },
    {  3U, MODE_REQUEST, PRIO(1, 0), PRIO(1, 0), 0U, 0U },
    {  4U, MODE_REQUEST, PRIO(1, 0), PRIO(3, 0), 1U, 0U },
    {  5U, MODE_REQUEST, PRIO(1, 0), PRIO(3, 0), 0U, 0U },
    {  6U, MODE_ARB,     PRIO(3, 0), PRIO(1, 0), 0U, 0U },
    {  7U, MODE_ARB,     PRIO(1, 1), PRIO(1, 0), 0U, 0U },
    {  8U, MODE_ARB,     PRIO(1, 0), PRIO(1, 0), 0U, 0U },
    {  9U, MODE_ARB,     PRIO(1, 0), PRIO(1, 0), 0U, 1U },
    { 10U, MODE_ARB,     PRIO(3, 0), PRIO(1, 0), 0U, 0U },
    { 11U, MODE_ARB,     PRIO(1, 0), PRIO(1, 0), 0U, 0U },
};
#define S4A_CASES (sizeof(s_cases) / sizeof(s_cases[0]))

void TIM2_IRQHandler(void);
void TIM3_IRQHandler(void);

static SeqLog s_log;
static volatile uint32_t s_mode;
static volatile uint32_t s_cond;
static volatile uint32_t s_l_is_tim3;
static volatile uint32_t s_done;          /* bit 0: TIM2 saiu, bit 1: TIM3 */
static volatile uint32_t s_t2_entries;
static volatile uint32_t s_ipsr, s_icsr, s_iabr, s_msp_l, s_msp_h, s_probe_set;

static void probe_high(void)
{
    if (s_probe_set == 0U) {
        s_ipsr = __get_IPSR();
        s_icsr = SCB->ICSR;
        s_iabr = NVIC->IABR[0];
        s_msp_h = __get_MSP();
        s_probe_set = 1U;
    }
}

static void handle(uint32_t is_tim3)
{
    uint32_t t = fidelity_now();
    if (s_mode == MODE_REQUEST) {
        if (is_tim3 == s_l_is_tim3) {
            IRQn_Type h = is_tim3 ? TIM2_IRQn : TIM3_IRQn;
            seq_mark(&s_log, EV_L_ENTER, t);
            s_msp_l = __get_MSP();
            seq_mark(&s_log, EV_L_REQ, fidelity_now());
            NVIC_SetPendingIRQ(h);
            __DSB();                       /* AN321: pendência efetiva antes */
            __ISB();                       /* da próxima instrução           */
            seq_mark(&s_log, EV_L_RESUME, fidelity_now());
            seq_mark(&s_log, EV_L_EXIT, fidelity_now());
        } else {
            seq_mark(&s_log, EV_H_ENTER, t);
            probe_high();
            seq_mark(&s_log, EV_H_EXIT, fidelity_now());
        }
    } else {
        seq_mark(&s_log, is_tim3 ? EV_T3_ENTER : EV_T2_ENTER, t);
        probe_high();                      /* 1º handler a entrar */
        if (!is_tim3) {
            s_t2_entries = s_t2_entries + 1U;
            if (s_cond == 11U && s_t2_entries == 1U) {
                NVIC_SetPendingIRQ(TIM2_IRQn);     /* repende a si mesmo */
            }
        }
        seq_mark(&s_log, is_tim3 ? EV_T3_EXIT : EV_T2_EXIT, fidelity_now());
    }
    s_done |= is_tim3 ? 2U : 1U;
}

void TIM2_IRQHandler(void)
{
    handle(0U);
}

void TIM3_IRQHandler(void)
{
    handle(1U);
}

static uint32_t wait_done(uint32_t mask)
{
    uint32_t t0 = fidelity_now();
    while ((s_done & mask) != mask) {
        if ((fidelity_now() - t0) > S4A_TIMEOUT) {
            fidelity_flag(FIDELITY_ERR_TIMEOUT);
            return 0U;
        }
    }
    /* Dá tempo de um eventual 2º disparo (self_repend) terminar. */
    uint32_t t1 = fidelity_now();
    while ((fidelity_now() - t1) < 2000U) {
    }
    return 1U;
}

static void run_case(const S4Case *c, uint32_t trial)
{
    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_DisableIRQ(TIM3_IRQn);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    seq_reset(&s_log);
    s_mode = c->mode;
    s_cond = c->cond;
    s_l_is_tim3 = c->l_is_tim3;
    s_done = 0U;
    s_t2_entries = 0U;
    s_probe_set = 0U;
    s_ipsr = s_icsr = s_iabr = s_msp_l = s_msp_h = 0U;
    NVIC_SetPriority(TIM2_IRQn, c->prio2);
    NVIC_SetPriority(TIM3_IRQn, c->prio3);
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(TIM3_IRQn);
    __DSB();
    __ISB();

    uint32_t delta = 0U;
    if (c->mode == MODE_REQUEST) {
        NVIC_SetPendingIRQ(c->l_is_tim3 ? TIM3_IRQn : TIM2_IRQn);
        (void)wait_done(3U);
        delta = s_log.ticks[EV_H_ENTER] - s_log.ticks[EV_L_REQ];
    } else if (c->cond == 10U) {
        __set_BASEPRI(PRIO(2, 0) << (8U - __NVIC_PRIO_BITS));
        __ISB();
        NVIC_SetPendingIRQ(TIM2_IRQn);
        NVIC_SetPendingIRQ(TIM3_IRQn);
        __DSB();
        __ISB();
        (void)wait_done(2U);               /* só TIM3 pode rodar */
        uint32_t still = NVIC_GetPendingIRQ(TIM2_IRQn);
        seq_mark(&s_log, EV_BASEPRI_CLR, fidelity_now());
        __set_BASEPRI(0U);
        __ISB();
        (void)wait_done(3U);
        delta = still;                      /* 1 = TIM2 ficou pendente */
    } else {
        __disable_irq();
        if (c->pend_tim3_first != 0U) {
            NVIC_SetPendingIRQ(TIM3_IRQn);
            NVIC_SetPendingIRQ(TIM2_IRQn);
        } else {
            NVIC_SetPendingIRQ(TIM2_IRQn);
            NVIC_SetPendingIRQ(TIM3_IRQn);
        }
        __DSB();
        __enable_irq();
        __ISB();
        (void)wait_done(c->cond == 11U ? 1U : 3U);
        /* Encadeamento: saída do 1º → entrada do 2º. */
        uint32_t first_exit = (s_log.seq[EV_T2_ENTER] < s_log.seq[EV_T3_ENTER])
                            ? s_log.ticks[EV_T2_EXIT] : s_log.ticks[EV_T3_EXIT];
        uint32_t second_enter = (s_log.seq[EV_T2_ENTER] < s_log.seq[EV_T3_ENTER])
                              ? s_log.ticks[EV_T3_ENTER] : s_log.ticks[EV_T2_ENTER];
        delta = (c->cond == 11U) ? s_t2_entries : second_enter - first_exit;
    }

    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_DisableIRQ(TIM3_IRQn);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);

    uint32_t msp_delta = (c->mode == MODE_REQUEST) ? s_msp_l - s_msp_h : 0U;
    fidelity_row(trial, c->cond, seq_order_code(&s_log), s_ipsr, s_icsr, s_iabr,
                 msp_delta, delta);
}

int main(void)
{
    board_init();
    NVIC_SetPriorityGrouping(4U);          /* 3 bits de grupo + 1 de sub */
    fidelity_init(4U, 1U, S4A_SEED);
    for (uint32_t trial = 1U; trial <= S4A_TRIALS; ++trial) {
        for (uint32_t i = 0U; i < S4A_CASES; ++i) {
            run_case(&s_cases[i], trial);
        }
    }
    fidelity_finish();
}
