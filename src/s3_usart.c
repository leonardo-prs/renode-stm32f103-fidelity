/**
 * @file    src/s3_usart.c
 * @brief   S3 — USART (cenário 3 da ABI fidelity v1).
 *
 * Mede troca USART1 115200 8N1 em loopback físico PA9→PA10 (Renode: UARTHub
 * passivo, sem echo peer). Condições (códigos exatos do contrato
 * RESULT_CONTRACT[3] em scripts/fidelity_analyze.py):
 *   1 leisurely_10ms — payload espaçado ≥10 ms;
 *   2 burst          — payload back-to-back (TXE);
 *   3 blackout_ore   — não ler DR durante a receção → ORE no HW real
 *                      (RM0008 §27.3.3–5). No Renode ORE nunca ocorre:
 *                      ore_events=0 é um model gap legítimo — nunca falsificar;
 *   4 ore_recovery   — provocação controlada + recuperação SR→DR
 *                      (RM0008 §27.3.5) com first_byte_retained, e depois
 *                      troca limpa do payload completo.
 *
 * Rows (a..f) = tx_bytes, rx_bytes, ore_events, recovery_ok, checksum_ok,
 * first_byte_retained. As condições 1/2/4 exigem rx == tx e checksum_ok = 1.
 *
 * Contabilidade (condição 4): o byte DPLICADO enviado para provocar ORE é
 * ESTÍMULO deliberado — não conta em tx/rx do payload (8 bytes); documentado
 * no relatório. Como o duplicado tem o MESMO valor do primeiro byte, o
 * first_byte_retained é verdadeiro em HW e RN independentemente de qual cópia
 * sobreviva no DR.
 *
 * Eventos: S3_TX/S3_RX por byte só nos primeiros 8 bytes do 1º trial de cada
 * condição (4×8×2=64, writer MAIN) + S3_SR por ORE observado + BOOT = ≤128.
 * Trial ids globais 1..8 (2 trials × 4 condições).
 */

#include "board.h"
#include "periph.h"
#include "fidelity.h"

#define S3_SEED             123U
#define S3_PAYLOAD_LEN      8U
#define S3_BLACKOUT_BYTES   3U
#define S3_LEISURE_TICKS    80000U             /* ≥10 ms @ 8 MHz */
#define S3_BYTE_TIMEOUT     200000U            /* ~25 ms: limite por byte */
#define S3_TRIALS_PER_COND  2U

static uint8_t s_payload[S3_PAYLOAD_LEN];

/* ── USART polling com timeout limitado (nunca pendurar) ── */

static void busy_wait_ticks(uint32_t ticks)
{
    uint32_t t0 = fidelity_ticks();
    while ((fidelity_ticks() - t0) < ticks) {
        __NOP();
    }
}

/* Envia 1 byte; devolve 0 se TXE não aparecer dentro do limite. */
static uint32_t usart_send(uint8_t byte)
{
    uint32_t t0 = fidelity_ticks();
    while (LL_USART_IsActiveFlag_TXE(USART1) == 0U) {
        if ((fidelity_ticks() - t0) > S3_BYTE_TIMEOUT) {
            return 0U;
        }
    }
    LL_USART_TransmitData8(USART1, byte);
    return 1U;
}

/* Recebe 1 byte; devolve 0 se RXNE não aparecer dentro do limite. */
static uint32_t usart_recv(uint8_t *byte)
{
    uint32_t t0 = fidelity_ticks();
    while (LL_USART_IsActiveFlag_RXNE(USART1) == 0U) {
        if ((fidelity_ticks() - t0) > S3_BYTE_TIMEOUT) {
            return 0U;
        }
    }
    *byte = LL_USART_ReceiveData8(USART1);
    return 1U;
}

static uint8_t payload_checksum(const uint8_t *buf, uint32_t n)
{
    uint8_t fold = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        fold ^= (uint8_t)(buf[i] + (uint8_t)i);
    }
    return fold;
}

/* ── contagem de eventos (1º trial de cada condição, ≤8 bytes) ── */

