/**
 * @file    src/s2/latency.c
 * @brief   S2A — latência de IRQ periódica e razão CPU/periférico.
 *
 * TIM2: PSC = 0, ARR = 7999 → update a cada 8000 ciclos de HCLK (1 kHz) e
 * CNT contando a 8 MHz. A 1ª leitura da ISR é TIM2->CNT, que vale o nº de
 * ticks do timer desde o evento de update = LATÊNCIA medida por um
 * periférico, resolução de 1 ciclo (não depende do DWT).
 *   HW: entrada de exceção = 12 ciclos (DDI0337G §5.5) + instruções até a
 *       leitura + acesso APB.
 *   Renode: sem custo de entrada (tlib); IRQ aceita em fronteira de bloco.
 *
 * Condição = o que o MAIN executa quando o evento chega:
 *   1 alu        laço asm 8×ADDS        5 masked  PRIMASK=1 de CNT≥7900 até
 *   2 div        laço asm 8×UDIV lento            CNT≥200 do período seguinte
 *   3 ldm        laço asm 8×LDM(4)      6 wfi_nodbg  WFI com DBGMCU_CR.DBG_SLEEP
 *   4 wfi        __WFI() (DBGMCU como               limpo pelo firmware (sleep
 *                o debugger deixou)                 real, HCLK parado no HW)
 * Por condição: S2A_SAMPLES interrupções.
 *
 * Rows (trial = índice da amostra 0..63, condição):
 *   v0 = latência (TIM2->CNT na entrada), v1 = DWT na entrada,
 *   v2 = w.count na entrada (trabalho acumulado do laço de fundo),
 *   v3 = DBGMCU_CR durante a condição.
 * Trace: IRQ_A = 4 primeiras entradas por condição (arg = CNT);
 *        MAIN  = BEGIN/END por condição.
 */
#include "board.h"
#include "periph.h"
#include "fidelity.h"

#define S2A_SEED      0x5EED0021U
#define S2A_SAMPLES   64U
#define S2A_ARR       7999U
#define S2A_MASK_FROM 7900U
#define S2A_MASK_TO   200U
#define S2A_CONDS     6U

typedef struct {
    volatile uint32_t count;
    volatile uint32_t stop;
    uint32_t data[6];
} S2Work;

void s2_spin_alu(S2Work *w);
void s2_spin_div(S2Work *w);
void s2_spin_ldm(S2Work *w);
void TIM2_IRQHandler(void);

static S2Work s_w __attribute__((aligned(8)));
static volatile uint32_t s_n;
static volatile uint32_t s_cond;
static uint32_t s_lat[S2A_SAMPLES];
static uint32_t s_at[S2A_SAMPLES];
static uint32_t s_work[S2A_SAMPLES];

void TIM2_IRQHandler(void)
{
    uint32_t cnt = TIM2->CNT;            /* 1º acesso: latência */
    uint32_t now = fidelity_now();
    TIM2->SR = 0U;                       /* limpa UIF cedo (rc_w0) */
    uint32_t n = s_n;
    if (n < S2A_SAMPLES) {
        s_lat[n] = cnt;
        s_at[n] = now;
        s_work[n] = s_w.count;
        if (n < 4U) {
            fidelity_trace_at(FIDELITY_IRQ_A, now, FIDELITY_EV_BEGIN, s_cond, cnt);
        }
    }
    s_n = n + 1U;
    if (n + 1U >= S2A_SAMPLES) {
        s_w.stop = 1U;
    }
}

static void masked_loop(void)
{
    while (s_w.stop == 0U) {
        while (TIM2->CNT < S2A_MASK_FROM) {
            if (s_w.stop != 0U) {
                return;
            }
        }
        __disable_irq();
        /* Atravessa o update (CNT volta a 0) e segura até CNT ≥ 200. */
        while (TIM2->CNT >= S2A_MASK_FROM || TIM2->CNT < S2A_MASK_TO) {
        }
        __enable_irq();
    }
}

static void run_condition(uint32_t cond)
{
    s_cond = cond;
    s_n = 0U;
    s_w.count = 0U;
    s_w.stop = 0U;

    uint32_t dbg_saved = DBGMCU->CR;
    if (cond == 6U) {
        DBGMCU->CR = dbg_saved & ~DBGMCU_CR_DBG_SLEEP;
    }
    uint32_t dbg_now = DBGMCU->CR;

    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->CNT = 0U;
    TIM2->SR = 0U;
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    TIM2->DIER = TIM_DIER_UIE;
    NVIC_EnableIRQ(TIM2_IRQn);
    fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_BEGIN, cond, 0U);
    TIM2->CR1 |= TIM_CR1_CEN;

    switch (cond) {
    case 1U: s2_spin_alu(&s_w); break;
    case 2U: s2_spin_div(&s_w); break;
    case 3U: s2_spin_ldm(&s_w); break;
    case 5U: masked_loop(); break;
    default:
        while (s_w.stop == 0U) {
            __WFI();
        }
        break;
    }

    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->DIER = 0U;
    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    TIM2->SR = 0U;
    DBGMCU->CR = dbg_saved;
    fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_END, cond, s_n);

    for (uint32_t i = 0U; i < S2A_SAMPLES; ++i) {
        fidelity_row(i, cond, s_lat[i], s_at[i], s_work[i], dbg_now, 0U, 0U);
    }
}

int main(void)
{
    board_init();
    fidelity_init(2U, 1U, S2A_SEED);

    s_w.data[0] = 0xFFFFFFFFU;           /* UDIV lento: dividendo */
    s_w.data[1] = 3U;                    /*             divisor   */
    for (uint32_t i = 2U; i < 6U; ++i) {
        s_w.data[i] = S2A_SEED + i;
    }

    /* TIM2: clock, PSC=0 carregado via UG (PSC é bufferizado no HW), ARR. */
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    TIM2->CR1 = 0U;
    TIM2->PSC = 0U;
    TIM2->ARR = S2A_ARR;
    TIM2->EGR = TIM_EGR_UG;
    TIM2->SR = 0U;
    NVIC_SetPriority(TIM2_IRQn, 4U);

    for (uint32_t cond = 1U; cond <= S2A_CONDS; ++cond) {
        run_condition(cond);
    }
    fidelity_finish();
}
