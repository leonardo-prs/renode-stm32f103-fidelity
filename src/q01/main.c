/*
 * src/q01/main.c — Q-01: liga o DWT_CYCCNT e executa a sequência medida
 * (q01.S) Q01_PASSES vezes. A primeira passagem traduz o código pela
 * primeira vez no Renode (fria); as seguintes reutilizam a tradução
 * (quentes). O coletor confere as três medidas em cada passagem.
 */
#include <stdint.h>

#include "stm32f1xx.h"

#define Q01_PASSES 3U
#define Q01_SLOTS  64U          /* >= Q01_PASSES × pontos por passagem */

uint32_t *q01_seq(uint32_t *cursor);
_Noreturn void q01_done(void);

uint32_t q01_cyc[Q01_SLOTS];    /* valores do DWT_CYCCNT, em ordem de execução */
volatile uint32_t q01_count;    /* slots preenchidos (único escritor: main) */

int main(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    uint32_t *cursor = q01_cyc;
    for (uint32_t pass = 0U; pass < Q01_PASSES; pass++) {
        cursor = q01_seq(cursor);
    }
    q01_count = (uint32_t)(cursor - q01_cyc);
    q01_done();
}
