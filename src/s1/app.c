/**
 * @file    src/s1/app.c
 * @brief   S1B — cargas de aplicação em C (-O2): tempo e resultado funcional.
 *
 * Pergunta: para código "real" compilado, quanto o tempo do Renode (modelo
 * instruções/MIPS) difere do HW, e o desvio é previsível a partir do CPI
 * por classe medido em S1A? (validação held-out da política "calibrated").
 *
 * Cargas (condição): 1 crc32 (bit a bit, 256 B), 2 isort (64 palavras),
 * 3 matmul (8×8 int32), 4 fir (16 taps q15 × 128 amostras), 5 memcpy
 * (palavras, 1 KiB), 6 isqrt (Newton com UDIV, 64 valores), 7 empty (só o
 * bracket: custo do observador).
 * Medição pelo bracket em asm `fidelity_measure` (ordem fixa; com DWT em C
 * o GCC -O2 inferiu as cargas "pure" e moveu a chamada para fora: crc32 =
 * 1 tick). Cargas também `noipa` e chamadas por wrappers de assinatura
 * uniforme (o wrapper — 1 chamada + retorno — entra no bracket, mesmo
 * custo para todas; a carga "empty" mede o bracket + wrapper).
 * Entradas geradas por xorshift32(seed) FORA do bracket; a assinatura de
 * saída é recomputada no host por um oráculo independente (Python).
 *
 * Rows: trial 0 = COLD (1ª execução após reset); trials 1..R = WARM.
 *   v0 = ticks, v1 = assinatura.
 */
#include "board.h"
#include "fidelity.h"

#define S1B_SEED    0x5EED0002U
#define S1B_TRIALS  8U

#define CRC_BYTES   256U
#define SORT_N      64U
#define MAT_N       8U
#define FIR_TAPS    16U
#define FIR_N       128U
#define COPY_WORDS  256U
#define SQRT_N      64U

static volatile uint32_t s_seed = S1B_SEED;
static uint32_t s_rng;

static uint8_t  s_bytes[CRC_BYTES];
static uint32_t s_sort[SORT_N];
static int32_t  s_ma[MAT_N][MAT_N], s_mb[MAT_N][MAT_N], s_mc[MAT_N][MAT_N];
static int16_t  s_x[FIR_N + FIR_TAPS], s_h[FIR_TAPS], s_y[FIR_N];
static uint32_t s_src[COPY_WORDS], s_dst[COPY_WORDS];
static uint32_t s_sq[SQRT_N];

static uint32_t xorshift32(void)
{
    uint32_t x = s_rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    s_rng = x;
    return x;
}

/* ───────────────────────── cargas medidas ───────────────────────── */

static __attribute__((noipa)) uint32_t w_crc32(const uint8_t *p, uint32_t n)
{
    uint32_t crc = 0xFFFFFFFFU;
    for (uint32_t i = 0U; i < n; ++i) {
        crc ^= p[i];
        for (uint32_t b = 0U; b < 8U; ++b) {
            crc = (crc >> 1) ^ (0xEDB88320U & (0U - (crc & 1U)));
        }
    }
    return ~crc;
}

static __attribute__((noipa)) uint32_t w_isort(uint32_t *a, uint32_t n)
{
    for (uint32_t i = 1U; i < n; ++i) {
        uint32_t key = a[i];
        uint32_t j = i;
        while (j > 0U && a[j - 1U] > key) {
            a[j] = a[j - 1U];
            --j;
        }
        a[j] = key;
    }
    uint32_t sig = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        sig = (sig * 31U) + a[i];
    }
    return sig;
}

static __attribute__((noipa)) uint32_t w_matmul(int32_t c[MAT_N][MAT_N],
                                                   int32_t a[MAT_N][MAT_N],
                                                   int32_t b[MAT_N][MAT_N])
{
    uint32_t sig = 0U;
    for (uint32_t i = 0U; i < MAT_N; ++i) {
        for (uint32_t j = 0U; j < MAT_N; ++j) {
            int32_t acc = 0;
            for (uint32_t k = 0U; k < MAT_N; ++k) {
                acc += a[i][k] * b[k][j];
            }
            c[i][j] = acc;
            sig ^= (uint32_t)acc + (i << 8) + j;
        }
    }
    return sig;
}

static __attribute__((noipa)) uint32_t w_fir(int16_t *y, const int16_t *x,
                                                const int16_t *h)
{
    uint32_t sig = 0U;
    for (uint32_t n = 0U; n < FIR_N; ++n) {
        int32_t acc = 0;
        for (uint32_t k = 0U; k < FIR_TAPS; ++k) {
            acc += (int32_t)x[n + k] * (int32_t)h[k];
        }
        y[n] = (int16_t)(acc >> 15);
        sig = (sig << 3) ^ (sig >> 29) ^ (uint16_t)y[n];
    }
    return sig;
}

