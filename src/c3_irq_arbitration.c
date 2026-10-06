/**
 * @file    src/c3_irq_arbitration.c
 * @brief   C3 — NVIC arbitration: TIM2 (HIGH) x TIM3 (LOW), STM32F103C8T6.
 *
 * Executavel build/c3/firmware.elf. Entry `main()`; hooks `c3_tim2_hook()` /
 * `c3_tim3_hook()` chamados de TIM2_IRQHandler / TIM3_IRQHandler (definidos
 * neste arquivo, 1a instrucao do handler).
 *
 * Perifericos ligados: SOMENTE TIM2 e TIM3 (+ DWT). NVIC: TIM2_IRQn e
 * TIM3_IRQn. Nenhuma USART, SysTick no estado de reset (off).
 *
 * Stack: HSI 8 MHz (reset state, sem HSE/PLL). Ambos os timers a 1 kHz
 * (PSC=7, ARR=999 -> periodo 1000 ticks x 8 ciclos = 8000 ciclos CPU).
 * LL apenas; sem HAL, sem printf. Dados saem via GDB dump de `c3_results`.
 *
 * Prioridades NVIC (congeladas no .ioc, preservada a ordem TIM2 > TIM3):
 *   TIM2_IRQn = 28, prioridade logica 2 (HIGH);
 *   TIM3_IRQn = 29, prioridade logica 12 (LOW).
 * NOTA: sao 2/12 (valores logicos). Rascunhos antigos citavam 0/192, que sao
 * os valores brutos do campo de prioridade (0x20/0xC0 com 4 bits
 * implementados, PRIORITYGROUP_4) — nao usar como prioridade logica.
 * Em empate de prioridade vale o menor exception number (ARMv7-M B1.5.4):
 * TIM2 (28) vence TIM3 (29) — ver fase E.
 *
 * Formato de amostra: pares (cyc, meta) em `c3_results` (2048 words = 1024
 * pares). meta = ((uint32_t)id << 16) | (__get_IPSR() & 0x1FFu). O timestamp
 * DWT->CYCCNT e lido ANTES do IPSR em `record()`. `c3_n` = words validas
 * (= g_w*2). `c3_done`: 1 = ok, 0xFD = timeout (park), 0xFE = sem CYCCNT.
 *
 * Ids de fase (campo id da meta; ordem + IPSR distinguem o timer):
 *   1 = baseline TIM3-alone | 2 = baseline TIM2-alone
 *   3 = TIM3 no sweep | 4 = TIM2 no sweep
 *   5 = PRIMASK (raw + hooks) | 6 = BASEPRI (raw + hooks) | 7 = tie
 * Os hooks selecionam o id via g_id2/g_id3 (setados por fase); a troca
 * "sweep usa 3/4, resto usa o id da fase" e implementada por esses
 * seletores, nao por branch nos hooks.
 *
 * Tabela de fases:
 * | Fase | PH_*   | Config                                          | N        | Classe |
 * | A1   | PH_A_T3| TIM2 IRQ off, roda so TIM3, id1               | 64 (T3)  | B      |
 * | A2   | PH_A_T2| TIM3 IRQ off, roda so TIM2, id2               | 64 (T2)  | B      |
 * | B/C  | PH_SWEEP|sweep K: ambos rodam, TIM2 adiantado K ticks    | 16 T3 /K | B + C  |
 * |      |        | ids 3 (T3) / 4 (T2); TIM3 com burn C3_BURN_ITERS |          |        |
 * | D1   | PH_DPRI| PRIMASK: cpsid, poll pendente TIM2, raw, cpsi e  | 1 raw+1  | C      |
 * | D2   | PH_DBASE| BASEPRI=0x20: idem, id6                       | 1 raw+1  | C      |
 * | E    | PH_ETIE| tie prio TIM3=2 (= TIM2), CNT=0 ambos, id7      | 16 (T3)  | A      |
 *
 * Tabela K do sweep (offset em ticks do timer; 1 tick = PSC+1 = 8 ciclos):
 *   K   = {2, 4, 8, 16, 32, 48, 64, 96, 125}
 *   defasagem ~ {16, 32, 64, 128, 256, 384, 512, 768, 1000} ciclos CPU.
 * Por K: para ambos, ClearFlag ambos, ClearPending ambos,
 * CNT(TIM3)=0, CNT(TIM2)=1000-K (TIM2 lidera K ticks), g_t3cnt=0,
 * PH_SWEEP, liga ambos; espera g_t3cnt>=16; para ambos.
 *
 * Classes de fidelidade:
 *   (A) binario de ordem arquitetural — fase E (empate -> 28 vence 29) e
 *       ordem TIM2-antes-TIM3 no sweep;
 *   (B) quantitativo 12c/6c (Yiu, "Definitive Guide to Cortex-M3", cap. de
 *       excecoes; Coleman, medicoes de latencia/overhead) — deltas de
 *       entrada vs. 12 ciclos (stacking) / 6 ciclos (tail-chain);
 *   (C) late-arrival implementation-defined — sweep K + mascaramentos D1/D2.
 */

