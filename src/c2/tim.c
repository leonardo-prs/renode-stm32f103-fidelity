/*
 * src/c2/tim.c — C2, etapa 4: o timer como fonte (04-c2.typ).
 *
 * TIM2 e TIM3 com o evento de atualização (UIF) pedindo a interrupção
 * (RM0008 §15.3.1). O tratador limpa a flag como primeira escrita (gancho de
 * escrita em TIMx_SR) e anota o atendimento. Relógio fixo: HSI 8 MHz,
 * prescalers de AHB/APB em 1 (RCC_CFGR = 0), timers a 8 MHz.
 *
 *  10  C2-10  período do TIM2             3 pares (PSC, ARR) de produto 1000, 10 períodos cada
 *  11  C2-11  empate TIM2 × TIM3           partidas pelo monitor com defasagem d; 5 rodadas
 *  12  C2-12  coalescência                 TIM2 de período 200, PRIMASK por D = 0..800 ticks
 */
#include "c2.h"

#define EXC_TIM2 (16U + (uint32_t)TIM2_IRQn)
#define EXC_TIM3 (16U + (uint32_t)TIM3_IRQn)
#define PRIO     8U

static const uint16_t PARES_10[3][2] = {{0U, 999U}, {9U, 99U}, {99U, 9U}};
#define N_10      11U                   /* atendimentos por par: o 1º e 10 em regime */
#define RODADAS_11 5U
#define ARR_11    999U
#define ARR_12    199U
#define D_MAX_12  800U

__attribute__((noipa)) void c2_mascara(void);
__attribute__((noipa)) void c2_libera(void);

void c2_irq(void)
{
    uint32_t exc = __get_IPSR() & 0x1FFU;
    if (exc == EXC_TIM2) {
        TIM2->SR = ~TIM_SR_UIF;
    } else if (exc == EXC_TIM3) {
        TIM3->SR = ~TIM_SR_UIF;
    }
    (void)c2_anota();
}

/* Instruções que mudam a máscara; os ganchos ficam nos seus endereços. */
void c2_mascara(void)
{
    __disable_irq();
}

void c2_libera(void)
{
    __enable_irq();
}

/* Estado inicial fixado: parado, contagem ascendente, PSC e ARR carregados
 * por UG, flag e pendência limpas, interrupção de atualização habilitada,
 * pré-carga do ARR ligada. A partida (CEN) fica para quem chama. */
static void prepara_tim(TIM_TypeDef *t, IRQn_Type irq, uint32_t psc, uint32_t arr)
{
    t->CR1 = 0U;
    t->DIER = 0U;
    t->PSC = psc;
    t->ARR = arr;
    t->CNT = 0U;
    t->EGR = TIM_EGR_UG;
    t->SR = 0U;
    NVIC_ClearPendingIRQ(irq);
    NVIC_SetPriority(irq, PRIO);
    t->DIER = TIM_DIER_UIE;
    t->CR1 = TIM_CR1_ARPE;
    c2_barreira();
}

static void para_tim(TIM_TypeDef *t, IRQn_Type irq)
{
    t->CR1 = TIM_CR1_ARPE;
    t->DIER = 0U;
    t->SR = 0U;
    NVIC_DisableIRQ(irq);
    NVIC_ClearPendingIRQ(irq);
    c2_barreira();
}

/* ── C2-10 ── por par: atendimentos (N_10). Os instantes vêm dos ganchos
 * (escrita da partida em TIM2_CR1, entradas em c2_irq). */
static void caso_10(void)
{
    for (uint32_t k = 0U; k < 3U; k++) {
        prepara_tim(TIM2, TIM2_IRQn, PARES_10[k][0], PARES_10[k][1]);
        NVIC_EnableIRQ(TIM2_IRQn);
        uint32_t n0 = c2_vezes[EXC_TIM2];
        TIM2->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
        while (c2_vezes[EXC_TIM2] < n0 + N_10) {
        }
        para_tim(TIM2, TIM2_IRQn);
        c2_grava(c2_vezes[EXC_TIM2] - n0);
    }
}

/* ── C2-11 ── o monitor liga os dois contadores (CEN) com a defasagem da
 * rodada; o firmware espera o 1º atendimento de cada um e grava a ordem
 * (prioridades iguais: nenhum preempta o outro, o registro vale). */
static void caso_11(void)
{
    for (uint32_t r = 0U; r < RODADAS_11; r++) {
        prepara_tim(TIM2, TIM2_IRQn, 0U, ARR_11);
        prepara_tim(TIM3, TIM3_IRQn, 0U, ARR_11);
        NVIC_EnableIRQ(TIM2_IRQn);
        NVIC_EnableIRQ(TIM3_IRQn);
        c2_barreira();
        uint32_t n0 = c2_nlog;
        c2_pronto = r + 1U;
        while (c2_vezes[EXC_TIM2] <= r || c2_vezes[EXC_TIM3] <= r) {
        }
        para_tim(TIM2, TIM2_IRQn);
        para_tim(TIM3, TIM3_IRQn);
        c2_grava(c2_atendido(n0) | (c2_atendido(n0 + 1U) << 16));
    }
}

/* ── C2-12 ── TIM2 periódico; por ponto d: sincroniza numa entrada, mascara
 * (PRIMASK) até o DWT_CYCCNT avançar d ticks, libera e espera 3 entradas.
 * Registro: atendimentos desde a sincronização. */
static void caso_12(void)
{
    prepara_tim(TIM2, TIM2_IRQn, 0U, ARR_12);
    NVIC_EnableIRQ(TIM2_IRQn);
    TIM2->CR1 = TIM_CR1_ARPE | TIM_CR1_CEN;
    while (c2_vezes[EXC_TIM2] < 3U) {
    }
    for (uint32_t d = 0U; d <= D_MAX_12; d++) {
        uint32_t n0 = c2_vezes[EXC_TIM2];
        while (c2_vezes[EXC_TIM2] == n0) {
        }
        uint32_t t0 = DWT->CYCCNT;
        c2_mascara();
        while (DWT->CYCCNT - t0 < d) {
        }
        c2_libera();
        uint32_t n1 = c2_vezes[EXC_TIM2];
        while (c2_vezes[EXC_TIM2] < n1 + 3U) {
        }
        c2_grava(c2_vezes[EXC_TIM2] - n0);
    }
    para_tim(TIM2, TIM2_IRQn);
}

int main(void)
{
    c2_init();
    RCC->CFGR = 0U;                                     /* HSI, AHB/APB1/APB2 ÷ 1 */
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN | RCC_APB1ENR_TIM3EN;
    switch (c2_caso) {
    case 10U: caso_10(); break;
    case 11U: caso_11(); break;
    case 12U: caso_12(); break;
    default: c2_falha();
    }
    c2_encerra();
}
