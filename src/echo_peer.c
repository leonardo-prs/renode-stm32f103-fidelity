/**
 * @file    src/echo_peer.c
 * @brief   Peer de echo para o C4 no Renode (INFRA de teste, não DUT).
 *
 * No HW o loopback do C4 é um jumper físico PA9→PA10 (passivo). No Renode
 * não há wire TX→RX intrínseco; o caminho canônico é um UART hub
 * (`emulation CreateUARTHub`) entre DUAS máquinas em virtual-time:
 * machine-0 roda o C4 (DUT), machine-1 roda este echo (devolve cada byte).
 * Entrega do hub é em virtual-time com atraso ≤ quantum (1us = 8c @8MHz),
 * caracterizado na análise — ver renode/PLAN.md e tcc/tmp/log.md.
 *
 * Compilado com SCENARIO=ECHO. Roda para sempre (sem done flag; GDB nunca
 * faz dump desta máquina). Polling puro, sem IRQs: determinístico.
 */

#include "board.h"
#include "periph.h"                     /* usart1_init_115200_8n1 */
#include "stm32f1xx_ll_usart.h"

/* Contador observável via GDB (prova de vida do peer). */
volatile uint32_t echo_n = 0U;

/**
 * @brief Entry do peer (build/echo/firmware.elf).
 *        Nunca retorna.
 */
int main(void)
{
    board_init();
    usart1_init_115200_8n1();

    SysTick->CTRL = 0U;                 /* sem tick */

    for (;;)
    {
        while (LL_USART_IsActiveFlag_RXNE(USART1) == 0U)
        {
        }
        (void)USART1->SR;               /* SR lido 1º: limpa ORE junto... */
        uint8_t b = LL_USART_ReceiveData8(USART1); /* ...ao ler DR (RM0008 §27.3) */
        while (LL_USART_IsActiveFlag_TXE(USART1) == 0U)
        {
        }
        LL_USART_TransmitData8(USART1, b);
        ++echo_n;
    }
}