static uint32_t s_trace_bytes;
static uint32_t s_trial;

static void trace_tx(uint8_t byte)
{
    if (s_trace_bytes < S3_PAYLOAD_LEN) {
        fidelity_trace(FIDELITY_MAIN, FIDELITY_S3_TX, s_trial, byte);
    }
}

static void trace_rx(uint8_t byte)
{
    if (s_trace_bytes < S3_PAYLOAD_LEN) {
        fidelity_trace(FIDELITY_MAIN, FIDELITY_S3_RX, s_trial, byte);
    }
}

/* Observa ORE em SR durante a provocação; conta ocorrências (0 no RN). */
static uint32_t poll_ore(uint32_t window_ticks)
{
    uint32_t count = 0U;
    uint32_t t0 = fidelity_ticks();
    while ((fidelity_ticks() - t0) < window_ticks) {
        if (LL_USART_IsActiveFlag_ORE(USART1) != 0U) {
            ++count;
            fidelity_trace(FIDELITY_MAIN, FIDELITY_S3_SR, s_trial, count);
            /* SR já foi lido pela macro LL (rc_w0 no hardware F1): ORE
             * permanece até leitura SR→DR; contamos uma vez por janela. */
            break;
        }
    }
    return count;
}

/* Teardown fora das contagens: SR→DR (limpa ORE) e drena RXNE. */
static void usart_drain(void)
{
    (void)USART1->SR;
    (void)LL_USART_ReceiveData8(USART1);
    for (uint32_t i = 0U; i < 4U; ++i) {
        uint8_t junk;
        if (usart_recv(&junk) == 0U) {
            break;
        }
        (void)USART1->SR;
    }
}

/* ── protocolos por condição ── */

static void run_leisurely(void)
{
    uint8_t rx[S3_PAYLOAD_LEN];
    uint32_t rxn = 0U;
    for (uint32_t i = 0U; i < S3_PAYLOAD_LEN; ++i) {
        trace_tx(s_payload[i]);
        (void)usart_send(s_payload[i]);
        busy_wait_ticks(S3_LEISURE_TICKS);
        uint8_t b;
        if (usart_recv(&b) != 0U) {
            trace_rx(b);
            rx[rxn++] = b;
        }
    }
    uint8_t ok = (rxn == S3_PAYLOAD_LEN) &&
                 (payload_checksum(rx, rxn) == payload_checksum(s_payload, S3_PAYLOAD_LEN));
    fidelity_result(s_trial, 1U, S3_PAYLOAD_LEN, rxn, 0U, 0U, ok ? 1U : 0U, 0U);
}

static void run_burst(void)
{
    uint8_t rx[S3_PAYLOAD_LEN];
    uint32_t rxn = 0U;
    for (uint32_t i = 0U; i < S3_PAYLOAD_LEN; ++i) {
        trace_tx(s_payload[i]);
        (void)usart_send(s_payload[i]);
    }
    for (uint32_t i = 0U; i < S3_PAYLOAD_LEN; ++i) {
        uint8_t b;
        if (usart_recv(&b) != 0U) {
            trace_rx(b);
            rx[rxn++] = b;
        }
    }
    uint8_t ok = (rxn == S3_PAYLOAD_LEN) &&
                 (payload_checksum(rx, rxn) == payload_checksum(s_payload, S3_PAYLOAD_LEN));
    fidelity_result(s_trial, 2U, S3_PAYLOAD_LEN, rxn, 0U, 0U, ok ? 1U : 0U, 0U);
}

static void run_blackout(void)
{
    /* Envia sem nunca ler DR: 2ª receção sem RXNE limpo provoca ORE (HW). */
    for (uint32_t i = 0U; i < S3_BLACKOUT_BYTES; ++i) {
        trace_tx(s_payload[i]);
        (void)usart_send(s_payload[i]);
    }
    busy_wait_ticks(3U * 1400U);               /* ≥2 frames a 115200 */
    uint32_t ore = poll_ore(8000U);
    /* Row registado com os valores observados; o teardown é depois. */
    fidelity_result(s_trial, 3U, S3_BLACKOUT_BYTES, 0U, ore, 0U, 0U, 0U);
    usart_drain();                            /* fora das contagens */
}

