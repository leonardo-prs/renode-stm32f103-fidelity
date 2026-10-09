/**
 * @file    lib/board.h
 * @brief   Inicialização comum a todos os firmwares (STM32F103, HSI 8 MHz).
 *
 * board_init() deixa: SYSCLK = HCLK = HSI 8 MHz, AHB/APB1/APB2 = /1, flash
 * com 0 wait states, sem HSE e sem PLL, NVIC com PRIGROUP padrão do
 * cenário. Nenhum periférico é ligado aqui: cada firmware liga o que usa.
 */
#ifndef BOARD_H
#define BOARD_H

#include "stm32f1xx.h"
#include "stm32f1xx_ll_bus.h"
#include "stm32f1xx_ll_cortex.h"
#include "stm32f1xx_ll_gpio.h"
#include "stm32f1xx_ll_rcc.h"
#include "stm32f1xx_ll_system.h"
#include "stm32f1xx_ll_utils.h"

#define BOARD_HCLK_HZ 8000000U      /* HSI nominal (RM0008 §7.2.1) */

/** Clock HSI 8 MHz, prescalers /1, flash 0 WS. */
void board_init(void);

/**
 * Troca os prescalers APB1/APB2 (valores LL_RCC_APB1_DIV_x / APB2_DIV_x).
 * Só o C2 usa, para os contrastes da árvore de clock dos timers.
 * Devolve RCC->CFGR lido de volta (registra o que o "hardware" aceitou).
 */
uint32_t board_set_apb(uint32_t apb1_div, uint32_t apb2_div);

#endif /* BOARD_H */
