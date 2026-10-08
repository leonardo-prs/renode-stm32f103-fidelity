/**
 * @file    src/s3/link.c
 * @brief   S3A — USART1 em loopback: integridade e semântica de flags.
 *
 * Bancada: fio PA9 (TX) → PA10 (RX) permanente. Renode: UARTHub com
 * loopback no usart1 (o emissor recebe os próprios bytes), sem peer ativo.
 * Comportamento de referência: RM0008 §27.3.2 (TXE/TC), §27.3.3 (RXNE,
 * ORE: "RDR não é perdido, o registrador de deslocamento é sobrescrito"),
 * §27.6.1 (SR; limpeza por leitura SR → DR).
 *
 *  1 ping_pong     32 bytes, envia e espera o eco de cada um
 *  2 full_duplex   64 bytes, escreve sempre que TXE, lê sempre que RXNE;
 *                  mede o adiantamento máximo do TX (bytes escritos − lidos)
 *  3 overrun       4 bytes sem ler o DR; depois SR, DR, dreno
 *  4 rxne_irq      32 bytes, recepção pela ISR (RXNEIE)
 *  5 txe_irq       32 bytes, transmissão pela ISR (TXEIE), recepção polling
 *  6 idle          IDLE após um byte; limpeza por SR → DR
 *  7 tc            TC logo após escrever DR e 2 quadros depois
 *  8 te_off        UE=1, TE=0: escrever DR transmite?
 *
 * Rows: trial 1..2 por condição; v0..v5 conforme firmware.py.
 */
#include "uart.h"

#define S3A_SEED    0x5EED0031U
#define S3A_TRIALS  2U
#define S3A_N       64U

void USART1_IRQHandler(void);

static uint8_t s_tx[S3A_N];
static volatile uint8_t s_rx[S3A_N];
static volatile uint32_t s_rx_n;
static volatile uint32_t s_tx_n;
static volatile uint32_t s_tx_len;
static volatile uint32_t s_irq_entries;

void USART1_IRQHandler(void)
{
    uint32_t sr = USART1->SR;
    s_irq_entries = s_irq_entries + 1U;
    /* Só consome RX se a recepção por IRQ estiver habilitada (senão
     * roubaria bytes do MAIN na condição txe_irq). */
    if ((USART1->CR1 & USART_CR1_RXNEIE) != 0U && (sr & USART_SR_RXNE) != 0U) {
        uint8_t b = (uint8_t)USART1->DR;
        uint32_t n = s_rx_n;
        if (n < S3A_N) {
            s_rx[n] = b;
        }
        s_rx_n = n + 1U;
    }
    if ((USART1->CR1 & USART_CR1_TXEIE) != 0U && (sr & USART_SR_TXE) != 0U) {
        uint32_t n = s_tx_n;
        if (n < s_tx_len) {
            USART1->DR = s_tx[n];
            s_tx_n = n + 1U;
        }
        if (n + 1U >= s_tx_len) {
            USART1->CR1 &= ~USART_CR1_TXEIE;
        }
    }
    if (s_irq_entries > 4U * S3A_N) {            /* guarda de tempestade */
        USART1->CR1 &= ~(USART_CR1_TXEIE | USART_CR1_RXNEIE);
    }
}

static uint32_t mismatches(uint32_t n)
{
    uint32_t bad = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        bad += (s_rx[i] != s_tx[i]) ? 1U : 0U;
    }
    return bad;
}

static void reset_rx(void)
{
    (void)s3_drain();
    s_rx_n = 0U;
    s_tx_n = 0U;
    s_irq_entries = 0U;
    for (uint32_t i = 0U; i < S3A_N; ++i) {
        s_rx[i] = 0U;
    }
}

static void cond_ping_pong(uint32_t trial)
{
    reset_rx();
    uint32_t timeouts = 0U;
    for (uint32_t i = 0U; i < 32U; ++i) {
        (void)s3_wait_flag(USART_SR_TXE);
        USART1->DR = s_tx[i];
        if (s3_wait_flag(USART_SR_RXNE) == 0U) {
            ++timeouts;
            continue;
        }
        s_rx[s_rx_n] = (uint8_t)USART1->DR;
        s_rx_n = s_rx_n + 1U;
    }
    fidelity_row(trial, 1U, s_rx_n, mismatches(s_rx_n), timeouts, 0U, 0U, 0U);
}