static void run_recovery(void)
{
    /* Fase A — provocação: envia payload[0] e um duplicado (ESTÍMULO, fora
     * da contagem do payload) sem ler DR. O DR mantém o 1º byte; o duplicado
     * é perdido no HW (ORE). No RN não há ORE — o valor retido é igual na
     * mesma (duplicado == original). */
    trace_tx(s_payload[0]);
    (void)usart_send(s_payload[0]);
    trace_tx(s_payload[0]);
    (void)usart_send(s_payload[0]);           /* duplicado: estímulo */
    busy_wait_ticks(3U * 1400U);
    uint32_t ore = poll_ore(8000U);

    /* Recuperação RM0008 §27.3.5: ler SR, depois DR (limpa ORE). */
    (void)USART1->SR;
    uint8_t retained = LL_USART_ReceiveData8(USART1);
    trace_rx(retained);
    uint32_t first_retained = (retained == s_payload[0]) ? 1U : 0U;

    /* O duplicado de estímulo pode sobreviver à provocação: no HW real o
     * ORE descarta-o, mas o modelo Renode não levanta ORE nem descarta e
     * entrega-o. Drenar com timeout limitado antes da fase limpa — bytes
     * drenados são ESTÍMULO e não contam em rx_bytes (contabilidade igual
     * nos dois ambientes). */
    uint8_t stimulus;
    while (usart_recv(&stimulus) != 0U) {
        /* descarta: sobrevivente do ORE (model gap) */
    }

    /* Fase B — troca limpa do resto do payload (payload[1..7]). */
    uint8_t rx[S3_PAYLOAD_LEN];
    uint32_t rxn = 0U;
    rx[rxn++] = retained;                     /* payload[0] contado 1 vez */
    uint32_t clean = 1U;
    for (uint32_t i = 1U; i < S3_PAYLOAD_LEN; ++i) {
        trace_tx(s_payload[i]);
        if (usart_send(s_payload[i]) == 0U) {
            clean = 0U;
            break;
        }
        uint8_t b;
        if (usart_recv(&b) == 0U) {
            clean = 0U;
            break;
        }
        trace_rx(b);
        rx[rxn++] = b;
    }
    uint32_t checksum_ok = (rxn == S3_PAYLOAD_LEN) &&
                           (payload_checksum(rx, rxn) == payload_checksum(s_payload, S3_PAYLOAD_LEN));
    uint32_t recovery_ok = (clean != 0U) && (checksum_ok != 0U) && (first_retained != 0U);
    fidelity_result(s_trial, 4U, S3_PAYLOAD_LEN, rxn, ore,
                    recovery_ok, checksum_ok, first_retained);
}

int main(void)
{
    board_init();
    fidelity_init(3U, S3_SEED);

    /* Payload determinístico derivado do seed (igual em TX e RX). */
    for (uint32_t i = 0U; i < S3_PAYLOAD_LEN; ++i) {
        s_payload[i] = (uint8_t)((S3_SEED * (i + 1U)) ^ (i * 0x5AU) ^ 0x3CU);
    }

    usart1_init_115200_8n1();

    uint32_t trial = 1U;
    for (uint32_t cond = 1U; cond <= 4U; ++cond) {
        for (uint32_t t = 0U; t < S3_TRIALS_PER_COND; ++t) {
            s_trial = trial;
            /* Só o 1º trial de cada condição emite eventos por byte. */
            s_trace_bytes = (t == 0U) ? 0U : S3_PAYLOAD_LEN;
            switch (cond) {
            case 1U:
                run_leisurely();
                break;
            case 2U:
                run_burst();
                break;
            case 3U:
                run_blackout();
                break;
            default:
                run_recovery();
                break;
            }
            ++trial;
        }
    }

    /* Ensaio completo: congela o snapshot (DONE). */
    fidelity_finish(0U);
}