#include "board.h"
#include "periph.h"                  /* tim_1khz_init() */
#include "trace.h"                   /* trace_init()/trace_emit(): ISRs 0x20-0x23, fase 0x24 */

/* Trace overhead (documentado): cada trace_emit = 1 load (base do ring) +
 * escrita no ring buffer em SRAM, ~10-20 ciclos. O marker 0x20/0x22 precede
 * a amostra CYCCNT no hook por instrucoes — deslocamento constante, removido
 * offline na analise (pares CYCCNT/meta preservados). Mapeamento por nome do
 * ISR: TIM2 (HIGH, prio 2) = 0x20/0x21, TIM3 (LOW, prio 12) = 0x22/0x23;
 * prioridades, fases e K inalterados. */

/* ── Config ─────────────────────────────────────────────────────────────── */
#define C3_CAP_PAIRS    1024u        /* pares (cyc,meta) cabiveis em c3_results */
#define C3_BURN_ITERS   500u         /* burn no hook TIM3 so em PH_SWEEP: deve ficar
                                      * < 8000c do periodo; ~2-4kc @-O0, validado
                                      * pelo max-delta na analise */

/* Timeouts em ciclos CYCCNT (1 amostra 1kHz = 8000c; folga ~15-25x). */
#define C3_TMO_64       8000000u     /* 64 amostras = 512kc */
#define C3_TMO_16       2000000u     /* 16 amostras = 128kc */
#define C3_TMO_1        200000u      /* 1 entrada */
#define C3_TMO_PEND     200000u      /* overflow chega em <= 8000c apos start */

/* Fases (g_phase). */
#define PH_A_T3         1u
#define PH_A_T2         2u
#define PH_SWEEP        3u
#define PH_DPRI         4u
#define PH_DBASE        5u
#define PH_ETIE         6u

#define C3_NK           9u

/* ── Buffer de resultados (lido via GDB) ────────────────────────────────── */
volatile uint32_t c3_results[2048];
volatile uint32_t c3_n = 0u;
volatile uint8_t  c3_done = 0u;

/* ── Trace/arbitragem visiveis ao GDB (volatile: tocados por ISR e GDB) ─── */
volatile uint32_t c3_sp_tim2 = 0u; /* SP (MSP) capturado na entrada do ISR TIM2 */
volatile uint32_t c3_sp_tim3 = 0u; /* SP (MSP) capturado na entrada do ISR TIM3 */
volatile uint8_t  in_low = 0u;     /* 1 = ISR TIM3 (LOW) em curso */
volatile uint8_t  seen_high = 0u;  /* 1 = TIM2 entrou com in_low (preempcao vista) */

/* ── Estado file-static ─────────────────────────────────────────────────── */
static volatile uint32_t g_w;        /* indice de escrita em PARES (0..1024) */
static volatile uint8_t  g_phase;    /* fase corrente (PH_*) */
static volatile uint32_t g_need;     /* pares desejados nesta fase (alvo p/ g_w) */
static volatile uint32_t g_t3cnt;    /* entradas TIM3 nesta fase */
static volatile uint32_t g_tunmask;  /* CYCCNT do unmask (fase D) */
static volatile uint8_t  g_id2;      /* seletor de id do hook TIM2 (por fase) */
static volatile uint8_t  g_id3;      /* seletor de id do hook TIM3 (por fase) */

