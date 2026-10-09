/**
 * @file    src/c2/timers.c
 * @brief   C2 — contagem, update, flags e IRQ de TIM2, TIM3 (APB1) e TIM1 (APB2).
 *
 * Pergunta: o Renode reproduz a contagem, a periodicidade, as flags e o
 * atendimento da IRQ provocada pelo timer, inclusive quando o prescaler do
 * barramento APB muda a frequência do timer?
 *
 * Cada caso usa UM timer por vez (sem arbitragem entre IRQs: isso é do C3)
 * e reinicializa todos os registradores que usa. O evento de update é
 * assíncrono ao fluxo de MAIN, mas determinístico pela configuração.
 *
 * Árvore de clock (RM0008 §7.2, Figura 8): TIMxCLK = PCLKx se o prescaler
 * APBx = 1; senão TIMxCLK = 2 × PCLKx. Com HCLK = 8 MHz:
 *   perfil /1 → PCLK 8 MHz, TIMCLK 8 MHz
 *   perfil /2 → PCLK 4 MHz, TIMCLK 8 MHz   (regra do ×2)
 *   perfil /4 → PCLK 2 MHz, TIMCLK 4 MHz
 * O perfil é aplicado aos dois barramentos (APB1 e APB2) ao mesmo tempo e
 * RCC->CFGR lido de volta é registrado em cada caso.
 *
 * Observação temporal: CNT lido como PRIMEIRA instrução útil da ISR (antes
 * do logger); com PSC = 0 cada contagem é um período de TIMCLK desde o
 * update. Timestamps de MAIN vêm de polling: resolução = uma volta do laço.
 *
 * PA9/PA10 (loopback da bancada) e as saídas de canal de TIM1 não são
 * tocados: CCER fica em 0 e nenhum GPIO é configurado.
 */
#include "board.h"
#include "fidelity.h"

#define FIRMWARE_ID 0x0201U

/* Eventos do C2 (anel do handler de cada timer). */
#define EV_ISR_ENTRY 0x200U      /* arg = CNT lido na entrada da ISR */

enum C2Kind {
    K_COUNT_OFF = 1,      /* CEN = 0: CNT não anda */
    K_COUNT_RATE,         /* ΔCNT / ΔDWT por perfil APB */
    K_UPDATE_POLL,        /* período entre updates (UIF por polling) */
    K_PSC_PRELOAD,        /* PSC escrito no meio do período */
    K_ARR_PRELOAD_OFF,    /* ARR escrito com ARPE = 0 */
    K_ARR_PRELOAD_ON,     /* ARR escrito com ARPE = 1 */
    K_UG_URS0,            /* UG com URS = 0 */
    K_UG_URS1,            /* UG com URS = 1 */
    K_UIF_PENDING,        /* UIF × UIE × linha × pending do NVIC */
    K_IRQ_IDLE,           /* IRQ periódica, MAIN em espera ativa */
    K_IRQ_LOAD,           /* IRQ periódica, MAIN executando carga C */
    K_IRQ_DELAYED,        /* NVIC habilitado 2000 ticks após o update */
    K_IRQ_COALESCED       /* NVIC habilitado 2,5 períodos após o update */
};

typedef struct {
    TIM_TypeDef *tim;
    IRQn_Type irq;
    uint32_t writer;      /* anel do handler deste timer */
} Timer;

enum { T_TIM2 = 0, T_TIM3 = 1, T_TIM1 = 2, TIMER_COUNT = 3 };

static const Timer TIMERS[TIMER_COUNT] = {
    [T_TIM2] = {TIM2, TIM2_IRQn, FID_IRQ1},
    [T_TIM3] = {TIM3, TIM3_IRQn, FID_IRQ2},
    [T_TIM1] = {TIM1, TIM1_UP_IRQn, FID_IRQ3},
};

