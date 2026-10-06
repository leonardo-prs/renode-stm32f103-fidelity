/**
 * @file    src/s1_core.c
 * @brief   S1 — núcleo/memória (cenário 1 da ABI fidelity v1).
 *
 * Mede operações elementares do núcleo com brackets DWT (S1_BEGIN/S1_END) e
 * checksum independente por ensaio. Condições (códigos exatos do contrato
 * RESULT_CONTRACT[1] em scripts/fidelity_analyze.py):
 *   1 empty_bracket — BEGIN/END sem nada entre (custo do observador);
 *   2 alu_dep       — cadeia dependente add/xor/shift (latência);
 *   3 mul           — cadeia MUL/SMULL com operands de runtime;
 *   4 div           — SDIV/UDIV com divisores de runtime não triviais;
 *   5 branch        — padrão de branches dependentes de dados (LCG);
 *   6 sram_rw       — escrita e leitura de buffer estático em SRAM;
 *   7 calibration   — kernel de calibração designado (mix fixo), base da
 *                     futura política "calibrated" de MIPS; mantê-lo estável.
 *
 * Rows (a..f) = expected_checksum, actual_checksum, iterations, 0, 0, 0.
 * expected é calculado por uma referência estruturalmente distinta (ref_*)
 * do kernel medido — um desacordo refuta o ensaio. Kernels são noinline e
 * recebem operands derivados de runtime (volatile/seed) para que o
 * constant-folding não os elimine (gate de disassembly do parent).
 *
 * Trial ids globais 1..28 (4 trials × 7 condições). Trace: 56 + BOOT = 57
 * entradas no canal MAIN (≤128).
 */

#include "board.h"
#include "fidelity.h"

#define S1_TRIALS_PER_COND 4U
#define S1_SEED            123U

/* Operands de runtime: a leitura volatile impede folding fechado. */
static volatile uint32_t s_seed = S1_SEED;
/* Sink de store/load do mix do kernel de calibração. */
static volatile uint32_t s_cal_slot;
/* Buffer estático de SRAM para o ensaio sram_rw (256 B). */
static volatile uint32_t s_buf[64];

/* ───────────────────────── kernels medidos ───────────────────────── */

static __attribute__((noinline)) uint32_t kernel_alu_dep(uint32_t start, uint32_t n)
{
    uint32_t acc = start;
    for (uint32_t i = 0U; i < n; ++i) {
        acc += (i ^ 0xA5A5A5A5U);
        acc = (acc << 5) | (acc >> 27);
        acc ^= (i * 2654435761U);
    }
    return acc;
}

static __attribute__((noinline)) uint32_t kernel_mul(uint32_t start, uint32_t n)
{
    uint32_t acc = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        uint32_t a = start + i;
        uint32_t b = 0x9E3779B1U - i;
        uint32_t u = a * b;                      /* MUL/UMULL */
        int32_t sa = (int32_t)(a & 0x7FFFU) - 0x1000;
        int32_t sb = (int32_t)(b & 0x7FFFU) - 0x1000;
        acc += u ^ (uint32_t)(sa * sb);          /* SMULL */
    }
    return acc;
}

static __attribute__((noinline)) uint32_t kernel_div(uint32_t start, uint32_t n)
{
    uint32_t acc = start;
    for (uint32_t i = 0U; i < n; ++i) {
        uint32_t d = (i * 17U) + 3U;             /* d >= 3, nunca zero */
        uint32_t q = acc / d;                    /* UDIV */
        uint32_t r = acc % d;
        acc = q ^ (r << 8) ^ i;
        int32_t sa = (int32_t)(acc & 0x7FFFU) - 0x1000;
        int32_t sd = (int32_t)(d & 0x7FFFU) | 1; /* ímpar positivo */
        acc += (uint32_t)((sa / sd) * 31);       /* SDIV */
    }
    return acc;
}

static __attribute__((noinline)) uint32_t kernel_branch(uint32_t start, uint32_t n)
{
    uint32_t acc = 0U;
    uint32_t x = start | 1U;
    for (uint32_t i = 0U; i < n; ++i) {
        x = x * 1664525U + 1013904223U;
        if ((x & 0x8000U) != 0U) {
            acc += (x ^ i);
        } else {
            acc -= (x + i);
        }
    }
    return acc;
}

static __attribute__((noinline)) uint32_t kernel_sram_rw(uint32_t start, uint32_t n)
{
    for (uint32_t i = 0U; i < n; ++i) {
        s_buf[i] = (start ^ (i * 2654435761U)) + i;
    }
    uint32_t fold = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        fold = (fold << 1) | (fold >> 31);
        fold ^= s_buf[i];
    }
    return fold;
}

/**
 * @brief Kernel de calibração designado — mix fixo (load, store, alu, mul,
 *        branch taken/not-taken). Congelado: é a base da política MIPS
 *        "calibrated" (validação held-out nos restantes blocos de S1 e S2..S4).
 */
static __attribute__((noinline)) uint32_t calibration_kernel(uint32_t start, uint32_t n)
{
    uint32_t acc = start;
    uint32_t x = start ^ 0x5A5A5A5AU;
    for (uint32_t i = 0U; i < n; ++i) {
        acc += x;                    /* alu */
        s_cal_slot = acc;            /* store */
        acc += s_cal_slot;           /* load */
        acc ^= (x * 9U);             /* mul */
        x = x * 1664525U + 1013904223U;
        if ((x & 0x80U) != 0U) {
            acc += 11U;              /* branch taken */
        } else {
            acc -= 5U;               /* branch not taken */
        }
    }
    return acc;
}

/* ────────────── referências independentes (estrutura distinta) ────────────── */