static const uint32_t C3_K_TICKS[C3_NK] = { 2u, 4u, 8u, 16u, 32u, 48u, 64u, 96u, 125u };

/* ── Prototipos (exigidos por -Wmissing-prototypes) ─────────────────────────
 * noinline nos hooks: antes viviam em outra TU (stm32f1xx_it.c chamava o
 * hook); mantem o mesmo caminho handler -> hook em qualquer nivel de -O. */
void c3_tim2_hook(void) __attribute__((noinline));
void c3_tim3_hook(void) __attribute__((noinline));
void TIM2_IRQHandler(void);
void TIM3_IRQHandler(void);

static void record(uint8_t id);
static void recordRaw(uint32_t cyc, uint8_t id);
static void parkTimeout(void);
static void waitCond(volatile uint32_t *p, uint32_t target, uint32_t timeout_cyc);
static void waitPendingTIM2(uint32_t timeout_cyc);

/* ── Helpers ────────────────────────────────────────────────────────────── */

/* Primeira coisa no ISR: timestamp e so depois IPSR (jitter minimo). */
static void record(uint8_t id)
{
    uint32_t cyc = DWT->CYCCNT;
    uint32_t ipsr = (uint32_t)__get_IPSR();
    uint32_t w = g_w;

    if (w < C3_CAP_PAIRS)
    {
        c3_results[w * 2u] = cyc;
        c3_results[w * 2u + 1u] = ((uint32_t)id << 16) | (ipsr & 0x1FFu);
        g_w = w + 1u;
    }
}

/* Amostra thread-mode (fase D): ipsr 0 por definicao. */
static void recordRaw(uint32_t cyc, uint8_t id)
{
    uint32_t w = g_w;

    if (w < C3_CAP_PAIRS)
    {
        c3_results[w * 2u] = cyc;
        c3_results[w * 2u + 1u] = ((uint32_t)id << 16);
        g_w = w + 1u;
    }
}

/* Park de timeout: done=0xFD, DSB, WFI para sempre. */
static void parkTimeout(void)
{
    c3_done = (uint8_t)0xFD;
    __DSB();
    for (;;)
    {
        __WFI();
    }
}

/* Espera *p >= target com deadline CYCCNT (comparacao unsigned = wrap-safe). */
static void waitCond(volatile uint32_t *p, uint32_t target, uint32_t timeout_cyc)
{
    uint32_t start = DWT->CYCCNT;

    while (*p < target)
    {
        if ((uint32_t)(DWT->CYCCNT - start) >= timeout_cyc)
        {
            parkTimeout();
        }
    }
}

/* Espera NVIC pendente de TIM2 com deadline CYCCNT (wrap-safe). */
static void waitPendingTIM2(uint32_t timeout_cyc)
{
    uint32_t start = DWT->CYCCNT;

    while (NVIC_GetPendingIRQ(TIM2_IRQn) == 0u)
    {
        if ((uint32_t)(DWT->CYCCNT - start) >= timeout_cyc)
        {
            parkTimeout();
        }
    }
}

/* ── IRQ handlers (sobrescrevem os aliases weak do startup) ─────────────── */

void TIM2_IRQHandler(void)
{
    trace_emit(0x20U);                /* ISR enter (primeira instrucao) */
    c3_sp_tim2 = __get_MSP();         /* captura SP na entrada */
    if (in_low != 0u)
    {
        seen_high = 1u;               /* HIGH entrou com LOW ativo: preempcao */
    }
    c3_tim2_hook();
    trace_emit(0x21U);                /* ISR exit (ultima antes do return) */
}

void TIM3_IRQHandler(void)
{
    trace_emit(0x22U);                /* ISR enter (primeira instrucao) */
    c3_sp_tim3 = __get_MSP();         /* captura SP na entrada */
    in_low = 1u;                      /* LOW ativo */
    c3_tim3_hook();
    in_low = 0u;                      /* LOW concluido (antes do exit) */
    trace_emit(0x23U);                /* ISR exit (ultima antes do return) */
}

