/**
 * @file    src/s4/race.c
 * @brief   S4B — corrida temporal: late-arrival × preempção × sequencial.
 *
 * UM timer (TIM1, PSC = 0, contador a 8 MHz) gera dois eventos com
 * defasagem exata de Δ ciclos: UPDATE (CNT → 0) na IRQ TIM1_UP (25, L,
 * prioridade baixa) e COMPARE CC1 (CNT == Δ) na IRQ TIM1_CC (27, H, alta).
 * O L fica ~150 ciclos ocupado. Pelo modelo de exceções do Cortex-M3
 * (DDI0337G §5.5 12 ciclos de entrada, §5.7 late-arriving):
 *   Δ pequeno  → H chega antes do 1º instrução de L executar: LATE-ARRIVAL
 *                (H roda primeiro, L entra por tail-chain, sem 2º stacking);
 *   Δ médio    → H PREEMPTA L (aninha: dois quadros na pilha);
 *   Δ > L      → SEQUENCIAL (L termina antes de H pender).
 * No Renode (tlib) a entrada de exceção não custa ciclos e o stacking é
 * atômico: a janela de late-arrival deve encolher para ~0.
 * Nenhuma saída de canal é habilitada (CCxE = 0): PA8..PA10 intocados
 * (loopback físico PA9→PA10 da bancada).
 *
 * Classificação (análise): o discriminante é L ATIVO quando H entra
 * (NVIC IABR bit 25): ativo → preempção; inativo e H antes de L → late-
 * arrival/arbitragem; L saiu antes de H → sequencial.
 *
 * Rows (cond 1; trial 0 = aquecimento Δ=100, descartável; 1.. = varredura):
 *   v0 = Δ, v1 = CNT na 1ª leitura de L, v2 = CNT na 1ª leitura de H,
 *   v3 = código de ordem (seq.h; 1 Le 2 Lx 3 He 4 Hx) | (IABR[0] bit 25 << 24)
 *        | (IABR[0] bit 27 << 25), v4 = t(L entra) − t(H entra) [int32],
 *   v5 = t(L entra) − t(H sai) [int32] (≈ encadeamento no late-arrival).
 * H que nunca entra (ex.: compare não dispara) aparece como ordem sem 3/4.
 */
#include "board.h"
#include "fidelity.h"
#include "seq.h"

#define S4B_SEED     0x5EED0042U
#define S4B_ARR      1999U
#define S4B_LEAD     40U          /* CNT inicial = ARR − LEAD */
#define S4B_L_BUSY   150U
#define S4B_REPS     2U
#define S4B_TIMEOUT  20000U

enum { EV_LE = 1, EV_LX = 2, EV_HE = 3, EV_HX = 4 };

void TIM1_UP_IRQHandler(void);
void TIM1_CC_IRQHandler(void);

static SeqLog s_log;
static volatile uint32_t s_done;
static volatile uint32_t s_l_cnt, s_h_cnt, s_h_iabr;

void TIM1_UP_IRQHandler(void)
{
    uint32_t cnt = TIM1->CNT;
    uint32_t t = fidelity_now();
    TIM1->SR = ~TIM_SR_UIF;
    TIM1->DIER &= ~TIM_DIER_UIE;
    seq_mark(&s_log, EV_LE, t);
    s_l_cnt = cnt;
    while ((fidelity_now() - t) < S4B_L_BUSY) {
    }
    seq_mark(&s_log, EV_LX, fidelity_now());
    s_done |= 1U;
}

void TIM1_CC_IRQHandler(void)
{
    uint32_t cnt = TIM1->CNT;
    uint32_t t = fidelity_now();
    TIM1->SR = ~TIM_SR_CC1IF;
    TIM1->DIER &= ~TIM_DIER_CC1IE;
    seq_mark(&s_log, EV_HE, t);
    s_h_cnt = cnt;
    s_h_iabr = NVIC->IABR[0];
    seq_mark(&s_log, EV_HX, fidelity_now());
    s_done |= 2U;
}

static void run_delta(uint32_t trial, uint32_t delta)
{
    TIM1->CR1 = 0U;
    TIM1->DIER = 0U;
    NVIC_DisableIRQ(TIM1_UP_IRQn);
    NVIC_DisableIRQ(TIM1_CC_IRQn);
    seq_reset(&s_log);
    s_done = 0U;
    s_l_cnt = s_h_cnt = s_h_iabr = 0U;

    TIM1->CNT = S4B_ARR - S4B_LEAD;
    TIM1->CCR1 = delta;
    TIM1->SR = 0U;
    NVIC_ClearPendingIRQ(TIM1_UP_IRQn);
    NVIC_ClearPendingIRQ(TIM1_CC_IRQn);
    TIM1->DIER = TIM_DIER_UIE | TIM_DIER_CC1IE;
    NVIC_EnableIRQ(TIM1_UP_IRQn);
    NVIC_EnableIRQ(TIM1_CC_IRQn);
    TIM1->CR1 = TIM_CR1_CEN;

    uint32_t t0 = fidelity_now();
    while (s_done != 3U && (fidelity_now() - t0) < S4B_TIMEOUT) {
    }
    TIM1->CR1 = 0U;
    TIM1->DIER = 0U;
    NVIC_DisableIRQ(TIM1_UP_IRQn);
    NVIC_DisableIRQ(TIM1_CC_IRQn);
    TIM1->SR = 0U;

    uint32_t order = seq_order_code(&s_log)
                   | (((s_h_iabr >> TIM1_UP_IRQn) & 1U) << 24)
                   | (((s_h_iabr >> TIM1_CC_IRQn) & 1U) << 25);
    fidelity_row(trial, 1U, delta, s_l_cnt, s_h_cnt, order,
                 s_log.ticks[EV_LE] - s_log.ticks[EV_HE],
                 s_log.ticks[EV_LE] - s_log.ticks[EV_HX]);
}

int main(void)
{
    board_init();                         /* PRIGROUP 4 bits de grupo */
    fidelity_init(4U, 2U, S4B_SEED);

    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_TIM1);
    TIM1->CR1 = 0U;
    TIM1->PSC = 0U;
    TIM1->ARR = S4B_ARR;
    TIM1->RCR = 0U;
    TIM1->CCMR1 = 0U;                     /* CC1 = saída "frozen": só compara */
    TIM1->CCER = 0U;                      /* nenhum pino */
    TIM1->EGR = TIM_EGR_UG;
    TIM1->SR = 0U;
    NVIC_SetPriority(TIM1_UP_IRQn, 8U);   /* L */
    NVIC_SetPriority(TIM1_CC_IRQn, 2U);   /* H */

    static const uint32_t extra[] = { 50U, 75U, 100U, 125U, 150U, 175U, 200U, 250U, 300U, 400U };
    run_delta(0U, 100U);                  /* aquecimento (1ª execução em flash) */
    uint32_t trial = 0U;
    for (uint32_t rep = 0U; rep < S4B_REPS; ++rep) {
        for (uint32_t d = 0U; d <= 40U; ++d) {
            run_delta(++trial, d);
        }
        for (uint32_t i = 0U; i < sizeof(extra) / sizeof(extra[0]); ++i) {
            run_delta(++trial, extra[i]);
        }
    }
    fidelity_finish();
}