static void cond_full_duplex(uint32_t trial)
{
    reset_rx();
    uint32_t sent = 0U;
    uint32_t got = 0U;
    uint32_t ahead_max = 0U;
    uint32_t ore = 0U;
    uint32_t t0 = fidelity_now();
    while (got < S3A_N && (fidelity_now() - t0) < (S3A_N + 8U) * S3_FRAME_TICKS * 2U) {
        uint32_t sr = USART1->SR;
        if ((sr & USART_SR_ORE) != 0U) {
            ++ore;
        }
        if ((sr & USART_SR_RXNE) != 0U) {
            s_rx[got] = (uint8_t)USART1->DR;
            ++got;
        }
        if (sent < S3A_N && (sr & USART_SR_TXE) != 0U) {
            USART1->DR = s_tx[sent];
            ++sent;
        }
        if (sent - got > ahead_max) {
            ahead_max = sent - got;
        }
    }
    s_rx_n = got;
    fidelity_row(trial, 2U, got, mismatches(got), ahead_max, ore, sent, 0U);
}

#define S3A_EV_TX  0x300U
#define S3A_EV_SR  0x301U
#define S3A_EV_RX  0x302U

static void cond_overrun(uint32_t trial)
{
    reset_rx();
    for (uint32_t i = 0U; i < 4U; ++i) {
        (void)s3_wait_flag(USART_SR_TXE);
        USART1->DR = s_tx[i];
        fidelity_trace(FIDELITY_MAIN, S3A_EV_TX, trial, i);
    }
    /* Observa o SR por 8 quadros SEM ler o DR (ler só o SR não limpa ORE
     * nem RXNE); cada mudança vai para o trace com timestamp. */
    uint32_t last = 0xFFFFFFFFU;
    uint32_t t0 = fidelity_now();
    while ((fidelity_now() - t0) < 8U * S3_FRAME_TICKS) {
        uint32_t sr = USART1->SR & 0x3FFU;
        if (sr != last) {
            fidelity_trace(FIDELITY_MAIN, S3A_EV_SR, trial, sr);
            last = sr;
        }
    }
    uint32_t sr1 = USART1->SR;               /* 1ª leitura do SR */
    uint32_t dr = USART1->DR;                /* SR → DR: limpa ORE */
    uint32_t sr2 = USART1->SR;
    uint32_t first_idx = 0xFFU;
    for (uint32_t i = 0U; i < 4U; ++i) {
        if ((uint8_t)dr == s_tx[i]) {
            first_idx = i;
            break;
        }
    }
    /* Dreno instrumentado: valor e instante de cada byte que ainda vier. */
    uint32_t more = 0U;
    uint32_t matches = 0U;
    t0 = fidelity_now();
    while ((fidelity_now() - t0) < 4U * S3_FRAME_TICKS) {
        if ((USART1->SR & USART_SR_RXNE) != 0U) {
            uint32_t b = USART1->DR & 0xFFU;
            fidelity_trace(FIDELITY_MAIN, S3A_EV_RX, trial, b);
            matches += (more + 1U < 4U && b == s_tx[more + 1U]) ? 1U : 0U;
            ++more;
        }
    }
    (void)s3_drain();
    fidelity_row(trial, 3U, sr1 & 0x3FFU, first_idx, sr2 & 0x3FFU, more, dr & 0xFFU, matches);
}

static void cond_rxne_irq(uint32_t trial)
{
    reset_rx();
    USART1->CR1 |= USART_CR1_RXNEIE;
    NVIC_EnableIRQ(USART1_IRQn);
    for (uint32_t i = 0U; i < 32U; ++i) {
        (void)s3_wait_flag(USART_SR_TXE);
        USART1->DR = s_tx[i];
    }
    s3_wait_ticks(4U * S3_FRAME_TICKS);
    USART1->CR1 &= ~USART_CR1_RXNEIE;
    NVIC_DisableIRQ(USART1_IRQn);
    uint32_t n = s_rx_n;
    uint32_t pending = NVIC_GetPendingIRQ(USART1_IRQn);
    uint32_t stranded = s3_drain();          /* bytes que a ISR não buscou */
    fidelity_row(trial, 4U, n, mismatches(n < S3A_N ? n : S3A_N), s_irq_entries,
                 stranded, pending, 0U);
}

