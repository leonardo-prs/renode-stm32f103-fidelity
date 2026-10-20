/**
 * @file    src/c1/cycle/main.c
 * @brief   C1 cycle (esqueleto).
 */
#include "c1.h"
#include "c1_catalog.h"

int main(void)
{
    c1_init(C1_PRESET_CYCLE, C1_CATALOG_HASH, 0U);
    c1_finish();
}