/* ── Hooks (chamados dos handlers acima, 1a instrucao do handler) ──────── */

void c3_tim2_hook(void)
{
    record(g_id2);
    LL_TIM_ClearFlag_UPDATE(TIM2);
}

void c3_tim3_hook(void)
{
    record(g_id3);
    LL_TIM_ClearFlag_UPDATE(TIM3);
    g_t3cnt++;
    if (g_phase == PH_SWEEP)
    {
        for (volatile uint32_t b = 0u; b < C3_BURN_ITERS; ++b)
        {
            __NOP();
        }
    }
}

/* ── Entry (nao retorna) ────────────────────────────────────────────────── */

int main(void)
{
    uint32_t ki;

    board_init();
    trace_init();                       /* ring de trace antes de qualquer emit */

    /* Unicos perifericos deste cenario: TIM2 e TIM3 @1 kHz. Prioridades e
     * habilitacao no NVIC sao feitas abaixo (mesma sequencia de antes). */
    tim_1khz_init(TIM2);
    tim_1khz_init(TIM3);

    /* SysTick off (defensivo; estado de reset): jitter fora do protocolo. */
    SysTick->CTRL = 0u;

    /* DWT CYCCNT como base de tempo (NOCYCCNT -> park 0xFE). */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    if ((DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk) != 0u)
    {
        c3_done = (uint8_t)0xFE;
        __DSB();
        for (;;)
        {
            __WFI();
        }
    }
    DWT->CYCCNT = 0u;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    /* Estado inicial + prioridades congeladas do .ioc (2 = HIGH, 12 = LOW). */
    g_w = 0u;
    g_phase = 0u;
    g_need = 0u;
    g_t3cnt = 0u;
    g_tunmask = 0u;
    g_id2 = 2u;
    g_id3 = 1u;
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    /* PRIGROUP 4.0 (só grupo preempta): 4 bits de grupo, 0 de subprioridade —
     * subprioridade só ordena pendências, nunca preempta (PM0056, SCB_AIRCR).
     * Garante que TIM2 (prio 2) preempta TIM3 (prio 12) por grupo. */
    NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4);
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_SetPriority(TIM3_IRQn, 12);
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(TIM3_IRQn);
    LL_TIM_EnableIT_UPDATE(TIM2);    /* tim_1khz_init nao liga DIER.UIE */
    LL_TIM_EnableIT_UPDATE(TIM3);

    /* ── Fase A1: baseline TIM3-alone, 64 amostras, id1 ── */
    g_phase = PH_A_T3;
    g_id3 = 1u;
    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(TIM3_IRQn);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    LL_TIM_SetCounter(TIM2, 0u);
    LL_TIM_SetCounter(TIM3, 0u);
    g_t3cnt = 0u;
    g_need = g_w + 64u;
    LL_TIM_EnableCounter(TIM3);
    waitCond(&g_t3cnt, 64u, C3_TMO_64);
    LL_TIM_DisableCounter(TIM3);

    /* ── Fase A2: baseline TIM2-alone, 64 amostras, id2 (espelho) ──
     * Sem contador dedicado de TIM2 no contrato: espera por g_w/g_need;
     * com o IRQ de TIM3 desligado, todo par novo e TIM2. */
    g_phase = PH_A_T2;
    g_id2 = 2u;
    NVIC_DisableIRQ(TIM3_IRQn);
    NVIC_EnableIRQ(TIM2_IRQn);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    LL_TIM_SetCounter(TIM2, 0u);
    LL_TIM_SetCounter(TIM3, 0u);
    g_t3cnt = 0u;
    g_need = g_w + 64u;
    LL_TIM_EnableCounter(TIM2);
    waitCond(&g_w, g_need, C3_TMO_64);
    LL_TIM_DisableCounter(TIM2);

    /* Reabilita ambos para o sweep. */
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(TIM3_IRQn);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);

    /* ── Fases B/C: sweep de offsets; TIM2 lidera K ticks (~K*8 ciclos) ── */
    g_id2 = 4u;
    g_id3 = 3u;
    for (ki = 0u; ki < C3_NK; ++ki)
    {
        uint32_t k = C3_K_TICKS[ki];

        LL_TIM_DisableCounter(TIM2);
        LL_TIM_DisableCounter(TIM3);
        LL_TIM_ClearFlag_UPDATE(TIM2);
        LL_TIM_ClearFlag_UPDATE(TIM3);
        NVIC_ClearPendingIRQ(TIM2_IRQn);
        NVIC_ClearPendingIRQ(TIM3_IRQn);
        LL_TIM_SetCounter(TIM3, 0u);
        LL_TIM_SetCounter(TIM2, (uint32_t)(1000u - k));
        g_t3cnt = 0u;
        g_phase = PH_SWEEP;
        trace_emit(0x24U);             /* mark: mudanca de fase do sweep (K) */
        g_need = g_w + 32u;          /* informativo: ~16 pares por timer */
        LL_TIM_EnableCounter(TIM2);
        LL_TIM_EnableCounter(TIM3);
        waitCond(&g_t3cnt, 16u, C3_TMO_16);
        LL_TIM_DisableCounter(TIM2);
        LL_TIM_DisableCounter(TIM3);
    }

    /* ── Fase D1: mascaramento PRIMASK, id5 ──
     * Para, zera CNT, cpsid, liga ambos, espera pendente de TIM2, marca
     * t_unmask via raw, cpsie e espera 1 entrada TIM2 (pendente de maior
     * prioridade entra primeiro). */
    g_phase = PH_DPRI;
    g_id2 = 5u;
    g_id3 = 5u;
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    LL_TIM_SetCounter(TIM2, 0u);
    LL_TIM_SetCounter(TIM3, 0u);
    g_t3cnt = 0u;
    __disable_irq();
    LL_TIM_EnableCounter(TIM2);
    LL_TIM_EnableCounter(TIM3);
    waitPendingTIM2(C3_TMO_PEND);
    g_tunmask = DWT->CYCCNT;
    recordRaw(g_tunmask, 5u);
    __enable_irq();
    g_need = g_w + 1u;
    waitCond(&g_w, g_need, C3_TMO_1);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);

    /* ── Fase D2: mascaramento BASEPRI, id6 ──
     * 0x20 = prio 2 << 4 (GROUP_4, 4 bits): mascara prio numerica >= 0x20,
     * i.e. TIM2(2) e TIM3(12); resto identico a D1. */
    g_phase = PH_DBASE;
    g_id2 = 6u;
    g_id3 = 6u;
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    LL_TIM_SetCounter(TIM2, 0u);
    LL_TIM_SetCounter(TIM3, 0u);
    g_t3cnt = 0u;
    __set_BASEPRI(0x20u);
    LL_TIM_EnableCounter(TIM2);
    LL_TIM_EnableCounter(TIM3);
    waitPendingTIM2(C3_TMO_PEND);
    g_tunmask = DWT->CYCCNT;
    recordRaw(g_tunmask, 6u);
    __set_BASEPRI(0u);
    g_need = g_w + 1u;
    waitCond(&g_w, g_need, C3_TMO_1);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);

    /* ── Fase E: empate de prioridade (TIM3=2), id7 ──
     * Classe A: mesma prio -> vence o menor exception number (28 < 29). */
    NVIC_SetPriority(TIM3_IRQn, 2);
    g_phase = PH_ETIE;
    g_id2 = 7u;
    g_id3 = 7u;
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    LL_TIM_SetCounter(TIM2, 0u);
    LL_TIM_SetCounter(TIM3, 0u);
    g_t3cnt = 0u;
    g_need = g_w + 32u;
    LL_TIM_EnableCounter(TIM2);
    LL_TIM_EnableCounter(TIM3);
    waitCond(&g_t3cnt, 16u, C3_TMO_16);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    NVIC_SetPriority(TIM3_IRQn, 12); /* restaura valor congelado do .ioc */

    /* ── Fim: publica e estaciona ── */
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableCounter(TIM3);
    NVIC_DisableIRQ(TIM2_IRQn);
    NVIC_DisableIRQ(TIM3_IRQn);
    c3_n = g_w * 2u;
    __DSB();
    c3_done = 1u;
    for (;;)
    {
        __WFI();
    }
}
