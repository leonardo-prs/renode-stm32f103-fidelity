/**
 * @file    src/c4_usart.c
 * @brief   C4 — USART1 115200 8N1 loopback fidelity (H4).
 *
 * Executável build/c4/firmware.elf (entry main()).
 * Stack: HSI 8 MHz (reset state), LL apenas, sem HAL, sem printf.
 * Hook c4_usart1_hook() chamado de USART1_IRQHandler (definido neste
 * arquivo, 1ª instrução do handler).
 *
 * Periféricos ligados: SOMENTE USART1 (+GPIOA PA9/PA10) e TIM2 (contador
 * de carga cooperativa da fase 2, SEM IRQ). NVIC: só USART1_IRQn (prio 8).
 *
 * ── H4 ─────────────────────────────────────────────────────────────────
 * O Renode entrega bytes USART1 corretos (funcional) E espaçamento
 * temporal por byte equivalente ao HW (temporal), sob carga cooperativa?
 * Métricas offline (GDB dump de c4_results/c4_aux): deltas RX por byte,
 * n_corrupt, flags ORE/FE/NE, BRR readback, UIF cooperativo da fase 2.
 *
 * ── Loopback-agnostic ──────────────────────────────────────────────────
 * O firmware NÃO sabe como TX chega ao RX: no HW há jumper físico
 * TX→RX; no Renode o wiring é resolvido fora do ELF. O mesmo ELF roda
 * nos dois mundos; qualquer divergência é fidelidade, não firmware.
 *
 * ── Padrão 0x55/0xAA ─────────────────────────────────────────────────
 * Bytes alternados 0x55/0xAA = transição a CADA bit (pior caso p/
 * clock-recovery e jitter). Esperado(i) = (i & 1) ? 0xAA : 0x55, com
 * contadores SEPARADOS p/ TX (g_tx_i, enviados) e RX (g_rx_i, recebidos)
 * — TX e RX andam em ritmos distintos (IRQ), nunca um índice só.
 *
 * ── Teoria de baud ────────────────────────────────────────────────────
 * USARTDIV = 8 MHz / (16 × 115200) = 4,3402… → BRR mantissa 4,
 * fração round(0,3402×16)=5 → BRR = 0x45 (4,3125). Baud real =
 * 8M/(16×4,3125) = 115942 (+0,64% sobre 115200; dentro da tolerância
 * de ±2% do receptor). Frame 10 bits (1 start + 8 data + 1 stop):
 * nominal 86,8056 µs = 694,44 ciclos @8MHz (não-inteiro; a média dos
 * deltas converge dentro da quantização do contador). c4_results[1030]
 * guarda o BRR lido de volta p/ auditoria.
 *
 * ── BER (sistemático apenas) ──────────────────────────────────────────
 * ~10⁴ bytes/fase ⇒ resolução de taxa ~1e-4; o cenário mede erros
 * sistemáticos (overrun/framing sob carga), NÃO BER estatístico
 * (exigiria ~1e9 bytes p/ 1e-9). n_corrupt conta mismatches; ORE/FE/NE
 * discriminam a causa no SR.
 *
 * ── Carga cooperativa fase 2 (DELIBERADA) ─────────────────────────────
 * Na fase 2 a IRQ do TIM2 fica DESABILITADA e o main faz poll do UIF
 * entre wakeups de RXNE. Racional: um handler vazio de TIM2
 * contaminaria a medida (cada UIF roubaria ciclos do caminho RX e
 * apareceria como jitter sistemático); o poll cooperativo prova que o
 * timer andou (UIF setou/limpou no ritmo) SEM handler, enquanto as
 * IRQs RXNE (~87 µs de cadência << período TIM2) acordam o WFI e o UIF
 * é visto com atraso < 1 período. HW × Renode: mesma cadência de UIF?
 *
 * ── Layout c4_results ─────────────────────────────────────────────────
 *   [0..1023]  timestamps CYCCNT absolutos dos 1024 1ºs bytes (fase 1a)
 *   [1024]     n_tx_total   (g_tx_i final; esperado 20000)
 *   [1025]     n_rx_total   (g_rx_i final; esperado 20000)
 *   [1026]     n_corrupt    (mismatches vs esperado(g_rx_i))
 *   [1027]     n_ore        (overrun)
 *   [1028]     n_fe         (framing error)
 *   [1029]     n_ne         (noise error)
 *   [1030]     USART1->BRR readback (esperado 0x45)
 *   [1031]     UIF count fase 2 (g_uif)
 * c4_n = 1032. c4_aux[0..c4_auxn-1] = CYCCNT absoluto de cada poll-hit
 * de UIF na fase 2 (até 256). c4_done: 0 = rodando, 1 = ok, 0xFD = timeout.
 * ─────────────────────────────────────────────────────────────────────
 */

