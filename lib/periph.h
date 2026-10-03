/**
 * @file    lib/periph.h
 * @brief   Inits de periferico compartilhados por 2+ cenarios.
 *
 * Extraidos de Core/Src/{gpio,tim,usart}.c (MX_*_Init, CubeMX 6.17) com
 * UMA diferenca deliberada: nenhuma funcao aqui toca o NVIC. Prioridade e
 * habilitacao de IRQ sao responsabilidade explicita de cada cenario, para
 * que "quais IRQs estao vivas" seja legivel no proprio src/<cenario>.c.
 */
#ifndef PERIPH_H
#define PERIPH_H

#include "board.h"
#include "stm32f1xx_ll_tim.h"
#include "stm32f1xx_ll_usart.h"

/**
 * @brief PC13 (LED) como saida push-pull low-speed, nivel inicial HIGH
 *        (LED apagado). Liga apenas o clock de GPIOC.
 */
void led_init(void);

/**
 * @brief TIM2 ou TIM3 a 1 kHz: PSC=7, ARR=999 (8 MHz / 8 / 1000).
 *
 * Liga o clock APB1 do timer e configura base de tempo, ARR preload,
 * clock interno, TRGO=reset, sem master/slave. Contador PARADO, UIE
 * desligada, NVIC intocado. Obs.: LL_TIM_Init gera UG, logo UIF=1 ao
 * retornar — o cenario deve limpar a flag antes de armar.
 *
 * @param TIMx TIM2 ou TIM3 (outros: nao suportado, sem efeito).
 */
void tim_1khz_init(TIM_TypeDef *TIMx);

/**
 * @brief USART1 115200 8N1, TX+RX, oversampling 16, sem flow control.
 *
 * Liga clocks USART1 + GPIOA; PA9 = AF push-pull (TX), PA10 = floating
 * (RX). USART habilitada (UE/TE/RE), nenhuma IT de USART e NVIC intocado.
 */
void usart1_init_115200_8n1(void);

#endif /* PERIPH_H */