static void cond_txe_irq(uint32_t trial)
{
    reset_rx();
    s_tx_len = 32U;
    NVIC_EnableIRQ(USART1_IRQn);
    USART1->CR1 |= USART_CR1_TXEIE;
    uint32_t got = 0U;
    uint32_t t0 = fidelity_now();
    while (got < 32U && (fidelity_now() - t0) < 80U * S3_FRAME_TICKS) {
        if ((USART1->SR & USART_SR_RXNE) != 0U) {
            s_rx[got] = (uint8_t)USART1->DR;
            ++got;
        }
    }
    USART1->CR1 &= ~USART_CR1_TXEIE;
    NVIC_DisableIRQ(USART1_IRQn);
    s_rx_n = got;
    fidelity_row(trial, 5U, got, mismatches(got), s_irq_entries, s_tx_n, 0U, 0U);
}

static void cond_idle(uint32_t trial)
{
    reset_rx();
    USART1->DR = s_tx[0];
    uint32_t rx_ok = s3_wait_flag(USART_SR_RXNE);
    (void)USART1->DR;                         /* lê o byte (RXNE → 0) */
    uint32_t idle = s3_wait_flag(USART_SR_IDLE);
    uint32_t sr_before = USART1->SR;          /* SR → DR limpa IDLE */
    (void)USART1->DR;
    uint32_t sr_after = USART1->SR;
    fidelity_row(trial, 6U, rx_ok, idle, sr_before & 0x3FFU, sr_after & 0x3FFU, 0U, 0U);
}

static void cond_tc(uint32_t trial)
{
    reset_rx();
    (void)s3_wait_flag(USART_SR_TC);
    USART1->SR = ~USART_SR_TC;                /* TC é rc_w0 */
    uint32_t tc_cleared = (USART1->SR & USART_SR_TC) ? 1U : 0U;
    USART1->DR = s_tx[1];
    uint32_t tc_now = (USART1->SR & USART_SR_TC) ? 1U : 0U;
    s3_wait_ticks(2U * S3_FRAME_TICKS);
    uint32_t tc_later = (USART1->SR & USART_SR_TC) ? 1U : 0U;
    fidelity_row(trial, 7U, tc_cleared, tc_now, tc_later, 0U, 0U, 0U);
}

static void cond_te_off(uint32_t trial)
{
    reset_rx();
    USART1->CR1 &= ~USART_CR1_TE;
    s3_wait_ticks(2U * S3_FRAME_TICKS);
    USART1->DR = s_tx[2];
    uint32_t rx = s3_wait_flag(USART_SR_RXNE);
    uint32_t sr = USART1->SR;
    uint32_t b = rx ? (USART1->DR & 0xFFU) : 0x100U;
    USART1->CR1 |= USART_CR1_TE;
    s3_wait_ticks(2U * S3_FRAME_TICKS);
    (void)s3_drain();
    /* O que importa é se o DADO escrito saiu; ao desligar TE o HW pode
     * produzir um quadro espúrio (0x00 / erro de quadro) na linha. */
    fidelity_row(trial, 8U, (b == s_tx[2]) ? 1U : 0U, rx, b, sr & 0x3FFU, 0U, 0U);
}

int main(void)
{
    board_init();
    fidelity_init(3U, 1U, S3A_SEED);
    uint32_t x = S3A_SEED;
    for (uint32_t i = 0U; i < S3A_N; ++i) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        s_tx[i] = (uint8_t)x;
    }
    usart1_init_115200_8n1();
    NVIC_SetPriority(USART1_IRQn, 4U);
    fidelity_row(0U, 0U, USART1->BRR, USART1->CR1, USART1->CR2, USART1->CR3, 0U, 0U);

    for (uint32_t trial = 1U; trial <= S3A_TRIALS; ++trial) {
        fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_BEGIN, trial, 0U);
        cond_ping_pong(trial);
        cond_full_duplex(trial);
        cond_overrun(trial);
        cond_rxne_irq(trial);
        cond_txe_irq(trial);
        cond_idle(trial);
        cond_tc(trial);
        cond_te_off(trial);
        fidelity_trace(FIDELITY_MAIN, FIDELITY_EV_END, trial, 0U);
    }
    (void)s3_drain();
    fidelity_finish();
}