static uint32_t ref_alu_dep(uint32_t start, uint32_t n)
{
    uint32_t acc = start;
    uint32_t i = 0U;
    while (i < n) {
        uint32_t t = acc + (i ^ 0xA5A5A5A5U);
        uint32_t rot = (t << 5) | (t >> 27);
        acc = rot ^ (i * 2654435761U);
        i += 1U;
    }
    return acc;
}

static uint32_t ref_mul(uint32_t start, uint32_t n)
{
    uint32_t acc = 0U;
    uint32_t i = 0U;
    while (i != n) {
        uint32_t a = start + i;
        uint32_t b = 0x9E3779B1U - i;
        uint32_t u = a * b;
        int32_t sa = (int32_t)(a & 0x7FFFU) - 0x1000;
        int32_t sb = (int32_t)(b & 0x7FFFU) - 0x1000;
        acc = acc + (u ^ (uint32_t)(sa * sb));
        i += 1U;
    }
    return acc;
}

static uint32_t ref_div(uint32_t start, uint32_t n)
{
    uint32_t acc = start;
    uint32_t i = 0U;
    while (i != n) {
        uint32_t d = (i * 17U) + 3U;
        uint32_t q = acc / d;
        uint32_t r = acc % d;
        uint32_t mixed = q ^ (r << 8) ^ i;
        int32_t sa = (int32_t)(mixed & 0x7FFFU) - 0x1000;
        int32_t sd = (int32_t)(d & 0x7FFFU) | 1;
        acc = mixed + (uint32_t)((sa / sd) * 31);
        i += 1U;
    }
    return acc;
}

static uint32_t ref_branch(uint32_t start, uint32_t n)
{
    /* Formulação branchless da mesma matemática do kernel (máscara). */
    uint32_t acc = 0U;
    uint32_t x = start | 1U;
    uint32_t i = 0U;
    while (i < n) {
        x = x * 1664525U + 1013904223U;
        uint32_t mask = 0U - ((x >> 15) & 1U);
        acc = acc + (mask & (x ^ i)) - (~mask & (x + i));
        i += 1U;
    }
    return acc;
}

static uint32_t ref_sram_rw(uint32_t start, uint32_t n)
{
    /* Recalcula o padrão sem tocar no buffer (caminho de memória é o medido). */
    uint32_t fold = 0U;
    uint32_t i = 0U;
    while (i < n) {
        uint32_t val = (start ^ (i * 2654435761U)) + i;
        fold = ((fold << 1) | (fold >> 31)) ^ val;
        i += 1U;
    }
    return fold;
}

static uint32_t ref_calibration(uint32_t start, uint32_t n)
{
    /* Mesmo mix do calibration_kernel, com estrutura de loop distinta. */
    uint32_t acc = start;
    uint32_t x = start ^ 0x5A5A5A5AU;
    uint32_t i = 0U;
    while (i != n) {
        uint32_t t1 = acc + x;
        uint32_t t2 = t1 + t1;                 /* == t1 + s_cal_slot(t1) */
        uint32_t lcg = x * 1664525U + 1013904223U;
        uint32_t t3 = t2 ^ (x * 9U);
        acc = t3 + (((lcg & 0x80U) != 0U) ? 11U : (uint32_t)-5);
        x = lcg;
        i += 1U;
    }
    return acc;
}

/* ───────────────────────── protocolo de ensaios ───────────────────────── */

typedef struct {
    uint32_t condition;
    uint32_t iterations;
    uint32_t (*kernel)(uint32_t, uint32_t);
    uint32_t (*reference)(uint32_t, uint32_t);
} S1Case;

static const S1Case s_cases[6] = {
    { 2U,   256U, kernel_alu_dep,     ref_alu_dep },
    { 3U,   256U, kernel_mul,         ref_mul },
    { 4U,   256U, kernel_div,         ref_div },
    { 5U,   256U, kernel_branch,      ref_branch },
    { 6U,    64U, kernel_sram_rw,     ref_sram_rw },
    { 7U,  1000U, calibration_kernel, ref_calibration },
};

int main(void)
{
    board_init();
    fidelity_init(1U, S1_SEED);

    uint32_t trial = 1U;

    /* Condição 1 — empty_bracket: apenas os brackets, nada entre eles.
     * iterations = 0 e checksums = 0 por definição (custo do observador). */
    for (uint32_t t = 0U; t < S1_TRIALS_PER_COND; ++t) {
        fidelity_trace(FIDELITY_MAIN, FIDELITY_S1_BEGIN, trial, 1U);
        fidelity_trace(FIDELITY_MAIN, FIDELITY_S1_END, trial, 1U);
        fidelity_result(trial, 1U, 0U, 0U, 0U, 0U, 0U, 0U);
        ++trial;
    }

    /* Condições 2..7 — 4 trials cada, trial ids globais 5..28. */
    for (uint32_t ci = 0U; ci < 6U; ++ci) {
        for (uint32_t t = 0U; t < S1_TRIALS_PER_COND; ++t) {
            uint32_t cond = s_cases[ci].condition;
            uint32_t n = s_cases[ci].iterations;
            /* Operands derivados de runtime (anti-fold). */
            uint32_t start = s_seed ^ (trial * 2654435761U) ^ (cond << 16);
            uint32_t expected = s_cases[ci].reference(start, n);
            fidelity_trace(FIDELITY_MAIN, FIDELITY_S1_BEGIN, trial, cond);
            uint32_t actual = s_cases[ci].kernel(start, n);
            fidelity_trace(FIDELITY_MAIN, FIDELITY_S1_END, trial, cond);
            fidelity_result(trial, cond, expected, actual, n, 0U, 0U, 0U);
            ++trial;
        }
    }

    /* Todos os ensaios concluídos: congela o snapshot (DONE). */
    fidelity_finish(0U);
}