#include "board.h"
#include "periph.h"                     /* usart1_init_115200_8n1, tim_1khz_init */

/* ── Símbolos públicos (extração via GDB) ─────────────────────────── */
volatile uint32_t c4_results[2048];
volatile uint32_t c4_n     = 0U;
volatile uint8_t  c4_done  = 0U;
volatile uint32_t c4_aux[256];
volatile uint32_t c4_auxn  = 0U;

/* ── Estado interno (volatile: tocado por ISR e thread/GDB) ───────── */
static volatile uint32_t g_tx_i    = 0U;  /* bytes transmitidos (lado TX) */
static volatile uint32_t g_rx_i    = 0U;  /* bytes recebidos (lado RX) */
static volatile uint32_t g_phase   = 0U;  /* 0=idle 1=ph1a 2=ph1b 3=ph2 */
static volatile uint32_t g_txN     = 0U;  /* alvo TX da fase corrente */
static volatile uint32_t g_corrupt = 0U;  /* mismatches dr vs esperado */
static volatile uint32_t g_ore     = 0U;  /* overrun errors */
static volatile uint32_t g_fe      = 0U;  /* framing errors */
static volatile uint32_t g_ne      = 0U;  /* noise errors */
static volatile uint32_t g_uif     = 0U;  /* poll-hits de UIF na fase 2 */

/* ── Timeouts (ciclos @8MHz; folga ~10× sobre o nominal) ──
 * Fase 1a: 1024 B × 694,44 ≈ 0,71 Mcyc → 8M (1 s).
 * Fases 1b/2: 10000 B ≈ 6,94 Mcyc → 80M (10 s).                         */
#define C4_TIMEOUT_PH1A_CYC  (8000000UL)
#define C4_TIMEOUT_PH1B_CYC  (80000000UL)
#define C4_TIMEOUT_PH2_CYC   (80000000UL)

/* ── Protótipos (antes da definição: -Wmissing-prototypes) ────────── */
void USART1_IRQHandler(void);
void c4_usart1_hook(void) __attribute__((noinline));

/**
 * @brief USART1 IRQ handler (overrides weak symbol from startup).
 */
void USART1_IRQHandler(void)
{
    c4_usart1_hook();
}

/* Byte esperado do índice i: alternância 0x55/0xAA (transição por bit). */
static uint8_t c4_pattern(uint32_t i)
{
    return (((i & 1U) != 0U) ? 0xAAU : 0x55U);
}

/* DWT CYCCNT como base de tempo absoluta (TRCENA + zera + habilita). */
static void c4_dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT       = 0U;
    DWT->CTRL        |= DWT_CTRL_CYCCNTENA_Msk;
}

/**
 * @brief Hook USART1 — 1ª instrução de USART1_IRQHandler.
 *
 * TXE primeiro: se a IT TXE está habilitada, TXE setado e ainda há
 * bytes a enviar, transmite esperado(g_tx_i++); ao atingir o alvo,
 * desabilita a IT TXE (fim do burst TX da fase).
 *
 * RXNE depois: SR lido PRIMEIRO (foto de ORE/FE/NE), depois DR via
 * LL (limpa RXNE). A sequência SR+DR já livra o ORE — RM0008 §27.3:
 * "ORE … cleared by a software sequence (read SR followed by read DR)".
 * Timestamp CYCCNT só na fase 1 (g_phase==1, 1024 1ºs bytes); compara
 * dr vs esperado(g_rx_i) e incrementa o contador RX.
 */
