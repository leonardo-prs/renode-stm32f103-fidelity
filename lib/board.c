/**
 * @file    lib/board.c
 * @brief   Init comum: NVIC grouping + clock HSI 8 MHz.
 *
 * Extraido literalmente de Core/Src/main.c (CubeMX 6.17, STM32Cube FW_F1
 * V1.8.7) na migracao para vendor/ congelado. Diferencas deliberadas em
 * relacao ao main() gerado (todas = "nao ligar o que nenhum cenario usa"):
 *   - sem LL_APB2 AFIO clock e sem LL_GPIO_AF_Remap_SWJ_NOJTAG(): o estado
 *     de reset (SWJ completo) ja permite SWD em PA13/PA14;
 *   - sem LL_APB1 PWR clock: nenhum cenario usa PWR (WFI = sleep mode, que
 *     nao depende de PWR_CR);
 *   - sem LL_Init1msTick(): SysTick fica no estado de reset (desligado);
 *     antes todo cenario o desligava manualmente;
 *   - sem NVIC_SetPriority(SysTick_IRQn, 15): SysTick nao e usado.
 */
#include "board.h"

static void clock_hsi8_init(void);

void board_init(void)
{
    NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4);
    clock_hsi8_init();
}

/*
 * SYSCLK = HSI 8 MHz, AHB/APB1/APB2 = /1, 0 wait states. Todos os valores
 * coincidem com o estado de reset do RCC; a sequencia e mantida explicita
 * para documentar a premissa de clock e tornar o init independente de
 * qualquer estado deixado por bootloader/debugger.
 */
static void clock_hsi8_init(void)
{
    LL_FLASH_SetLatency(LL_FLASH_LATENCY_0);
    while (LL_FLASH_GetLatency() != LL_FLASH_LATENCY_0)
    {
    }
    LL_RCC_HSI_SetCalibTrimming(16);
    LL_RCC_HSI_Enable();
    while (LL_RCC_HSI_IsReady() != 1U)
    {
    }
    LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
    LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
    LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
    LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_HSI);
    while (LL_RCC_GetSysClkSource() != LL_RCC_SYS_CLKSOURCE_STATUS_HSI)
    {
    }
    LL_SetSystemCoreClock(BOARD_SYSCLK_HZ);
}