static __attribute__((noipa)) uint32_t w_memcpy(uint32_t *dst, const uint32_t *src,
                                                   uint32_t n)
{
    for (uint32_t i = 0U; i < n; ++i) {
        dst[i] = src[i];
    }
    return dst[0] ^ dst[n / 2U] ^ dst[n - 1U];
}

static __attribute__((noipa)) uint32_t w_isqrt(const uint32_t *v, uint32_t n)
{
    uint32_t sig = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        uint32_t x = v[i];
        uint32_t r = x;
        if (x > 1U) {
            uint32_t y = (r + x / r) >> 1;
            while (y < r) {
                r = y;
                y = (r + x / r) >> 1;
            }
        }
        sig += r * (i + 1U);
    }
    return sig;
}

/* ───────────────────────── protocolo ───────────────────────── */

static void prepare(uint32_t cond)
{
    switch (cond) {
    case 1U:
        for (uint32_t i = 0U; i < CRC_BYTES; ++i) {
            s_bytes[i] = (uint8_t)xorshift32();
        }
        break;
    case 2U:
        for (uint32_t i = 0U; i < SORT_N; ++i) {
            s_sort[i] = xorshift32();
        }
        break;
    case 3U:
        for (uint32_t i = 0U; i < MAT_N; ++i) {
            for (uint32_t j = 0U; j < MAT_N; ++j) {
                s_ma[i][j] = (int32_t)(xorshift32() & 0xFFFFU) - 0x8000;
                s_mb[i][j] = (int32_t)(xorshift32() & 0xFFFFU) - 0x8000;
            }
        }
        break;
    case 4U:
        for (uint32_t i = 0U; i < FIR_N + FIR_TAPS; ++i) {
            s_x[i] = (int16_t)xorshift32();
        }
        for (uint32_t k = 0U; k < FIR_TAPS; ++k) {
            s_h[k] = (int16_t)(xorshift32() >> 20);    /* |h| < 2^11 */
        }
        break;
    case 5U:
        for (uint32_t i = 0U; i < COPY_WORDS; ++i) {
            s_src[i] = xorshift32();
        }
        break;
    case 6U:
        for (uint32_t i = 0U; i < SQRT_N; ++i) {
            s_sq[i] = xorshift32();
        }
        break;
    default:
        break;
    }
}

/* Pontos de entrada uniformes p/ fidelity_measure: (a, b) ignorados. */
static uint32_t e_crc32(uint32_t a, uint32_t b)  { (void)a; (void)b; return w_crc32(s_bytes, CRC_BYTES); }
static uint32_t e_isort(uint32_t a, uint32_t b)  { (void)a; (void)b; return w_isort(s_sort, SORT_N); }
static uint32_t e_matmul(uint32_t a, uint32_t b) { (void)a; (void)b; return w_matmul(s_mc, s_ma, s_mb); }
static uint32_t e_fir(uint32_t a, uint32_t b)    { (void)a; (void)b; return w_fir(s_y, s_x, s_h); }
static uint32_t e_memcpy(uint32_t a, uint32_t b) { (void)a; (void)b; return w_memcpy(s_dst, s_src, COPY_WORDS); }
static uint32_t e_isqrt(uint32_t a, uint32_t b)  { (void)a; (void)b; return w_isqrt(s_sq, SQRT_N); }
static uint32_t e_empty(uint32_t a, uint32_t b)  { (void)a; (void)b; return 0U; }

static const FidelityFn s_entry[8] = {
    0, e_crc32, e_isort, e_matmul, e_fir, e_memcpy, e_isqrt, e_empty,
};

static void trial(uint32_t trial_id, uint32_t cond)
{
    /* Entradas novas por ensaio (xorshift contínuo, mesma sequência nos 2
     * ambientes) — a assinatura também testa a fidelidade funcional. */
    prepare(cond);
    FidelityMeasure m;
    uint32_t ticks = fidelity_measure(s_entry[cond], 0U, 0U, &m);
    uint32_t sig = m.ret;
    uint32_t t0 = m.t0;
    uint32_t t1 = t0 + ticks;
    fidelity_row(trial_id, cond, ticks, sig, 0U, 0U, 0U, 0U);
    if (trial_id == 1U) {
        fidelity_trace_at(FIDELITY_MAIN, t0, FIDELITY_EV_BEGIN, trial_id, cond);
        fidelity_trace_at(FIDELITY_MAIN, t1, FIDELITY_EV_END, trial_id, cond);
    }
}

int main(void)
{
    board_init();
    fidelity_init(1U, 2U, S1B_SEED);
    s_rng = s_seed;

    for (uint32_t t = 0U; t <= S1B_TRIALS; ++t) {
        for (uint32_t cond = 1U; cond <= 7U; ++cond) {
            trial(t, cond);
        }
    }
    fidelity_finish();
}