void c4_usart1_hook(void)
{
    /* ── TXE: alimenta o burst da fase ── */
    if ((LL_USART_IsEnabledIT_TXE(USART1) != 0U)
        && (LL_USART_IsActiveFlag_TXE(USART1) != 0U)
        && (g_tx_i < g_txN))
    {
        LL_USART_TransmitData8(USART1, c4_pattern(g_tx_i++));
        if (g_tx_i == g_txN)
        {
            LL_USART_DisableIT_TXE(USART1);
        }
    }

    /* ── RXNE: recebe, classifica erro, timestampa (fase 1), confere ── */
    if (LL_USART_IsActiveFlag_RXNE(USART1) != 0U)
    {
        uint32_t sr      = USART1->SR;  /* ler SR PRIMEIRO: foto ORE/FE/NE */
        uint32_t is_ore  = ((sr & USART_SR_ORE) != 0U) ? 1U : 0U;
        uint32_t is_fe   = ((sr & USART_SR_FE) != 0U) ? 1U : 0U;
        uint32_t is_ne   = ((sr & USART_SR_NE) != 0U) ? 1U : 0U;
        /* Ler DR limpa RXNE; a sequência SR+DR acima limpa ORE (RM0008 27.3). */
        uint8_t  dr      = LL_USART_ReceiveData8(USART1);

        if (is_ore != 0U)
        {
            g_ore++;
        }
        if (is_fe != 0U)
        {
            g_fe++;
        }
        if (is_ne != 0U)
        {
            g_ne++;
        }
        if ((g_phase == 1U) && (g_rx_i < 1024U))
        {
            c4_results[g_rx_i] = DWT->CYCCNT;
        }
        if (dr != c4_pattern(g_rx_i))
        {
            g_corrupt++;
        }
        g_rx_i++;
    }
}

/**
 * @brief Entry C4 — nunca retorna.
 *
 * Fase 1a: TX por polling (1024 B), RX por IRQ com timestamp.
 * Fase 1b: TX+RX por IRQ (até 10000 B totais).
 * Fase 2:  TIM2 ligado (PSC=7/ARR=999, IRQ desabilitada) como carga
 *          cooperativa + RXNE preemptivo (até 20000 B totais); main faz
 *          poll do UIF entre wakeups.
 * Timeout em qualquer espera → c4_done = 0xFD (resultados parciais
 * ainda preenchidos).
 */
