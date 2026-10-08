/**
 * @file    src/s3/uart.h
 * @brief   Helpers USART1 comuns a S3A/S3B (loopback físico PA9 → PA10).
 *
 * USART1 115200 8N1, BRR = 0x45 (USARTDIV 4,3125 @ 8 MHz) → 1 quadro =
 * 10 bits × 69 = 690 ciclos de HCLK (RM0008 §27.3.4). Toda espera tem
 * timeout em ticks DWT: nenhum teste pendura.
 */
#ifndef S3_UART_H
#define S3_UART_H

#include "board.h"
#include "periph.h"
#include "fidelity.h"

#define S3_FRAME_TICKS   690U
#define S3_TIMEOUT       (40U * S3_FRAME_TICKS)

/* Espera até (SR & mask) != 0; devolve 1 se viu, 0 em timeout. */
static inline uint32_t s3_wait_flag(uint32_t mask)
{
    uint32_t t0 = fidelity_now();
    while ((USART1->SR & mask) == 0U) {
        if ((fidelity_now() - t0) > S3_TIMEOUT) {
            return 0U;
        }
    }
    return 1U;
}

static inline void s3_wait_ticks(uint32_t ticks)
{
    uint32_t t0 = fidelity_now();
    while ((fidelity_now() - t0) < ticks) {
    }
}

/* Esvazia o receptor (SR → DR) até a linha ficar quieta por 2 quadros. */
static inline uint32_t s3_drain(void)
{
    uint32_t n = 0U;
    uint32_t t0 = fidelity_now();
    while ((fidelity_now() - t0) < 2U * S3_FRAME_TICKS) {
        if ((USART1->SR & USART_SR_RXNE) != 0U) {
            (void)USART1->DR;
            ++n;
            t0 = fidelity_now();
        }
    }
    (void)USART1->SR;
    (void)USART1->DR;               /* limpa ORE/IDLE residuais (SR → DR) */
    return n;
}

#endif /* S3_UART_H */
