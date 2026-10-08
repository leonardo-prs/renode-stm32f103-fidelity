/**
 * @file    src/s3/timing.c
 * @brief   S3B — temporização de quadro da USART1 em loopback.
 *
 * Referência física: 8N1 com BRR = 69 → 1 quadro = 10 × 69 = 690 ciclos
 * de HCLK (RM0008 §27.3.4); TXE sobe quando o TDR passa ao registrador de
 * deslocamento, TC ao fim do bit de parada, RXNE após a amostragem do bit
 * de parada (§27.3.2–3), IDLE após um quadro inteiro de linha ociosa.
 * Renode: TXE sempre 1, TC imediato; atraso de entrega pelo hub só com
 * AutoUpdateDelay (tag do run). Medição por polling do SR com DWT
 * (resolução = 1 volta do laço de polling).
 *
 *  1 single   32 amostras: byte isolado (linha ociosa antes)
 *             v0 = t_txe, v1 = t_tc, v2 = t_rxne, v3 = t_idle (após RXNE),
 *             v4 = byte_ok — tudo relativo à escrita no DR
 *  2 burst    4 rajadas × 16 bytes, escrita assim que TXE, leitura assim que
 *             RXNE; trial = rajada*16 + i; v0 = t_write_i, v1 = t_rxne_i
 *             (relativos ao início da rajada), v2 = byte_ok
 *  3 tc_8     4 ensaios: 8 bytes TXE-paced, v0 = tempo até TC final
 */
#include "uart.h"

#define S3B_SEED      0x5EED0032U
#define S3B_SINGLES   32U
#define S3B_BURSTS    4U
#define S3B_BURST_N   16U

static uint8_t s_tx[S3B_BURST_N * S3B_BURSTS + S3B_SINGLES];

static void quiet_line(void)
{
    (void)s3_wait_flag(USART_SR_TC);
    (void)s3_drain();
}

static void cond_single(void)
{
    for (uint32_t i = 0U; i < S3B_SINGLES; ++i) {
        quiet_line();
        uint8_t b = s_tx[i];
        uint32_t t_txe = 0U, t_tc = 0U, t_rx = 0U, t_idle = 0U, seen = 0U, rx = 0x100U;
        USART1->SR = ~USART_SR_TC;
        uint32_t t0 = fidelity_now();
        USART1->DR = b;
        while (seen != 7U) {
            uint32_t sr = USART1->SR;
            uint32_t t = fidelity_now() - t0;
            if ((seen & 1U) == 0U && (sr & USART_SR_TXE) != 0U) { t_txe = t; seen |= 1U; }
            if ((seen & 2U) == 0U && (sr & USART_SR_TC) != 0U)  { t_tc = t;  seen |= 2U; }
            if ((seen & 4U) == 0U && (sr & USART_SR_RXNE) != 0U) {
                t_rx = t;
                seen |= 4U;
                rx = USART1->DR & 0xFFU;
            }
            if (t > S3_TIMEOUT) {
                fidelity_flag(FIDELITY_ERR_TIMEOUT);
                break;
            }
        }
        while ((USART1->SR & USART_SR_IDLE) == 0U) {
            if ((fidelity_now() - t0) > S3_TIMEOUT) {
                break;
            }
        }
        t_idle = fidelity_now() - t0;
        (void)USART1->DR;                    /* SR → DR limpa IDLE */
        if (i == 0U) {
            fidelity_trace_at(FIDELITY_MAIN, t0, FIDELITY_EV_BEGIN, 1U, b);
            fidelity_trace_at(FIDELITY_MAIN, t0 + t_rx, FIDELITY_EV_END, 1U, rx);
        }
        fidelity_row(i, 1U, t_txe, t_tc, t_rx, t_idle, (rx == b) ? 1U : 0U, 0U);
    }
}

static void cond_burst(void)
{
    uint32_t t_w[S3B_BURST_N];
    uint32_t t_r[S3B_BURST_N];
    uint8_t got[S3B_BURST_N];
    for (uint32_t k = 0U; k < S3B_BURSTS; ++k) {
        quiet_line();
        const uint8_t *p = &s_tx[S3B_SINGLES + k * S3B_BURST_N];
        uint32_t sent = 0U, recv = 0U;
        uint32_t t0 = fidelity_now();
        while (recv < S3B_BURST_N && (fidelity_now() - t0) < 40U * S3_FRAME_TICKS) {
            uint32_t sr = USART1->SR;
            if ((sr & USART_SR_RXNE) != 0U) {
                t_r[recv] = fidelity_now() - t0;
                got[recv] = (uint8_t)USART1->DR;
                ++recv;
            }
            if (sent < S3B_BURST_N && (sr & USART_SR_TXE) != 0U) {
                t_w[sent] = fidelity_now() - t0;
                USART1->DR = p[sent];
                ++sent;
            }
        }
        for (uint32_t i = 0U; i < S3B_BURST_N; ++i) {
            uint32_t ok = (i < recv && got[i] == p[i]) ? 1U : 0U;
            fidelity_row(k * S3B_BURST_N + i, 2U, (i < sent) ? t_w[i] : 0xFFFFFFFFU,
                         (i < recv) ? t_r[i] : 0xFFFFFFFFU, ok, 0U, 0U, 0U);
        }
    }
}

static void cond_tc8(void)
{
    for (uint32_t k = 0U; k < 4U; ++k) {
        quiet_line();
        USART1->SR = ~USART_SR_TC;
        uint32_t t0 = fidelity_now();
        for (uint32_t i = 0U; i < 8U; ++i) {
            (void)s3_wait_flag(USART_SR_TXE);
            USART1->DR = s_tx[i];
        }
        (void)s3_wait_flag(USART_SR_TC);
        uint32_t t = fidelity_now() - t0;
        (void)s3_drain();
        fidelity_row(k, 3U, t, 0U, 0U, 0U, 0U, 0U);
    }
}

int main(void)
{
    board_init();
    fidelity_init(3U, 2U, S3B_SEED);
    uint32_t x = S3B_SEED;
    for (uint32_t i = 0U; i < sizeof(s_tx); ++i) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        s_tx[i] = (uint8_t)x;
    }
    usart1_init_115200_8n1();
    fidelity_row(0U, 0U, USART1->BRR, USART1->CR1, 0U, 0U, 0U, 0U);
    cond_single();
    cond_burst();
    cond_tc8();
    quiet_line();
    fidelity_finish();
}
