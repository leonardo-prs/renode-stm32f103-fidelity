/*
 * src/c2/common/startup.c — tabela de vetores e Reset_Handler dos firmwares do C2.
 *
 * Em C (regra de projeto: sem assembly escrito, 03-quadro-comum.typ §Regras).
 * Só o necessário: copia .data, zera .bss e chama main; .noinit (c2_param)
 * não é tocado. As linhas livres do catálogo vão para c2_irq_handler; toda
 * outra exceção cai em c2_fault, que o coletor observa por gancho
 * (execução inválida). O endereço da tabela é gravado no VTOR por main.
 */
#include "c2.h"

extern uint32_t _estack[], _sdata[], _edata[], _sidata[], _sbss[], _ebss[];

int main(void);
__attribute__((noreturn)) void Reset_Handler(void);

__attribute__((section(".isr_vector"), used))
const c2_vectors_t c2_vectors = {
    _estack,
    {
        Reset_Handler,                                  /*  1 Reset */
        c2_fault, c2_fault, c2_fault, c2_fault, c2_fault, /*  2..6 NMI, HardFault, MemManage, BusFault, UsageFault */
        c2_fault, c2_fault, c2_fault, c2_fault,         /*  7..10 reservados */
        c2_fault, c2_fault, c2_fault, c2_fault, c2_fault, /* 11..15 SVC, DebugMon, reservado, PendSV, SysTick */
        C2_IRQ_VECTORS
    },
};

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
    c2_fault();
}

void c2_fault(void)
{
    for (;;) {
    }
}
