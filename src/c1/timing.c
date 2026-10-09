/**
 * @file    src/c1/timing.c
 * @brief   C1-timing — duração de cargas C pequenas (bracket DWT em asm).
 *
 * Perguntas:
 *   - a referência nominal de 8 MIPS (1 instrução = 1 ciclo a 8 MHz)
 *     reproduz os tempos de cargas com características diferentes?
 *   - as diferenças entre cargas expõem os limites de um modelo temporal
 *     baseado em contagem de instruções?
 *
 * Cada carga é uma função C `noipa` com assinatura uint32_t f(n, arg), medida
 * por fid_measure() (lib/fidelity_measure.S): o intervalo vai do LDR do
 * CYCCNT antes do BLX até o LDR depois do retorno. Três tamanhos por carga
 * (N_SIZES) permitem verificar linearidade e separar custo por iteração do
 * custo fixo (chamada + bracket). A carga `empty` mede só o custo fixo.
 *
 * Protocolo de repetição: para cada (carga, tamanho) há REPS execuções com
 * ENTRADAS IDÊNTICAS (os vetores de entrada são regenerados antes de cada
 * execução, fora do bracket). A execução 0 é a primeira daquela combinação
 * após o reset; 1..REPS-1 são as seguintes. Nenhum timer, IRQ ou USART fica
 * ligado: o intervalo contém só o código da carga.
 *
 * O caminho executado de cada carga é documentado no README (disassembly
 * conferido no ELF) e contado instrução a instrução pelo traço por stepi do
 * host (scripts/fidelity/instr.py), na placa e no Renode.
 *
 * Registro por caso (uma combinação carga × tamanho):
 *   words = [load_id, n, arg, REPS, {ticks, t0, result} × REPS]
 */
#include "board.h"
#include "fidelity.h"
#include "table.h"

#define FIRMWARE_ID 0x0102U
#define NOIPA __attribute__((noipa))

#define REPS        4U
#define MAX_N       256U
#define SEED        0x2545F491U

enum C1Load {
    LOAD_EMPTY = 0,     /* só chamada + retorno: custo fixo do bracket */
    LOAD_ALU,           /* xorshift32: deslocamentos/XOR em registradores */
    LOAD_MUL,           /* MUL + ADD encadeados */
    LOAD_DIV_SMALL,     /* UDIV com quociente pequeno (dividendo ~ divisor) */
    LOAD_DIV_LARGE,     /* UDIV com quociente grande (dividendo 32 bits, divisor 3) */
    LOAD_SRAM_COPY,     /* LDR/STR de palavras em SRAM */
    LOAD_FLASH_SUM,     /* LDR de palavras da flash (.rodata) */
    LOAD_BRANCH,        /* desvios dependentes de dados */
    LOAD_CRC,           /* CRC-32 bit a bit sobre bytes da flash (carga mista) */
    LOAD_COUNT
};

static const uint32_t SIZES[] = {16U, 64U, 256U};
#define N_SIZES (sizeof(SIZES) / sizeof(SIZES[0]))

/* 1 caso para `empty` + N_SIZES para cada uma das demais cargas. */
#define CASE_COUNT (1U + (LOAD_COUNT - 1U) * N_SIZES)

static uint32_t s_src[MAX_N];
static uint32_t s_dst[MAX_N];

/* ───────────────────────────── cargas ───────────────────────────── */

static NOIPA uint32_t load_empty(uint32_t n, uint32_t arg)
{
    return n ^ arg;
}

static NOIPA uint32_t load_alu(uint32_t n, uint32_t x)
{
    for (uint32_t i = 0U; i < n; ++i) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
    }
    return x;
}

static NOIPA uint32_t load_mul(uint32_t n, uint32_t x)
{
    for (uint32_t i = 0U; i < n; ++i) {
        x = x * 0x01000193U + i;            /* FNV prime; módulo 2^32 */
    }
    return x;
}

/* Mesmas instruções para os dois divisores; só os operandos mudam. */
static NOIPA uint32_t load_div(uint32_t n, uint32_t divisor)
{
    uint32_t acc = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        acc += s_src[i] / divisor;
    }
    return acc;
}