int main(void)
{
    uint32_t t0;
    uint8_t  done_code = 1U;

    board_init();

    /* ── Periféricos deste cenário: USART1 e TIM2 (carga fase 2) ── */
    usart1_init_115200_8n1();
    tim_1khz_init(TIM2);
    LL_TIM_DisableCounter(TIM2);
    LL_TIM_DisableIT_UPDATE(TIM2);
    LL_TIM_ClearFlag_UPDATE(TIM2);
    NVIC_DisableIRQ(TIM2_IRQn);

    SysTick->CTRL = 0UL;                 /* SysTick fora */

    c4_dwt_init();

    /* Livra RXNE/ORE herdado do init (sequência SR+DR, RM0008 27.3). */
    if (LL_USART_IsActiveFlag_RXNE(USART1) != 0U)
    {
        (void)USART1->SR;
        (void)LL_USART_ReceiveData8(USART1);
    }
    NVIC_ClearPendingIRQ(USART1_IRQn);
    LL_USART_EnableIT_RXNE(USART1);      /* RX por IRQ nas 3 fases */
    NVIC_SetPriority(USART1_IRQn, NVIC_EncodePriority(NVIC_GetPriorityGrouping(), 8, 0));
    NVIC_EnableIRQ(USART1_IRQn);

    /* ── Fase 1a: TX polling (1024 B), RX IRQ + timestamp ── */
    g_phase = 1U;
    g_txN   = 1024U;
    while (g_tx_i < 1024U)
    {
        while (LL_USART_IsActiveFlag_TXE(USART1) == 0U)
        {
        }
        LL_USART_TransmitData8(USART1, c4_pattern(g_tx_i++));
    }
    t0 = DWT->CYCCNT;
    while (g_rx_i < 1024U)
    {
        if (((uint32_t)(DWT->CYCCNT - t0)) > C4_TIMEOUT_PH1A_CYC)
        {
            done_code = 0xFDU;
            goto c4_finish;
        }
    }

    /* ── Fase 1b: TX+RX por IRQ (até 10000 B totais) ── */
    g_phase = 2U;
    g_txN   = 10000U;
    LL_USART_EnableIT_TXE(USART1);       /* hook assume o TX */
    t0 = DWT->CYCCNT;
    while (g_rx_i < 10000U)
    {
        if (((uint32_t)(DWT->CYCCNT - t0)) > C4_TIMEOUT_PH1B_CYC)
        {
            done_code = 0xFDU;
            goto c4_finish;
        }
    }
    LL_USART_DisableIT_TXE(USART1);      /* idempotente (hook já cortou) */

    /* ── Fase 2: TIM2 ligado, poll UIF cooperativo + RXNE ── */
    g_phase = 3U;
    g_txN   = 20000U;                    /* mais 10000 B */
    LL_TIM_ClearFlag_UPDATE(TIM2);
    LL_TIM_SetCounter(TIM2, 0U);
    /* UIE religada (NVIC segue desligada): C2 prova que o modelo gera
     * update com UIE; a quarentena a desligou e a fase 2 a quer de volta
     * só como flag p/ poll — sem ISR, sem interferência no caminho RX. */
    LL_TIM_EnableIT_UPDATE(TIM2);
    LL_TIM_EnableCounter(TIM2);          /* MX PSC/ARR 7/999 já configurados */
    LL_USART_EnableIT_TXE(USART1);       /* retoma o burst TX via hook */
    t0 = DWT->CYCCNT;
    while (g_rx_i < 20000U)
    {
        if (LL_TIM_IsActiveFlag_UPDATE(TIM2) != 0U)
        {
            if (c4_auxn < 256U)
            {
                c4_aux[c4_auxn++] = DWT->CYCCNT;
            }
            g_uif++;
            LL_TIM_ClearFlag_UPDATE(TIM2);
        }
        /* Re-checa antes de dormir: a ISR entre o topo do loop e aqui pode
         * ter completado g_rx_i (20000) sem deixar IRQ pendente → o __WFI()
         * abaixo dormiria para sempre (corrida observada no rerun: main
         * estacionado com todos os bytes já recebidos, done=0). */
        if (g_rx_i < 20000U)
        {
            __WFI();  /* RXNE acorda << período TIM2: UIF visto pronto */
        }
        if (((uint32_t)(DWT->CYCCNT - t0)) > C4_TIMEOUT_PH2_CYC)
        {
            done_code = 0xFDU;
            goto c4_finish;
        }
    }

c4_finish:
    LL_TIM_DisableCounter(TIM2);
    LL_USART_DisableIT_TXE(USART1);
    LL_USART_DisableIT_RXNE(USART1);
    NVIC_DisableIRQ(USART1_IRQn);

    c4_results[1024] = g_tx_i;           /* n_tx_total */
    c4_results[1025] = g_rx_i;           /* n_rx_total */
    c4_results[1026] = g_corrupt;        /* n_corrupt */
    c4_results[1027] = g_ore;            /* n_ore */
    c4_results[1028] = g_fe;             /* n_fe */
    c4_results[1029] = g_ne;             /* n_ne */
    c4_results[1030] = (uint32_t)(USART1->BRR);  /* BRR readback (0x45) */
    c4_results[1031] = g_uif;            /* UIF count fase 2 */
    c4_n = 1032U;
    __DSB();
    c4_done = done_code;

    for (;;)
    {
        __WFI();
    }
}
