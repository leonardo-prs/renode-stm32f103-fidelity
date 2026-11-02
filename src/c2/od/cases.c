/*
 * src/c2/od/cases.c — despachante do firmware #oD do C2 (preset c2-od).
 *
 * Um firmware para todos os casos #oD: o caso e os pontos vêm de c2_param,
 * gravado pelo monitor do Renode antes da partida. Assim, uma campanha usa
 * um único ELF (um SHA-256) para todos os casos e pontos.
 */
#include "c2.h"

bool c2_09_run(uint32_t index, const uint32_t arg[C2_N_ARGS]);

bool c2_run_case(const c2_param_t *p)
{
    bool (*run)(uint32_t, const uint32_t[C2_N_ARGS]);
    switch (p->case_id) {
    case C2_CASE_09:
        run = c2_09_run;
        break;
    default:
        return false;
    }
    for (uint32_t i = 0U; i < p->n_points; i++) {
        if (!run(i, p->arg[i])) {
            return false;
        }
    }
    return true;
}
