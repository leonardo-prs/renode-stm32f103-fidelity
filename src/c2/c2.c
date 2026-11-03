/*
 * src/c2/c2.c — vetores, partida e configuração comuns aos firmwares do C2.
 *
 * Toda configuração de que os casos dependem é escrita explicitamente,
 * mesmo quando é o valor de reset (03-quadro-comum.typ §Regras de projeto):
 * VTOR, PRIGROUP = 0 (os 4 bits implementados são de grupo), BASEPRI = 0,
 * FAULTMASK = PRIMASK = 0, todas as linhas desabilitadas e sem pendência.
 */
#include "c2.h"

extern uint32_t _estack[], _sdata[], _edata[], _sidata[], _sbss[], _ebss[];

const uint8_t c2_livres[C2_N_LIVRE] = {0, 1, 2, 3, 4, 5, 18, 19, 20, 21, 22, 35, 36, 41, 42};

__attribute__((section(".noinit"))) volatile uint32_t c2_caso;
volatile uint32_t c2_log[C2_LOG];
volatile uint32_t c2_nlog;
volatile uint32_t c2_vezes[16 + C2_N_IRQ];
volatile uint32_t c2_pronto;
__attribute__((section(".noinit"))) volatile uint32_t c2_rec[C2_REC];   /* só vale até c2_nrec */
volatile uint32_t c2_nrec;
volatile uint32_t c2_status;

#define F c2_falha
__attribute__((section(".isr_vector"), used))
void (*const c2_vetores[16 + C2_N_IRQ])(void) = {
    (void (*)(void))_estack, Reset_Handler,
    F, F, F, F, F, F, F, F, F, F, F, F, F, F,      /* 2..15: exceções do sistema, não usadas */
    [16 ... 16 + C2_N_IRQ - 1] = c2_irq,           /* IRQ 0..42 */
};
#undef F

void Reset_Handler(void)
{
    const uint32_t *src = _sidata;
    for (uint32_t *dst = _sdata; dst < _edata; dst++) {
        *dst = *src++;
    }
    for (uint32_t *dst = _sbss; dst < _ebss; dst++) {
        *dst = 0U;
    }
    (void)main();
    c2_falha();
}

void c2_falha(void)
{
    for (;;) {
    }
}

void c2_fim(void)
{
}

/* Fim do caso: o gancho em c2_fim despeja o registro; depois o núcleo dorme
 * com tudo desabilitado (o tempo virtual corre sem instruções). */
void c2_encerra(void)
{
    __disable_irq();
    c2_status = 1U;
    c2_fim();
    for (;;) {
        __WFI();
    }
}

void c2_init(void)
{
    SCB->VTOR = (uint32_t)c2_vetores;
    NVIC_SetPriorityGrouping(0U);
    __set_BASEPRI(0U);
    __enable_fault_irq();
    for (uint32_t k = 0U; k < 8U; k++) {
        NVIC->ICER[k] = 0xFFFFFFFFU;
        NVIC->ICPR[k] = 0xFFFFFFFFU;
    }
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    c2_barreira();
    __enable_irq();
}

void c2_grava(uint32_t valor)
{
    uint32_t n = c2_nrec;
    if (n < C2_REC) {
        c2_rec[n] = valor;
        c2_nrec = n + 1U;
    }
}

void c2_espera(uint32_t voltas)
{
    for (volatile uint32_t i = 0U; i < voltas; i++) {
    }
}
