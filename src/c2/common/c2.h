/*
 * src/c2/common/c2.h — interface comum dos firmwares do C2 (04-c2.typ).
 *
 * Contrato com o host (scripts/c2/catalog.py → build/<preset>/gen/c2_catalog.h):
 *   c2_param   gravado pelo monitor com a simulação parada, antes da partida
 *   c2_rec     o que o firmware viu em cada ponto (único escritor: main)
 *   c2_served  atendimentos por linha (único escritor: o tratador da linha)
 *   c2_status  estado de fim (único escritor: main)
 *   c2_point   ponto marcado: o gancho no endereço de c2_point lê o id em R0
 *   c2_done    fim da execução: o gancho lê c2_rec/c2_served/c2_status
 */
#ifndef C2_H
#define C2_H

#include <stdbool.h>
#include <stdint.h>

#include "stm32f1xx.h"
#include "c2_catalog.h"

typedef struct {
    uint32_t magic;                             /* C2_MAGIC */
    uint32_t case_id;                           /* C2_CASE_nn */
    uint32_t n_points;                          /* 1..C2_MAX_POINTS */
    uint32_t reserved;
    uint32_t arg[C2_MAX_POINTS][C2_N_ARGS];     /* argumentos de cada ponto */
} c2_param_t;

typedef void (*c2_handler_t)(void);

typedef struct {
    uint32_t *initial_sp;
    c2_handler_t vector[15U + C2_N_IRQ];        /* exceções 1..15 e IRQ0..IRQ42 */
} c2_vectors_t;

extern const c2_vectors_t c2_vectors;
extern c2_param_t c2_param;
extern uint32_t c2_rec[C2_MAX_POINTS][C2_N_REC];
extern volatile uint32_t c2_served[C2_N_IRQ];
extern volatile uint32_t c2_status;

/* noipa: o compilador não pode remover, fundir nem presumir nada da chamada
 * (o corpo vazio seria tratado como "const" pela análise interprocedural). */
__attribute__((noipa)) void c2_point(uint32_t id);
__attribute__((noipa, noreturn)) void c2_done(void);

void c2_irq_handler(void);
__attribute__((noreturn)) void c2_fault(void);

/* Despachante dos casos do firmware (src/c2/<preset>/cases.c). */
bool c2_run_case(const c2_param_t *p);

/* Janela de espera de n voltas (NOP é volátil: o laço não é removido). */
static inline void c2_spin(uint32_t n)
{
    for (uint32_t i = 0U; i < n; i++) {
        __NOP();
    }
}

static inline uint32_t c2_point_id(uint32_t index, uint32_t phase)
{
    return (index << C2_POINT_SHIFT) | phase;
}

static inline bool c2_line_is_free(uint32_t line)
{
    uint32_t mask = (line < 32U) ? C2_FREE_LINES_MASK0 : C2_FREE_LINES_MASK1;
    return (line < C2_N_IRQ) && ((mask >> (line & 31U)) & 1U) != 0U;
}

#endif
