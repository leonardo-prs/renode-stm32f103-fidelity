/**
 * @file    src/c1/cycle/main.c
 * @brief   C1 temporal: executa as variantes de um lote e grava os Δ brutos.
 *
 * Para cada variante (caso × operandos), na ordem K, 2K, 3K:
 *   - 1 + R chamadas de cada bloco (a 1ª é a "fria", as R seguintes são as
 *     "quentes"); antes de cada chamada a memória e os registradores são
 *     preparados de novo (setup), fora da janela de medida;
 *   - por fim, o bloco K uma vez mais como BLOCO DE PERFIL: os cinco
 *     contadores de 8 bits do DWT são zerados pela transição 0 → 1 dos bits
 *     *EVTENA e lidos logo depois (diagnóstico na placa; a janela inclui a
 *     chamada, por isso a análise desconta o perfil do bloco vazio).
 *
 * Registro por variante: Δ[3][1 + R] (+ t0/t1 por chamada em C1_V_RAW),
 * depois {Δ do perfil, CPICNT, EXCCNT, SLEEPCNT, LSUCNT, FOLDCNT}.
 *
 * Ambiente: interrupções mascaradas (PRIMASK = 1) durante as medições,
 * exceto nas variantes C1_V_PRIMASK0 (T-DWT-06: com PRIMASK = 1 o SVC
 * escalaria para HardFault); nenhuma fonte de interrupção está habilitada.
 */
#include "c1.h"
#include "c1_catalog.h"

#define DWT_CTRL_REG    (*(volatile uint32_t *)0xE0001000U)
#define DWT_PROF(k)     (*(volatile uint32_t *)(0xE0001008U + 4U * (k)))   /* CPI..FOLD */
#define DWT_EVTENA_ALL  (0x1FU << 17)        /* CPI, EXC, SLEEP, LSU, FOLD EVTENA */
#define SRAM_ALIAS(a, b) (0x22000000U + ((uint32_t)(a) - 0x20000000U) * 32U + (b) * 4U)

_Alignas(32) static uint32_t c1_cell[64];
_Alignas(8) uint32_t c1_cyc_tab[2U * 24U];   /* lido por P_PAIRS (br.S) */
static uint32_t c1_src[24], c1_dst[24];
_Alignas(16) static const uint32_t c1_flash_data[16] = {
    0x11111111U, 0x22222222U, 0x33333333U, 0x44444444U,
    0x55555555U, 0x66666666U, 0x77777777U, 0x88888888U,
    0x99999999U, 0xAAAAAAAAU, 0xBBBBBBBBU, 0xCCCCCCCCU,
    0xDDDDDDDDU, 0xEEEEEEEEU, 0xFFFFFFFFU, 0x01234567U,
};
static uint32_t regs[13];

/* Endereço da 1ª unidade dos blocos cujo alvo de desvio é a unidade seguinte
 * lida da memória (T-BR-09, T-BR-10). */
static uintptr_t first_unit(uint32_t setup, uint32_t k)
{
    static const char *const br09[3] = { t_br09_8_x0, t_br09_16_x0, t_br09_24_x0 };
    static const char *const br10[3] = { t_br10_8_x0, t_br10_16_x0, t_br10_24_x0 };
    return (uintptr_t)(setup == C1_SETUP_LDRPC ? br09[k] : br10[k]);
}

