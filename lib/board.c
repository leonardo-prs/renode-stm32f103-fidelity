/**
 * @file    lib/board.c
 * @brief   Clock HSI 8 MHz explícito (ver board.h).
 *
 * Todos os valores coincidem com o estado de reset do RCC; a sequência é
 * escrita mesmo assim para documentar a premissa de clock e não depender
 * de estado deixado por bootloader ou debugger.
 */
#include "board.h"

void board_init(void)
{
    LL_FLASH_SetLatency(LL_FLASH_LATENCY_0);
    while (LL_FLASH_GetLatency() != LL_FLASH_LATENCY_0) {
    }
    LL_RCC_HSI_Enable();
    while (LL_RCC_HSI_IsReady() != 1U) {
    }
    LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
    LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
    LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
    LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_HSI);
    while (LL_RCC_GetSysClkSource() != LL_RCC_SYS_CLKSOURCE_STATUS_HSI) {
    }
    LL_SetSystemCoreClock(BOARD_HCLK_HZ);
}

uint32_t board_set_apb(uint32_t apb1_div, uint32_t apb2_div)
{
    LL_RCC_SetAPB1Prescaler(apb1_div);
    LL_RCC_SetAPB2Prescaler(apb2_div);
    __DSB();
    return RCC->CFGR;
}
