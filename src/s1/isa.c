/**
 * @file    src/s1/isa.c
 * @brief   S1A — custo por classe de instrução (HW: ciclos; Renode: ticks).
 *
 * Pergunta: quanto tempo cada classe de instrução custa em cada ambiente?
 * Hipótese de modelo (Renode 1.17): tempo virtual = instruções / MIPS, logo
 * com MIPS = 8 e DWT a 8 MHz cada instrução vale ~1 tick, qualquer classe.
 * Referência física: ARM DDI 0337G (Cortex-M3 r2p0) Tabela 18-1 e §18.3.
 *
 * Método (inclinação): cada kernel (isa_kernels.S) roda com N_LO e N_HI
 * iterações; (T(N_HI) − T(N_LO)) / (N_HI − N_LO) = custo por iteração, sem
 * a chamada, o prólogo nem o custo do observador (DWT), que se cancelam.
 * Cada iteração = 16 instruções da classe + SUBS + BNE (s1k_loop: só 2).
 *
 * Rows (2 + 14 + 14×2×4 = 128 = capacidade):
 *   cond 1..14, trial 0     : COLD — 1ª chamada após reset, N_LO iterações;
 *   cond 1..14, trial 1..R  : WARM — v0 = iterações, v1 = ticks, v2 = assinatura.
 *   cond 0 (contexto p/ oráculo do host): trial 0 → ctx[0..5];
 *   trial 1 → ctx[6], ctx[7], *(&palavra em flash).
 * Trace (MAIN): BEGIN/END exatos (fidelity_trace_at) da medição N_HI do
 * trial 1 de cada kernel → spans no Perfetto.
 */
#include "board.h"
#include "fidelity.h"

#define S1A_SEED     0x5EED0001U
#define S1A_TRIALS   4U
#define S1A_N_LO     8U
#define S1A_N_HI     264U

typedef uint32_t (*Kernel)(uint32_t iterations, uint32_t *ctx);

uint32_t s1k_loop(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_alu(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_mul(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_udiv_fast(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_udiv_slow(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_ldr(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_ldr_dep(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_str(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_ldr_flash(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_branch(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_ldm(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_mix(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_alu_ram(uint32_t iterations, uint32_t *ctx);
uint32_t s1k_ldr_ram(uint32_t iterations, uint32_t *ctx);

/* Ordem = código de condição (1..14); espelhada em scripts/fidelity/. */
static const Kernel s_kernels[] = {
    s1k_loop, s1k_alu, s1k_mul, s1k_udiv_fast, s1k_udiv_slow,
    s1k_ldr, s1k_ldr_dep, s1k_str, s1k_ldr_flash, s1k_branch,
    s1k_ldm, s1k_mix, s1k_alu_ram, s1k_ldr_ram,
};
#define S1A_KERNELS (sizeof(s_kernels) / sizeof(s_kernels[0]))

static uint32_t s_ctx[32] __attribute__((aligned(8)));
/* Palavra em FLASH (.rodata) para o kernel LDR-flash. */
static const uint32_t s_flash_word __attribute__((used)) = 0xC0FFEE11U;
/* Semente via volatile: os operandos não são constantes de compilação. */
static volatile uint32_t s_seed = S1A_SEED;

static void ctx_init(void)
{
    uint32_t seed = s_seed;
    s_ctx[0] = (uint32_t)&s_ctx[0];
    s_ctx[1] = seed * 2654435761U;
    s_ctx[2] = (seed ^ 0x9E3779B9U) | 1U;
    s_ctx[3] = 7U + (seed & 1U);            /* dividendo < divisor: rápido */
    s_ctx[4] = 0x10000000U;
    s_ctx[5] = 0xFFFFFFFFU;                 /* quociente máximo: lento */
    s_ctx[6] = 3U;
    s_ctx[7] = (uint32_t)&s_flash_word;
}

static uint32_t measure(Kernel k, uint32_t n, uint32_t *t0_out, uint32_t *sig)
{
    __asm volatile("" ::: "memory");
    uint32_t t0 = fidelity_now();
    uint32_t r = k(n, s_ctx);
    uint32_t t1 = fidelity_now();
    __asm volatile("" ::: "memory");
    *t0_out = t0;
    *sig = r;
    return t1 - t0;
}

int main(void)
{
    board_init();
    fidelity_init(1U, 1U, S1A_SEED);
    ctx_init();

    /* Contexto do oráculo do host: cond 0, trials 0 e 1 (não são ensaios). */
    fidelity_row(0U, 0U, s_ctx[0], s_ctx[1], s_ctx[2], s_ctx[3], s_ctx[4], s_ctx[5]);
    fidelity_row(1U, 0U, s_ctx[6], s_ctx[7], s_flash_word, 0U, 0U, 0U);

    /* COLD: primeira execução de cada kernel após o reset (trial 0). No HW
     * a 1ª chamada de código em FLASH custa ciclos extras determinísticos
     * (diagnóstico 2026-10-07, .slim); no Renode não. Registrada como
     * condição própria, nunca descartada em silêncio. */
    for (uint32_t i = 0U; i < S1A_KERNELS; ++i) {
        uint32_t t0;
        uint32_t sig;
        uint32_t ticks = measure(s_kernels[i], S1A_N_LO, &t0, &sig);
        fidelity_row(0U, i + 1U, S1A_N_LO, ticks, sig, 0U, 0U, 0U);
    }
    for (uint32_t trial = 1U; trial <= S1A_TRIALS; ++trial) {
        for (uint32_t i = 0U; i < S1A_KERNELS; ++i) {
            uint32_t cond = i + 1U;
            for (uint32_t pass = 0U; pass < 2U; ++pass) {
                uint32_t n = (pass == 0U) ? S1A_N_LO : S1A_N_HI;
                uint32_t t0;
                uint32_t sig;
                uint32_t ticks = measure(s_kernels[i], n, &t0, &sig);
                fidelity_row(trial, cond, n, ticks, sig, 0U, 0U, 0U);
                if (trial == 1U && pass == 1U) {
                    fidelity_trace_at(FIDELITY_MAIN, t0, FIDELITY_EV_BEGIN, trial, cond);
                    fidelity_trace_at(FIDELITY_MAIN, t0 + ticks, FIDELITY_EV_END, trial, cond);
                }
            }
        }
    }
    fidelity_finish();
}