static NOIPA uint32_t load_sram_copy(uint32_t n, uint32_t unused)
{
    (void)unused;
    for (uint32_t i = 0U; i < n; ++i) {
        s_dst[i] = s_src[i] + 1U;           /* +1: impede troca por memcpy */
    }
    return s_dst[n - 1U];
}

static NOIPA uint32_t load_flash_sum(uint32_t n, uint32_t unused)
{
    (void)unused;
    uint32_t sum = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        sum += C1_TABLE[i & (C1_TABLE_WORDS - 1U)];
    }
    return sum;
}

static NOIPA uint32_t load_branch(uint32_t n, uint32_t unused)
{
    (void)unused;
    uint32_t a = 0U;
    uint32_t b = 0U;
    uint32_t c = 0U;
    for (uint32_t i = 0U; i < n; ++i) {
        uint32_t v = s_src[i];
        if ((v & 1U) != 0U) {
            a += v;
        } else if ((v & 2U) != 0U) {
            b ^= v;
        } else {
            c -= v;
        }
    }
    return a ^ b ^ c;
}

static NOIPA uint32_t load_crc(uint32_t n, uint32_t unused)
{
    (void)unused;
    const uint8_t *bytes = (const uint8_t *)C1_TABLE;  /* 256 bytes em flash */
    uint32_t crc = 0xFFFFFFFFU;
    for (uint32_t i = 0U; i < n; ++i) {
        crc ^= bytes[i];
        for (uint32_t bit = 0U; bit < 8U; ++bit) {
            uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1) ^ (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

/* ─────────────────────── entradas e protocolo ─────────────────────── */

typedef struct {
    FidFn fn;
    uint32_t arg;
} Load;

static const Load LOADS[LOAD_COUNT] = {
    [LOAD_EMPTY] = {load_empty, 0x5A5A5A5AU},
    [LOAD_ALU] = {load_alu, SEED},
    [LOAD_MUL] = {load_mul, 0x811C9DC5U},
    [LOAD_DIV_SMALL] = {load_div, 0x00F00000U},
    [LOAD_DIV_LARGE] = {load_div, 3U},
    [LOAD_SRAM_COPY] = {load_sram_copy, 0U},
    [LOAD_FLASH_SUM] = {load_flash_sum, 0U},
    [LOAD_BRANCH] = {load_branch, 0U},
    [LOAD_CRC] = {load_crc, 0U},
};

/* Entradas reproduzíveis: xorshift32 a partir de SEED (o host gera igual).
 * Para LOAD_DIV_SMALL os dividendos ficam em [0x00F00000, 0x01EFFFFF]
 * (quociente 1), para os demais são 32 bits completos. */
static void prepare_inputs(uint32_t load)
{
    uint32_t x = SEED;
    for (uint32_t i = 0U; i < MAX_N; ++i) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        s_src[i] = (load == LOAD_DIV_SMALL) ? (0x00F00000U + (x & 0x00FFFFFFU) % 0x00F00000U) : x;
        s_dst[i] = 0U;
    }
}

/* case_id = load * 16 + índice do tamanho (cabe nos 16 bits do evento). */
static void measure_case(uint32_t load, uint32_t size_index, uint32_t n)
{
    fid_case_begin((load << 4) | size_index);
    fid_put(load);
    fid_put(n);
    fid_put(LOADS[load].arg);
    fid_put(REPS);
    for (uint32_t rep = 0U; rep < REPS; ++rep) {
        FidSpan span;
        prepare_inputs(load);
        uint32_t ticks = fid_measure(LOADS[load].fn, n, LOADS[load].arg, &span);
        fid_put(ticks);
        fid_put(span.t0);
        fid_put(span.result);
    }
    fid_case_end(FID_CASE_OK);
}

int main(void)
{
    board_init();
    fid_init(FIRMWARE_ID, CASE_COUNT);

    measure_case(LOAD_EMPTY, 0U, 0U);
    for (uint32_t load = LOAD_ALU; load < LOAD_COUNT; ++load) {
        for (uint32_t s = 0U; s < N_SIZES; ++s) {
            measure_case(load, s, SIZES[s]);
        }
    }

    fid_finish();
}
