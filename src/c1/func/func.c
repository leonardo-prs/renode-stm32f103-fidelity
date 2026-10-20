/**
 * @file    src/c1/func/func.c
 * @brief   Estado de referência do preset c1-func e sua restauração.
 */
#include "c1.h"
#include "func.h"

#define SHPR ((volatile uint32_t *)0xE000ED18U)   /* SHPR1..SHPR3 */

static uint32_t ref_ccr, ref_shpr[3], ref_shcsr, ref_vtor;

void func_setup(void)
{
    ref_ccr = SCB->CCR;
    for (uint32_t i = 0U; i < 3U; ++i) {
        ref_shpr[i] = SHPR[i];
    }
    ref_shcsr = SCB->SHCSR;
    ref_vtor = SCB->VTOR;
}

void func_restore(void)
{
    __set_BASEPRI(0U);
    __set_FAULTMASK(0U);
    __set_PRIMASK(0U);
    SCB->CCR = ref_ccr;
    for (uint32_t i = 0U; i < 3U; ++i) {
        SHPR[i] = ref_shpr[i];
    }
    SCB->SHCSR = ref_shcsr;
    SCB->VTOR = ref_vtor;
    __DSB();
    __ISB();
}