/* Perfis APB (índice gravado no caso). */
static const uint32_t APB1_DIV[3] = {LL_RCC_APB1_DIV_1, LL_RCC_APB1_DIV_2, LL_RCC_APB1_DIV_4};
static const uint32_t APB2_DIV[3] = {LL_RCC_APB2_DIV_1, LL_RCC_APB2_DIV_2, LL_RCC_APB2_DIV_4};

#define N_PERIODS        8U        /* updates observados por polling */
#define N_IRQS           16U       /* entradas de ISR nos casos periódicos */
#define RATE_WINDOW      24000U    /* ticks de DWT entre as leituras de CNT */
#define IRQ_DELAY        2000U
#define IRQ_COALESCE     20000U    /* 2,5 períodos de 8000 ticks */
#define WAIT_LIMIT       200000U   /* teto de qualquer espera (25 ms) */

/* Contador de entradas: cada elemento só é escrito pela ISR do seu timer.
 * MAIN só o zera com a IRQ desligada (UIE = 0 e NVIC desabilitado). */
static volatile uint32_t s_entries[TIMER_COUNT];
static volatile uint32_t s_sink;

/* ───────────────────────────── handlers ───────────────────────────── */

static void timer_isr(uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    uint32_t cnt = tim->CNT;                  /* primeiro ponto observado */
    fid_log(TIMERS[t].writer, EV_ISR_ENTRY, cnt);
    tim->SR = ~TIM_SR_UIF;                    /* rc_w0: zera só UIF */
    (void)tim->SR;                            /* garante a escrita antes do retorno */
    s_entries[t] = s_entries[t] + 1U;
}

void TIM2_IRQHandler(void);
void TIM3_IRQHandler(void);
void TIM1_UP_IRQHandler(void);

void TIM2_IRQHandler(void) { timer_isr(T_TIM2); }
void TIM3_IRQHandler(void) { timer_isr(T_TIM3); }
void TIM1_UP_IRQHandler(void) { timer_isr(T_TIM1); }

/* ───────────────────────────── utilidades ───────────────────────────── */

static void timer_quiesce(uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    tim->CR1 = 0U;
    tim->DIER = 0U;
    NVIC_DisableIRQ(TIMERS[t].irq);
    tim->PSC = 0U;
    tim->ARR = 0xFFFFU;
    tim->CNT = 0U;
    tim->SR = 0U;
    NVIC_ClearPendingIRQ(TIMERS[t].irq);
    s_entries[t] = 0U;
}

/* PSC/ARR carregados no registrador ativo via UG (URS = 0 → UIF = 1),
 * depois UIF limpo: o timer começa do zero, parado. */
static void timer_setup(uint32_t t, uint32_t psc, uint32_t arr)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    timer_quiesce(t);
    tim->PSC = psc;
    tim->ARR = arr;
    tim->EGR = TIM_EGR_UG;
    tim->SR = 0U;
    NVIC_ClearPendingIRQ(TIMERS[t].irq);
}

/* Espera UIF = 1. Devolve 1 e o instante em *when; 0 em timeout. */
static uint32_t wait_uif(TIM_TypeDef *tim, uint32_t *when)
{
    uint32_t t0 = fid_now();
    while ((tim->SR & TIM_SR_UIF) == 0U) {
        if ((fid_now() - t0) > WAIT_LIMIT) {
            *when = 0U;
            return 0U;
        }
    }
    *when = fid_now();
    return 1U;
}

static uint32_t wait_cnt_at_least(TIM_TypeDef *tim, uint32_t value)
{
    uint32_t t0 = fid_now();
    while (tim->CNT < value) {
        if ((fid_now() - t0) > WAIT_LIMIT) {
            return 0U;
        }
    }
    return 1U;
}

static uint32_t wait_entries(uint32_t t, uint32_t target)
{
    uint32_t t0 = fid_now();
    while (s_entries[t] < target) {
        if ((fid_now() - t0) > WAIT_LIMIT) {
            return 0U;
        }
    }
    return 1U;
}