static void setup(const C1Variant *v, uint32_t k)
{
    const uint32_t *src = c1_regs_pool[v->regs[k]];
    for (uint32_t i = 0U; i < 11U; ++i) {
        regs[i] = src[i];
    }
    regs[11] = 0U;
    regs[12] = 0U;
    for (uint32_t i = 0U; i < 64U; ++i) {
        c1_cell[i] = 0x01010101U * i;
    }
    uint32_t n = v->units[k];
    switch (v->setup) {
    case C1_SETUP_CELL:                       /* base na SRAM (+ deslocamento) */
        regs[0] = (uint32_t)(uintptr_t)c1_cell + v->arg;
        break;
    case C1_SETUP_SELF:                       /* ponteiro que aponta para si mesmo */
        c1_cell[0] = (uint32_t)(uintptr_t)&c1_cell[0];
        regs[0] = c1_cell[0];
        break;
    case C1_SETUP_WALK:                       /* writeback percorre 24 palavras */
        regs[0] = (uint32_t)(uintptr_t)c1_cell;
        break;
    case C1_SETUP_LS08A:                      /* r1 recarregado de [r2] = &A */
        c1_cell[1] = (uint32_t)(uintptr_t)&c1_cell[0];
        regs[1] = (uint32_t)(uintptr_t)&c1_cell[0];
        regs[2] = (uint32_t)(uintptr_t)&c1_cell[1];
        break;
    case C1_SETUP_LS08B:
        regs[1] = (uint32_t)(uintptr_t)&c1_cell[0];
        regs[2] = 0U;
        regs[3] = (uint32_t)(uintptr_t)&c1_cell[8] - 20U;
        break;
    case C1_SETUP_LS08C:
        regs[1] = (uint32_t)(uintptr_t)&c1_cell[0];
        regs[2] = 0U;
        regs[3] = (uint32_t)(uintptr_t)&c1_cell[8];
        break;
    case C1_SETUP_LS08D:                      /* r1 ← [r2] = &A; r2 ← [r3 + 4] = &B */
        c1_cell[1] = (uint32_t)(uintptr_t)&c1_cell[0];
        c1_cell[3] = (uint32_t)(uintptr_t)&c1_cell[1];
        regs[1] = (uint32_t)(uintptr_t)&c1_cell[0];
        regs[2] = (uint32_t)(uintptr_t)&c1_cell[1];
        regs[3] = (uint32_t)(uintptr_t)&c1_cell[2];
        break;
    case C1_SETUP_LDRPC: {                    /* alvo k = unidade k + 1 (4 bytes cada) */
        uintptr_t u0 = first_unit(v->setup, k);
        for (uint32_t i = 0U; i < n; ++i) {
            c1_cyc_tab[i] = (uint32_t)(u0 + 4U * (i + 1U)) | 1U;
        }
        regs[0] = (uint32_t)(uintptr_t)c1_cyc_tab;
        break;
    }
    case C1_SETUP_PAIRS: {                    /* pares (r4, PC) de POP {r4, pc}, 2 bytes */
        uintptr_t u0 = first_unit(v->setup, k);
        for (uint32_t i = 0U; i < n; ++i) {
            c1_cyc_tab[2U * i] = 0x5A5A0000U + i;
            c1_cyc_tab[2U * i + 1U] = (uint32_t)(u0 + 2U * (i + 1U)) | 1U;
        }
        break;
    }
    case C1_SETUP_ROM:                        /* base na flash (.rodata) */
        regs[0] = (uint32_t)(uintptr_t)c1_flash_data + v->arg;
        break;
    case C1_SETUP_ALIAS:
        regs[0] = SRAM_ALIAS(&c1_cell[4], 0U);
        regs[1] = 1U;
        break;
    case C1_SETUP_BB3_ALIAS:
        regs[0] = SRAM_ALIAS(&c1_cell[4], 0U);
        regs[1] = 1U;
        regs[3] = (uint32_t)(uintptr_t)&c1_cell[8];
        break;
    case C1_SETUP_BB3_PLAIN:
        regs[0] = (uint32_t)(uintptr_t)&c1_cell[4];
        regs[1] = 1U;
        regs[3] = (uint32_t)(uintptr_t)&c1_cell[8];
        break;
    case C1_SETUP_COPY:
        regs[0] = (uint32_t)(uintptr_t)c1_dst;
        regs[1] = (uint32_t)(uintptr_t)c1_src;
        break;
    default:
        break;
    }
}

static void prefetch(uint32_t on)
{
    if (on) {
        FLASH->ACR |= FLASH_ACR_PRFTBE;
        while ((FLASH->ACR & FLASH_ACR_PRFTBS) == 0U && (FLASH->ACR & FLASH_ACR_PRFTBE) != 0U) {
        }
    } else {
        FLASH->ACR &= ~FLASH_ACR_PRFTBE;
        while ((FLASH->ACR & FLASH_ACR_PRFTBS) != 0U) {
        }
    }
}

static void run_variant(uint32_t idx, uint32_t iters, uint32_t trace)
{
    const C1Variant *v = &c1_variants[idx];
    const C1BlockSet *s = &c1_sets[v->set];

    c1_begin(idx);
    if (v->flags & C1_V_PRIMASK0) {
        __enable_irq();
    }
    if (v->flags & C1_V_CYCOFF) {
        DWT->CTRL &= ~DWT_CTRL_CYCCNTENA_Msk;
    }
    if (v->flags & C1_V_PREFOFF) {
        prefetch(0U);
    }
    for (uint32_t k = 0U; k < 3U; ++k) {
        for (uint32_t it = 0U; it <= iters; ++it) {
            setup(v, k);
            uint32_t d = c1_call((uintptr_t)s->fn[k], (uint32_t)(uintptr_t)regs, 0U);
            c1_put(d);
            if (v->flags & C1_V_RAW) {
                c1_put(regs[11]);
                c1_put(regs[12]);
            }
            if (trace) {
                break;
            }
        }
        if (trace) {
            break;
        }
    }
    if (!trace) {
        setup(v, 0U);
        DWT_CTRL_REG &= ~DWT_EVTENA_ALL;      /* 0 → 1 zera os cinco contadores */
        DWT_CTRL_REG |= DWT_EVTENA_ALL;
        uint32_t d = c1_call((uintptr_t)s->fn[0], (uint32_t)(uintptr_t)regs, 0U);
        uint32_t prof[5];
        for (uint32_t k = 0U; k < 5U; ++k) {
            prof[k] = DWT_PROF(k);
        }
        DWT_CTRL_REG &= ~DWT_EVTENA_ALL;
        c1_put(d);
        for (uint32_t k = 0U; k < 5U; ++k) {
            c1_put(prof[k]);
        }
    }
    if (v->flags & C1_V_PREFOFF) {
        prefetch(1U);
    }
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    __disable_irq();
    c1_end();
}

int main(void)
{
    uint32_t batch = c1_host.batch;
    uint32_t iters = c1_host.iters;
    uint32_t trace = c1_host.flags & C1_HOST_TRACE;
    const C1Batch *b = (batch < C1_N_BATCHES) ? &c1_batches[batch] : 0;

    c1_init(C1_PRESET_CYCLE, C1_CATALOG_HASH, b ? b->count : 0U);
    if (b == 0) {
        c1_fail(C1_ERR_BATCH);
    }
    if (iters > C1_R_MAX) {
        c1_fail(C1_ERR_HOST);
    }
    __disable_irq();
    for (uint32_t i = 0U; i < b->count; ++i) {
        run_variant(c1_items[b->first + i], iters, trace);
    }
    __enable_irq();
    c1_finish();
}
