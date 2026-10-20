/**
 * @file    src/c1/layout/main.c
 * @brief   C1 layout (esqueleto).
 */
#include "c1.h"
#include "c1_catalog.h"

int main(void)
{
    c1_init(C1_PRESET_LAYOUT, C1_CATALOG_HASH, 0U);
    c1_finish();
}
