/*
 * src/c2/common/c2.c — main comum dos firmwares do C2.
 *
 * Fixa explicitamente toda configuração de que os casos dependem, mesmo
 * quando ela é o valor de reset (03-quadro-comum.typ §Regras de projeto):
 * VTOR = c2_vectors; PRIGROUP = 0 (os 4 bits implementados são de grupo,
 * 04-c2.typ §Máscaras e pendência); BASEPRI = 0; FAULTMASK = PRIMASK = 0.
 * Depois valida c2_param e entrega ao despachante do firmware.
 */
#include "c2.h"

__attribute__((section(".noinit"))) c2_param_t c2_param;
uint32_t c2_rec[C2_MAX_POINTS][C2_N_REC];
volatile uint32_t c2_served[C2_N_IRQ];
volatile uint32_t c2_status;

int main(void);

void c2_point(uint32_t id)
{
    (void)id;
}

void c2_done(void)
{
    for (;;) {
    }
}

/* Tratador único das linhas livres: conta o atendimento da linha em
 * execução. Cada elemento de c2_served só é escrito no contexto da própria
 * linha (um escritor por variável). */
void c2_irq_handler(void)
{
    uint32_t line = __get_IPSR() - 16U;
    if (line < C2_N_IRQ) {
        c2_served[line]++;
    }
}

int main(void)
{
    SCB->VTOR = (uint32_t)&c2_vectors;
    NVIC_SetPriorityGrouping(0U);
    __set_BASEPRI(0U);
    __enable_fault_irq();
    __enable_irq();
    __DSB();
    __ISB();

    c2_status = C2_ST_RUNNING;
    if (c2_param.magic != C2_MAGIC || c2_param.n_points == 0U ||
        c2_param.n_points > C2_MAX_POINTS || !c2_run_case(&c2_param)) {
        c2_status = C2_ST_BAD_PARAM;
        c2_done();
    }
    c2_status = C2_ST_DONE;
    c2_done();
}
