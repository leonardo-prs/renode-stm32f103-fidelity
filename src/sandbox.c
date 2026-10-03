/**
 * @file    src/sandbox.c
 * @brief   Sandbox genérico para testes ad-hoc no STM32F103C8T6
 *
 * ─────────────────────────────────────────────────────────────────────────
 * Executável build/sandbox/firmware.elf. Use para:
 *   - Validar o toolchain (build, flash, debug, GDB attach)
 *   - Piscar LED, ler registrador, testar periférico
 *   - Qualquer experimento livre que NÃO faz parte dos cenários formais
 *     (C1..C4) do TCC
 *
 * Stack: HSI 8 MHz (reset state do MCU). Sem HSE, sem PLL.
 * Periféricos ligados: SOMENTE GPIOC (PC13 = LED). Nenhuma IRQ.
 *
 * Para customizar: edite main(). O resto é boilerplate.
 * ─────────────────────────────────────────────────────────────────────────
 */

#include "board.h"       /* LED_BUILTIN_*, board_init() */
#include "periph.h"      /* led_init() */

/* Volatile: observado via GDB `p g_iter` em ambos os ambientes */
volatile uint32_t g_iter = 0U;

/**
 * @brief Entry do sandbox. Nunca retorna.
 *
 * Implementação padrão: blink LED em PC13 com período ~200 ms
 * (HIGH 100 ms, LOW 100 ms). A calibragem do busy-wait é empírica
 * para HSI 8 MHz; ajustar i_max se mudares de clock.
 */
int main(void)
{
    board_init();
    led_init();                         /* LED inicia apagado (PC13 HIGH, ativo-baixo) */

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
