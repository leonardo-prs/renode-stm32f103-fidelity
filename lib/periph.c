/**
 * @file    lib/periph.c
 * @brief   Inits de periferico compartilhados (ver periph.h).
 *
 * Corpo = MX_GPIO_Init / MX_TIM2_Init / MX_TIM3_Init / MX_USART1_UART_Init
 * gerados pelo CubeMX 6.17, sem as linhas de NVIC e sem o clock de GPIOA
 * em led_init() (so era necessario para a USART, que o liga por conta
 * propria).
 */
#include "periph.h"

void led_init(void)
{
    LL_GPIO_InitTypeDef gpio = {0};

    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_GPIOC);

    LL_GPIO_SetOutputPin(LED_BUILTIN_GPIO_Port, LED_BUILTIN_Pin);

    gpio.Pin        = LED_BUILTIN_Pin;
    gpio.Mode       = LL_GPIO_MODE_OUTPUT;
    gpio.Speed      = LL_GPIO_SPEED_FREQ_LOW;
    gpio.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
    LL_GPIO_Init(LED_BUILTIN_GPIO_Port, &gpio);
}

void tim_1khz_init(TIM_TypeDef *TIMx)
{
    LL_TIM_InitTypeDef tim = {0};

    if (TIMx == TIM2)
    {
        LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    }
    else if (TIMx == TIM3)
    {
        LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM3);
    }
    else
    {
        return;
    }

    tim.Prescaler     = 7U;
    tim.CounterMode   = LL_TIM_COUNTERMODE_UP;
    tim.Autoreload    = 999U;
    tim.ClockDivision = LL_TIM_CLOCKDIVISION_DIV1;
    LL_TIM_Init(TIMx, &tim);
    LL_TIM_EnableARRPreload(TIMx);
    LL_TIM_SetClockSource(TIMx, LL_TIM_CLOCKSOURCE_INTERNAL);
    LL_TIM_SetTriggerOutput(TIMx, LL_TIM_TRGO_RESET);
    LL_TIM_DisableMasterSlaveMode(TIMx);
}

void usart1_init_115200_8n1(void)
{
    LL_USART_InitTypeDef usart = {0};
    LL_GPIO_InitTypeDef  gpio  = {0};

    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_USART1);
    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_GPIOA);

    /* PA9 -> USART1_TX */
    gpio.Pin        = LL_GPIO_PIN_9;
    gpio.Mode       = LL_GPIO_MODE_ALTERNATE;
    gpio.Speed      = LL_GPIO_SPEED_FREQ_HIGH;
    gpio.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
    LL_GPIO_Init(GPIOA, &gpio);

    /* PA10 -> USART1_RX */
    gpio.Pin  = LL_GPIO_PIN_10;
    gpio.Mode = LL_GPIO_MODE_FLOATING;
    LL_GPIO_Init(GPIOA, &gpio);

    usart.BaudRate            = 115200U;
    usart.DataWidth           = LL_USART_DATAWIDTH_8B;
    usart.StopBits            = LL_USART_STOPBITS_1;
    usart.Parity              = LL_USART_PARITY_NONE;
    usart.TransferDirection   = LL_USART_DIRECTION_TX_RX;
    usart.HardwareFlowControl = LL_USART_HWCONTROL_NONE;
    usart.OverSampling        = LL_USART_OVERSAMPLING_16;
    LL_USART_Init(USART1, &usart);
    LL_USART_ConfigAsyncMode(USART1);
    LL_USART_Enable(USART1);
}