/* Abre o caso e grava o cabeçalho comum. */
static void begin(uint32_t kind, uint32_t t, uint32_t profile, uint32_t psc, uint32_t arr)
{
    uint32_t cfgr = board_set_apb(APB1_DIV[profile], APB2_DIV[profile]);
    fid_case_begin((kind << 8) | (t << 4) | profile);
    fid_put(kind);
    fid_put(t);
    fid_put(profile);
    fid_put(cfgr);
    fid_put(psc);
    fid_put(arr);
}

static void end(uint32_t t, uint32_t ok)
{
    timer_quiesce(t);
    board_set_apb(LL_RCC_APB1_DIV_1, LL_RCC_APB2_DIV_1);
    fid_case_end(ok ? FID_CASE_OK : FID_CASE_TIMEOUT);
}

/* ───────────────────────── contagem e update ───────────────────────── */

static void case_count_off(uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    timer_setup(t, 0U, 0xFFFFU);
    begin(K_COUNT_OFF, t, 0U, 0U, 0xFFFFU);
    uint32_t c0 = tim->CNT;
    fid_delay(8000U);
    uint32_t c1 = tim->CNT;
    fid_put(c0);
    fid_put(c1);
    fid_put(tim->SR);
    end(t, 1U);
}

static void case_count_rate(uint32_t t, uint32_t profile)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    timer_setup(t, 0U, 0xFFFFU);
    begin(K_COUNT_RATE, t, profile, 0U, 0xFFFFU);
    tim->CR1 = TIM_CR1_CEN;
    fid_delay(100U);
    uint32_t t0 = fid_now();
    uint32_t c0 = tim->CNT;
    fid_delay(RATE_WINDOW);
    uint32_t t1 = fid_now();
    uint32_t c1 = tim->CNT;
    fid_put(t0);
    fid_put(c0);
    fid_put(t1);
    fid_put(c1);
    fid_put(tim->SR);
    end(t, 1U);
}

/* PSC = 7, ARR = 999: período previsto 8000 / (TIMCLK/HCLK) ticks. */
static void case_update_poll(uint32_t t, uint32_t profile)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    uint32_t ok = 1U;
    timer_setup(t, 7U, 999U);
    begin(K_UPDATE_POLL, t, profile, 7U, 999U);
    tim->CR1 = TIM_CR1_CEN;
    fid_put(fid_now());                       /* instante do CEN */
    for (uint32_t k = 0U; k < N_PERIODS; ++k) {
        uint32_t when;
        ok &= wait_uif(tim, &when);
        tim->SR = ~TIM_SR_UIF;
        fid_put(when);
    }
    end(t, ok);
}

/*
 * Escreve um novo PSC ou ARR quando CNT >= 500 e registra os dois updates
 * seguintes. RM0008 §15.3.1/§15.4: PSC é sempre bufferizado (vale a partir
 * do próximo update); ARR é bufferizado só com ARPE = 1.
 */
static void case_preload(uint32_t kind, uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    uint32_t ok = 1U;
    uint32_t u1;
    uint32_t u2;
    timer_setup(t, 7U, 999U);
    begin(kind, t, 0U, 7U, 999U);
    if (kind == K_ARR_PRELOAD_ON) {
        tim->CR1 = TIM_CR1_ARPE;
    }
    tim->CR1 |= TIM_CR1_CEN;
    ok &= wait_cnt_at_least(tim, 500U);
    uint32_t cnt_w = tim->CNT;
    uint32_t t_w = fid_now();
    if (kind == K_PSC_PRELOAD) {
        tim->PSC = 15U;
    } else {
        tim->ARR = 699U;
    }
    ok &= wait_uif(tim, &u1);
    tim->SR = ~TIM_SR_UIF;
    ok &= wait_uif(tim, &u2);
    tim->SR = ~TIM_SR_UIF;
    fid_put(cnt_w);
    fid_put(t_w);
    fid_put(u1);
    fid_put(u2);
    end(t, ok);
}

