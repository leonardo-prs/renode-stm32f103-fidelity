/**
 * @file    src/c1/func/func.h
 * @brief   Estado comum do preset c1-func (ver func.c).
 */
#ifndef C1_FUNC_H
#define C1_FUNC_H

#include <stdint.h>

/** Janela de memória dos casos F_MEM (32 B, alinhada a 16). */
extern volatile uint32_t c1_scratch[];

/** Grava o estado de referência do SCB (depois de c1_init). */
void func_setup(void);

/**
 * Restaura, depois de cada vetor, o estado global que um caso pode ter
 * mudado de propósito (CCR, prioridades, máscaras, CONTROL, SHCSR, VTOR):
 * as prioridades e os traps são PRECONDIÇÃO declarada só do caso que os usa
 * (material-base, "Prioridades como precondição").
 */
void func_restore(void);

#endif /* C1_FUNC_H */
