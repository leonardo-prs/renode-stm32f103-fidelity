/**
 * @file    lib/board.h
 * @brief   Init comum a TODOS os cenarios (STM32F103C8T6 Blue Pill, HSI 8 MHz).
 *
 * Substitui o par Core/Inc/main.h + SystemClock_Config() do CubeMX.
 * Contem apenas o que todo cenario precisa: CMSIS/LL basicos, pino do LED
 * (constante, nao inicializado aqui) e board_init() (NVIC grouping + clock).
 * Nenhum periferico e ligado por board_init(); ver lib/periph.h.
 */
#ifndef BOARD_H
#define BOARD_H

#include "stm32f1xx.h"              /* CMSIS device: registradores, DWT, NVIC */
#include "stm32f1xx_ll_bus.h"       /* LL_APBx_GRP1_EnableClock */
#include "stm32f1xx_ll_cortex.h"
#include "stm32f1xx_ll_gpio.h"
#include "stm32f1xx_ll_rcc.h"
#include "stm32f1xx_ll_system.h"    /* LL_FLASH_SetLatency */
#include "stm32f1xx_ll_utils.h"     /* LL_SetSystemCoreClock */

/* LED onboard: PC13, ativo-baixo. */
#define LED_BUILTIN_Pin         LL_GPIO_PIN_13
#define LED_BUILTIN_GPIO_Port   GPIOC

/* 4 bits de preempcao, 0 de subprioridade (mesmo valor usado pelo CubeMX). */
#ifndef NVIC_PRIORITYGROUP_4
#define NVIC_PRIORITYGROUP_4    ((uint32_t)0x00000003)
#endif

#define BOARD_SYSCLK_HZ         8000000U    /* HSI 8 MHz, sem PLL */

/**
 * @brief Init minimo comum: NVIC PRIORITYGROUP_4 + SYSCLK = HSI 8 MHz.
 *
 * Nao habilita clock de nenhum periferico, nao liga SysTick, nao habilita
 * nenhuma IRQ. Cada cenario liga explicitamente o que usa.
 */
void board_init(void);

#endif /* BOARD_H */