/* UG com o contador andando (CNT >= 500), UIE = 0. RM0008 §15.4.1/§15.4.5:
 * UG zera CNT e o contador do prescaler; com URS = 0 o UG seta UIF. */
static void case_ug(uint32_t kind, uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    timer_setup(t, 7U, 999U);
    begin(kind, t, 0U, 7U, 999U);
    tim->CR1 = (kind == K_UG_URS1) ? (TIM_CR1_URS | TIM_CR1_CEN) : TIM_CR1_CEN;
    uint32_t ok = wait_cnt_at_least(tim, 500U);
    tim->SR = 0U;
    uint32_t cnt_before = tim->CNT;
    tim->EGR = TIM_EGR_UG;
    uint32_t cnt_after = tim->CNT;
    uint32_t sr_after = tim->SR;
    fid_put(cnt_before);
    fid_put(cnt_after);
    fid_put(sr_after);
    end(t, ok);
}

/*
 * Distingue evento (UIF), linha de IRQ (UIF & UIE) e pending do NVIC, com a
 * IRQ DESABILITADA no NVIC (nunca é atendida neste caso). PM0056 §4.3:
 * o pending fica registrado mesmo que a linha caia depois; só some por
 * entrada no handler ou escrita em ICPR.
 */
static void case_uif_pending(uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    IRQn_Type irq = TIMERS[t].irq;
    timer_setup(t, 7U, 999U);
    begin(K_UIF_PENDING, t, 0U, 7U, 999U);
    tim->CR1 = TIM_CR1_CEN;
    uint32_t when;
    uint32_t ok = wait_uif(tim, &when);
    tim->CR1 = 0U;                                  /* congela: sem novos updates */
    uint32_t uif0 = tim->SR & TIM_SR_UIF;
    uint32_t pend0 = NVIC_GetPendingIRQ(irq);       /* UIE = 0: linha baixa */
    tim->DIER = TIM_DIER_UIE;
    (void)tim->DIER;
    __DSB();
    uint32_t pend1 = NVIC_GetPendingIRQ(irq);       /* linha alta → pending */
    tim->SR = ~TIM_SR_UIF;
    (void)tim->SR;
    __DSB();
    uint32_t uif1 = tim->SR & TIM_SR_UIF;
    uint32_t pend2 = NVIC_GetPendingIRQ(irq);       /* linha caiu; pending fica? */
    NVIC_ClearPendingIRQ(irq);
    __DSB();
    uint32_t pend3 = NVIC_GetPendingIRQ(irq);
    fid_put(uif0);
    fid_put(pend0);
    fid_put(pend1);
    fid_put(uif1);
    fid_put(pend2);
    fid_put(pend3);
    end(t, ok);
}

/* ───────────────────────────── IRQ ───────────────────────────── */

static void irq_start(uint32_t t)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    NVIC_SetPriority(TIMERS[t].irq, 8U);
    tim->DIER = TIM_DIER_UIE;
    NVIC_EnableIRQ(TIMERS[t].irq);
    tim->CR1 = TIM_CR1_CEN;
}

/* Carga de MAIN enquanto a IRQ periódica acontece: MUL, UDIV e store. */
static uint32_t busy_load(uint32_t x)
{
    for (uint32_t i = 0U; i < 16U; ++i) {
        x = x * 1664525U + 1013904223U;
        x ^= x / 7U;
        s_sink = x;
    }
    return x;
}

/* PSC = 0, ARR = 7999: período de 8000 contagens de TIMCLK. */
static void case_irq_periodic(uint32_t kind, uint32_t t, uint32_t profile)
{
    timer_setup(t, 0U, 7999U);
    begin(kind, t, profile, 0U, 7999U);
    uint32_t ok = 1U;
    uint32_t t_start = fid_now();
    irq_start(t);
    if (kind == K_IRQ_IDLE) {
        ok = wait_entries(t, N_IRQS);
    } else {
        uint32_t x = 1U;
        while (s_entries[t] < N_IRQS) {
            x = busy_load(x);
            if ((fid_now() - t_start) > WAIT_LIMIT) {
                ok = 0U;
                break;
            }
        }
    }
    TIMERS[t].tim->CR1 = 0U;
    TIMERS[t].tim->DIER = 0U;
    fid_put(t_start);
    fid_put(s_entries[t]);
    end(t, ok);
}

