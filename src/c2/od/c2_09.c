/*
 * src/c2/od/c2_09.c — C2-09: interrupção desabilitada no NVIC recebe pedido
 * por software; depois é habilitada (04-c2.typ, ARM ARM §B3.4.1).
 *
 * Um ponto = (linha livre, mecanismo do pedido: STIR ou ISPR). Três pontos
 * marcados por ponto do caso, em que o gancho lê o estado do NVIC de fora:
 *   ARMED    linha desabilitada, pendência limpa (estado inicial)
 *   PENDING  depois do pedido com a linha desabilitada e de uma janela
 *   SERVED   depois de habilitar a linha e de uma janela
 * O firmware também grava o que ele próprio vê (pendência lida no ISPR e o
 * contador de atendimentos da linha) antes de cada ponto: é o que o código
 * de um usuário veria, e serve de conferência cruzada com o observador
 * externo. Barreiras DSB+ISB depois de cada escrita no NVIC, como a ARM
 * recomenda para que o efeito valha nas instruções seguintes.
 */
#include "c2.h"

bool c2_09_run(uint32_t index, const uint32_t arg[C2_N_ARGS]);

static void c2_09_sample(uint32_t *rec, uint32_t k_pend, uint32_t k_served, uint32_t line)
{
    rec[k_pend] = NVIC_GetPendingIRQ((IRQn_Type)line);
    rec[k_served] = c2_served[line];
}

bool c2_09_run(uint32_t index, const uint32_t arg[C2_N_ARGS])
{
    const uint32_t line = arg[0];
    const uint32_t mech = arg[1];
    if (!c2_line_is_free(line) || (mech != C2_MECH_STIR && mech != C2_MECH_ISPR)) {
        return false;
    }
    const IRQn_Type irq = (IRQn_Type)line;
    uint32_t *rec = c2_rec[index];

    NVIC_DisableIRQ(irq);
    NVIC_ClearPendingIRQ(irq);
    NVIC_SetPriority(irq, C2_09_PRIO);
    __DSB();
    __ISB();
    c2_09_sample(rec, C2_09_REC_PEND_ARMED, C2_09_REC_SERVED_ARMED, line);
    c2_point(c2_point_id(index, C2_09_ARMED));

    if (mech == C2_MECH_STIR) {
        NVIC->STIR = line;
    } else {
        NVIC_SetPendingIRQ(irq);                /* ISPR[line / 32] = 1 << (line % 32) */
    }
    __DSB();
    __ISB();
    c2_spin(C2_09_WINDOW);
    c2_09_sample(rec, C2_09_REC_PEND_PENDING, C2_09_REC_SERVED_PENDING, line);
    c2_point(c2_point_id(index, C2_09_PENDING));

    NVIC_EnableIRQ(irq);
    __DSB();
    __ISB();
    c2_spin(C2_09_WINDOW);
    c2_09_sample(rec, C2_09_REC_PEND_SERVED, C2_09_REC_SERVED_SERVED, line);
    c2_point(c2_point_id(index, C2_09_SERVED));

    NVIC_DisableIRQ(irq);
    return true;
}
