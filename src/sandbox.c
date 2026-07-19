/**
 * @file    src/sandbox.c
 * @brief   Sandbox genérico para testes ad-hoc no STM32F103C8T6
 *
 * ─────────────────────────────────────────────────────────────────────────
 * Compilado quando SCENARIO=SANDBOX. Use para:
 *   - Validar o toolchain (build, flash, debug, GDB attach)
 *   - Piscar LED, ler registrador, testar periférico
 *   - Qualquer experimento livre que NÃO faz parte dos cenários formais
 *     (scenario_a, scenario_b) do TCC
 *
 * Stack: HSI 8 MHz (reset state do MCU). Sem HSE, sem PLL.
 * Periféricos básicos (GPIO PC13 = LED) já vêm inicializados pelo
 * Core/Src/main.c (SystemClock_Config + MX_GPIO_Init).
 *
 * Para customizar: edite sandbox_main(). O resto é boilerplate.
 * ─────────────────────────────────────────────────────────────────────────
 */

#include "main.h"        /* CubeMX-gerado: LED_BUILTIN_Pin, LED_BUILTIN_GPIO_Port, etc. */
#include "gpio.h"
#include "stm32f1xx_ll_gpio.h"

/* Volatile: observado via GDB `p g_iter` em ambos os ambientes */
volatile uint32_t g_iter = 0U;

/**
 * @brief Entry do cenário sandbox — chamada por Core/Src/main.c
 *        quando SCENARIO_SANDBOX está definido.
 *
 * Implementação padrão: blink LED em PC13 com período ~200 ms
 * (HIGH 100 ms, LOW 100 ms). A calibragem do busy-wait é empírica
 * para HSI 8 MHz; ajustar i_max se mudares de clock.
 */
void sandbox_main(void)
{
    /* LED inicia apagado (PC13 em HIGH porque é ativo-baixo) */
    LL_GPIO_SetOutputPin(LED_BUILTIN_GPIO_Port, LED_BUILTIN_Pin);

    for (;;)
    {
        LL_GPIO_TogglePin(LED_BUILTIN_GPIO_Port, LED_BUILTIN_Pin);

        /* Busy-wait ~100 ms @ 8 MHz HSI. Volatile evita que o
         * compilador otimize o loop. Ajuste i_max se o clock mudar. */
        for (volatile uint32_t i = 0U; i < 200000U; ++i)
        {
            __NOP();
        }

        ++g_iter;
    }
}