/*
 * Separa o evento do atendimento: UIE = 1 mas a IRQ fica desabilitada no
 * NVIC; MAIN observa UIF (instante t_seen), espera `delay` ticks e só então
 * habilita a IRQ. Com delay maior que um período, outros updates acontecem
 * com UIF já em 1: a ISR deve rodar uma vez só (eventos coalescidos). O
 * número de updates no intervalo é INFERIDO da configuração, não observado.
 */
static void case_irq_delayed(uint32_t kind, uint32_t t, uint32_t delay)
{
    TIM_TypeDef *tim = TIMERS[t].tim;
    timer_setup(t, 0U, 7999U);
    begin(kind, t, 0U, 0U, 7999U);
    NVIC_SetPriority(TIMERS[t].irq, 8U);
    tim->DIER = TIM_DIER_UIE;
    tim->CR1 = TIM_CR1_CEN;
    uint32_t t_seen;
    uint32_t ok = wait_uif(tim, &t_seen);
    uint32_t cnt_seen = tim->CNT;
    fid_delay(delay);
    uint32_t t_enable = fid_now();
    NVIC_EnableIRQ(TIMERS[t].irq);
    ok &= wait_entries(t, 1U);
    tim->CR1 = 0U;                         /* para antes do próximo update */
    tim->DIER = 0U;
    fid_put(delay);
    fid_put(t_seen);
    fid_put(cnt_seen);
    fid_put(t_enable);
    fid_put(s_entries[t]);
    end(t, ok);
}

/* ───────────────────────────── main ───────────────────────────── */

#define CASE_COUNT 49U

int main(void)
{
    board_init();
    fid_init(FIRMWARE_ID, CASE_COUNT);

    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN | RCC_APB1ENR_TIM3EN;
    RCC->APB2ENR |= RCC_APB2ENR_TIM1EN;
    (void)RCC->APB2ENR;
    NVIC_SetPriorityGrouping(0U);

    for (uint32_t t = 0U; t < TIMER_COUNT; ++t) {
        case_count_off(t);
    }
    for (uint32_t t = 0U; t < TIMER_COUNT; ++t) {
        for (uint32_t p = 0U; p < 3U; ++p) {
            case_count_rate(t, p);
        }
    }
    for (uint32_t t = 0U; t < TIMER_COUNT; ++t) {
        case_update_poll(t, 0U);
    }
    case_update_poll(T_TIM2, 2U);
    case_update_poll(T_TIM1, 2U);
    for (uint32_t t = 0U; t < TIMER_COUNT; ++t) {
        case_preload(K_PSC_PRELOAD, t);
        case_preload(K_ARR_PRELOAD_OFF, t);
        case_preload(K_ARR_PRELOAD_ON, t);
        case_ug(K_UG_URS0, t);
        case_ug(K_UG_URS1, t);
        case_uif_pending(t);
    }
    for (uint32_t t = 0U; t < TIMER_COUNT; ++t) {
        case_irq_periodic(K_IRQ_IDLE, t, 0U);
    }
    case_irq_periodic(K_IRQ_IDLE, T_TIM2, 1U);
    case_irq_periodic(K_IRQ_IDLE, T_TIM2, 2U);
    for (uint32_t t = 0U; t < TIMER_COUNT; ++t) {
        case_irq_periodic(K_IRQ_LOAD, t, 0U);
        case_irq_delayed(K_IRQ_DELAYED, t, IRQ_DELAY);
        case_irq_delayed(K_IRQ_COALESCED, t, IRQ_COALESCE);
    }

    fid_finish();
}
