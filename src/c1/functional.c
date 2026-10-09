/**
 * @file    src/c1/functional.c
 * @brief   C1-functional — resultados de operações do núcleo e da memória.
 *
 * Pergunta: o mesmo ELF produz, na placa e no Renode, os resultados e efeitos
 * laterais esperados para operações representativas, em casos normais e de
 * fronteira? (Resultados finais iguais NÃO provam estado intermediário
 * correto após cada instrução; ver o traço de instruções do C1-timing.)
 *
 * Cada caso grava em words[] as ENTRADAS que usou e as SAÍDAS observadas. O
 * host (scripts/fidelity/c1.py) confere as entradas com o plano e recalcula
 * as saídas esperadas com aritmética de largura explícita, sem reutilizar
 * este código. Nada aqui depende de comportamento indefinido em C:
 *   - sem overflow com sinal e sem INT32_MIN / -1;
 *   - deslocamentos sempre com quantidade 0..31;
 *   - casos dependentes da implementação (conversão para tipo com sinal
 *     menor e >> de negativo) seguem a convenção documentada do GCC (módulo
 *     2^N e deslocamento aritmético) e são marcados como tal no host.
 *
 * As operações ficam em funções `noipa`: o GCC não pode propagar as
 * constantes de entrada através da chamada, então a operação é executada
 * pelo núcleo em tempo de execução. Memória testada via ponteiros volatile.
 */
#include <string.h>

#include "board.h"
#include "fidelity.h"
#include "table.h"

#define FIRMWARE_ID 0x0101U

#define NOIPA __attribute__((noipa))
#define COUNT(a) (sizeof(a) / sizeof((a)[0]))

enum C1Case {
    C1_U32_ADD = 1,
    C1_U32_SUB,
    C1_U32_MUL,
    C1_U32_MUL_WIDE,
    C1_U32_DIVREM,
    C1_S32_ADDSUB,
    C1_S32_MUL,
    C1_S32_DIVREM,
    C1_COMPARE,
    C1_BIT_LOGIC,
    C1_SHIFTS,
    C1_ROTATE,
    C1_BITFIELD,
    C1_BITCOUNT,
    C1_PROMOTION,
    C1_CONVERSION,
    C1_U64_OPS,
    C1_SRAM_BYTE_ORDER,
    C1_SRAM_WIDTHS,
    C1_SRAM_PATTERNS,
    C1_SRAM_WALKING,
    C1_FLASH_WORDS,
    C1_FLASH_NARROW,
    C1_COPY_UNALIGNED,
    C1_FILL_REGION,
    C1_SORT16,
    C1_GCD,
    C1_SWITCH,
    C1_RECURSION,
    C1_CASE_COUNT = C1_RECURSION
};

/* ─────────────────────────── entradas ─────────────────────────── */

static const uint32_t U32_PAIRS[][2] = {
    {0x00000000U, 0x00000000U},
    {0x00000001U, 0xFFFFFFFFU},
    {0xFFFFFFFFU, 0xFFFFFFFFU},
    {0x80000000U, 0x80000000U},
    {0x7FFFFFFFU, 0x00000001U},
    {0x12345678U, 0x9ABCDEF0U},
    {0xDEADBEEFU, 0x00010001U},
    {0x0000FFFFU, 0x00010001U},
};

static const uint32_t U32_DIV_PAIRS[][2] = {     /* divisor nunca é zero */
    {0xFFFFFFFFU, 0x00000001U},
    {0xFFFFFFFFU, 0xFFFFFFFFU},
    {0x00000007U, 0x00000003U},
    {0x80000000U, 0x00000002U},
    {0x00000064U, 0x00000007U},
    {0x12345678U, 0x00001000U},
    {0x00000001U, 0xFFFFFFFFU},
    {0xDEADBEEFU, 0x00010001U},
    {0x00000000U, 0x00000007U},
};

static const int32_t S32_ADDSUB_PAIRS[][2] = {   /* a+b e a-b representáveis */
    {INT32_MAX, 0},
    {INT32_MIN, 0},
    {-1, 1},
    {100, -200},
    {INT32_MIN + 5, -5},
    {INT32_MAX - 5, 5},
    {-123456789, 987654321},
};

static const int32_t S32_MUL_PAIRS[][2] = {      /* a*b representável */
    {-3, 7},
    {46340, 46340},
    {-46341, 46340},
    {INT32_MIN, 1},
    {-1, INT32_MAX},
    {0, INT32_MIN},
    {-65536, 32767},
};

static const int32_t S32_DIV_PAIRS[][2] = {      /* b != 0, nunca MIN / -1 */
    {7, 2},
    {-7, 2},
    {7, -2},
    {-7, -2},
    {INT32_MIN, 1},
    {INT32_MIN, 2},
    {INT32_MAX, -1},
    {-1, INT32_MAX},
    {INT32_MIN, INT32_MAX},
    {0, -5},
};

static const uint32_t SHIFT_VALUES[] = {0x80000001U, 0xFFFFFFFFU, 0x12345678U, 0x00000001U};
static const uint32_t SHIFT_AMOUNTS[] = {0U, 1U, 15U, 31U};
static const uint32_t ROTATE_VALUES[] = {0x80000001U, 0x12345678U};
static const uint32_t ROTATE_AMOUNTS[] = {1U, 8U, 31U};

/* Campos de bits {lsb, largura}: largura 1..16, lsb + largura <= 32. */
static const uint32_t FIELDS[][2] = {{0U, 1U}, {4U, 8U}, {31U, 1U}, {16U, 16U}, {3U, 5U}};
#define FIELD_SOURCE 0xDEADBEEFU
#define FIELD_VALUE  0x0000005AU

static const uint32_t BITCOUNT_VALUES[] = {      /* nunca zero (clz/ctz) */
    0x00000001U, 0x80000000U, 0x00010000U, 0xFFFFFFFFU, 0x0F0F0000U, 0x00000300U,
};

static const uint32_t CONVERSION_VALUES[] = {
    0x00000080U, 0x0000FF7FU, 0xFFFF8000U, 0x12345678U, 0x7FFFFFFFU,
};

static const uint32_t U64_PAIRS[][4] = {         /* {a_lo, a_hi, b_lo, b_hi} */
    {0xFFFFFFFFU, 0x00000000U, 0x00000001U, 0x00000000U},
    {0xFFFFFFFFU, 0xFFFFFFFFU, 0x00000002U, 0x00000000U},
    {0x9ABCDEF0U, 0x12345678U, 0x87654321U, 0x0FEDCBA9U},
};

static const uint32_t SORT_INPUT[16] = {
    0xFFFFFFFFU, 0U, 5U, 0x80000000U, 5U, 0x7FFFFFFFU, 1U, 0xFFFFFFFEU,
    42U, 0U, 1000U, 3U, 0x80000001U, 7U, 42U, 2U,
};

static const uint32_t GCD_PAIRS[][2] = {
    {48U, 18U}, {17U, 5U}, {0U, 9U}, {1071U, 462U}, {0xFFFFFFFFU, 0x0000FFFFU},
    {0x80000000U, 0x00100000U},
};

static const uint32_t RECURSION_INPUTS[] = {0U, 1U, 10U, 18U};

/* ───────────────────────── operações (noipa) ───────────────────────── */

typedef uint32_t (*BinaryOp)(uint32_t a, uint32_t b);

static NOIPA uint32_t op_add(uint32_t a, uint32_t b) { return a + b; }
static NOIPA uint32_t op_sub(uint32_t a, uint32_t b) { return a - b; }
static NOIPA uint32_t op_mul(uint32_t a, uint32_t b) { return a * b; }
static NOIPA uint64_t op_mul_wide(uint32_t a, uint32_t b) { return (uint64_t)a * b; }
static NOIPA uint32_t op_udiv(uint32_t a, uint32_t b) { return a / b; }
static NOIPA uint32_t op_urem(uint32_t a, uint32_t b) { return a % b; }
static NOIPA int32_t op_sadd(int32_t a, int32_t b) { return a + b; }
static NOIPA int32_t op_ssub(int32_t a, int32_t b) { return a - b; }
static NOIPA int32_t op_smul(int32_t a, int32_t b) { return a * b; }
static NOIPA int32_t op_sdiv(int32_t a, int32_t b) { return a / b; }
static NOIPA int32_t op_srem(int32_t a, int32_t b) { return a % b; }

/* Reinterpretação de bits uint32 ↔ int32 (memcpy: bem definida em C). */
static uint32_t bits_of(int32_t v)
{
    uint32_t u;
    memcpy(&u, &v, sizeof u);
    return u;
}

static int32_t signed_of(uint32_t u)
{
    int32_t v;
    memcpy(&v, &u, sizeof v);
    return v;
}

static void run_binary(uint32_t case_id, BinaryOp op,
                       const uint32_t pairs[][2], uint32_t count)
{
    fid_case_begin(case_id);
    for (uint32_t i = 0U; i < count; ++i) {
        fid_put(pairs[i][0]);
        fid_put(pairs[i][1]);
        fid_put(op(pairs[i][0], pairs[i][1]));
    }
    fid_case_end(FID_CASE_OK);
}

/* ─────────────────────────── aritmética ─────────────────────────── */

static void case_u32_mul_wide(void)
{
    fid_case_begin(C1_U32_MUL_WIDE);
    for (uint32_t i = 0U; i < COUNT(U32_PAIRS); ++i) {
        uint64_t p = op_mul_wide(U32_PAIRS[i][0], U32_PAIRS[i][1]);
        fid_put(U32_PAIRS[i][0]);
        fid_put(U32_PAIRS[i][1]);
        fid_put((uint32_t)p);
        fid_put((uint32_t)(p >> 32));
    }
    fid_case_end(FID_CASE_OK);
}

static void case_u32_divrem(void)
{
    fid_case_begin(C1_U32_DIVREM);
    for (uint32_t i = 0U; i < COUNT(U32_DIV_PAIRS); ++i) {
        uint32_t a = U32_DIV_PAIRS[i][0];
        uint32_t b = U32_DIV_PAIRS[i][1];
        fid_put(a);
        fid_put(b);
        fid_put(op_udiv(a, b));
        fid_put(op_urem(a, b));
    }
    fid_case_end(FID_CASE_OK);
}

static void case_s32_addsub(void)
{
    fid_case_begin(C1_S32_ADDSUB);
    for (uint32_t i = 0U; i < COUNT(S32_ADDSUB_PAIRS); ++i) {
        int32_t a = S32_ADDSUB_PAIRS[i][0];
        int32_t b = S32_ADDSUB_PAIRS[i][1];
        fid_put(bits_of(a));
        fid_put(bits_of(b));
        fid_put(bits_of(op_sadd(a, b)));
        fid_put(bits_of(op_ssub(a, b)));
    }
    fid_case_end(FID_CASE_OK);
}

static void case_s32_mul(void)
{
    fid_case_begin(C1_S32_MUL);
    for (uint32_t i = 0U; i < COUNT(S32_MUL_PAIRS); ++i) {
        int32_t a = S32_MUL_PAIRS[i][0];
        int32_t b = S32_MUL_PAIRS[i][1];
        fid_put(bits_of(a));
        fid_put(bits_of(b));
        fid_put(bits_of(op_smul(a, b)));
    }
    fid_case_end(FID_CASE_OK);
}

static void case_s32_divrem(void)
{
    fid_case_begin(C1_S32_DIVREM);
    for (uint32_t i = 0U; i < COUNT(S32_DIV_PAIRS); ++i) {
        int32_t a = S32_DIV_PAIRS[i][0];
        int32_t b = S32_DIV_PAIRS[i][1];
        fid_put(bits_of(a));
        fid_put(bits_of(b));
        fid_put(bits_of(op_sdiv(a, b)));     /* C: trunca em direção a zero */
        fid_put(bits_of(op_srem(a, b)));     /* sinal do dividendo */
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t compare_flags(uint32_t a, uint32_t b)
{
    uint32_t flags = 0U;
    flags |= (a < b) ? 1U : 0U;                              /* sem sinal */
    flags |= (signed_of(a) < signed_of(b)) ? 2U : 0U;        /* com sinal */
    flags |= (a == b) ? 4U : 0U;
    flags |= (a >= b) ? 8U : 0U;
    flags |= (signed_of(a) >= signed_of(b)) ? 16U : 0U;
    return flags;
}

static void case_compare(void)
{
    run_binary(C1_COMPARE, compare_flags, U32_PAIRS, COUNT(U32_PAIRS));
}

/* ─────────────────────────────── bits ─────────────────────────────── */

static NOIPA uint32_t op_and(uint32_t a, uint32_t b) { return a & b; }
static NOIPA uint32_t op_or(uint32_t a, uint32_t b) { return a | b; }
static NOIPA uint32_t op_xor(uint32_t a, uint32_t b) { return a ^ b; }
static NOIPA uint32_t op_not(uint32_t a) { return ~a; }
static NOIPA uint32_t op_andn(uint32_t a, uint32_t b) { return a & ~b; }

static void case_bit_logic(void)
{
    fid_case_begin(C1_BIT_LOGIC);
    for (uint32_t i = 0U; i < COUNT(U32_PAIRS); ++i) {
        uint32_t a = U32_PAIRS[i][0];
        uint32_t b = U32_PAIRS[i][1];
        fid_put(a);
        fid_put(b);
        fid_put(op_and(a, b));
        fid_put(op_or(a, b));
        fid_put(op_xor(a, b));
        fid_put(op_not(a));
        fid_put(op_andn(a, b));
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t op_lsl(uint32_t v, uint32_t n) { return v << n; }
static NOIPA uint32_t op_lsr(uint32_t v, uint32_t n) { return v >> n; }
/* >> de valor negativo: definido pela implementação; GCC = aritmético. */
static NOIPA uint32_t op_asr(uint32_t v, uint32_t n) { return bits_of(signed_of(v) >> n); }

static void case_shifts(void)
{
    fid_case_begin(C1_SHIFTS);
    for (uint32_t i = 0U; i < COUNT(SHIFT_VALUES); ++i) {
        for (uint32_t j = 0U; j < COUNT(SHIFT_AMOUNTS); ++j) {
            uint32_t v = SHIFT_VALUES[i];
            uint32_t n = SHIFT_AMOUNTS[j];
            fid_put(v);
            fid_put(n);
            fid_put(op_lsl(v, n));
            fid_put(op_lsr(v, n));
            fid_put(op_asr(v, n));
        }
    }
    fid_case_end(FID_CASE_OK);
}

/* n em 1..31: os dois deslocamentos ficam dentro de 0..31. */
static NOIPA uint32_t op_ror(uint32_t v, uint32_t n) { return (v >> n) | (v << (32U - n)); }
static NOIPA uint32_t op_rol(uint32_t v, uint32_t n) { return (v << n) | (v >> (32U - n)); }

static void case_rotate(void)
{
    fid_case_begin(C1_ROTATE);
    for (uint32_t i = 0U; i < COUNT(ROTATE_VALUES); ++i) {
        for (uint32_t j = 0U; j < COUNT(ROTATE_AMOUNTS); ++j) {
            uint32_t v = ROTATE_VALUES[i];
            uint32_t n = ROTATE_AMOUNTS[j];
            fid_put(v);
            fid_put(n);
            fid_put(op_ror(v, n));
            fid_put(op_rol(v, n));
        }
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t field_extract(uint32_t v, uint32_t lsb, uint32_t width)
{
    uint32_t mask = (1U << width) - 1U;              /* width <= 16 */
    return (v >> lsb) & mask;
}

static NOIPA uint32_t field_extract_signed(uint32_t v, uint32_t lsb, uint32_t width)
{
    uint32_t field = field_extract(v, lsb, width);
    uint32_t sign = 1U << (width - 1U);
    return (field ^ sign) - sign;                    /* extensão de sinal sem UB */
}

static NOIPA uint32_t field_insert(uint32_t dst, uint32_t v, uint32_t lsb, uint32_t width)
{
    uint32_t mask = ((1U << width) - 1U) << lsb;
    return (dst & ~mask) | ((v << lsb) & mask);
}

static void case_bitfield(void)
{
    fid_case_begin(C1_BITFIELD);
    fid_put(FIELD_SOURCE);
    fid_put(FIELD_VALUE);
    for (uint32_t i = 0U; i < COUNT(FIELDS); ++i) {
        uint32_t lsb = FIELDS[i][0];
        uint32_t width = FIELDS[i][1];
        fid_put(lsb);
        fid_put(width);
        fid_put(field_extract(FIELD_SOURCE, lsb, width));
        fid_put(field_extract_signed(FIELD_SOURCE, lsb, width));
        fid_put(field_insert(FIELD_SOURCE, FIELD_VALUE, lsb, width));
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t op_clz(uint32_t v) { return (uint32_t)__builtin_clz(v); }
static NOIPA uint32_t op_ctz(uint32_t v) { return (uint32_t)__builtin_ctz(v); }
static NOIPA uint32_t op_popcount(uint32_t v) { return (uint32_t)__builtin_popcount(v); }

static void case_bitcount(void)
{
    fid_case_begin(C1_BITCOUNT);
    for (uint32_t i = 0U; i < COUNT(BITCOUNT_VALUES); ++i) {
        uint32_t v = BITCOUNT_VALUES[i];
        fid_put(v);
        fid_put(op_clz(v));
        fid_put(op_ctz(v));
        fid_put(op_popcount(v));
    }
    fid_case_end(FID_CASE_OK);
}

/* ───────────────────── promoções e conversões ───────────────────── */

static volatile uint8_t s_u8a = 200U;
static volatile uint8_t s_u8b = 100U;
static volatile uint16_t s_u16 = 0xFFFFU;
static volatile int8_t s_s8 = -128;
static volatile int16_t s_s16 = -32768;

/*
 * Operandos de 8/16 bits são promovidos a int (32 bits) antes da operação
 * (C17 6.3.1.1): a soma 200 + 100 vale 300 e só vira 44 se for convertida
 * de volta para uint8_t. A multiplicação 0xFFFF * 0xFFFF seria overflow de
 * int: por isso o produto é feito explicitamente em uint32_t.
 */
static void case_promotion(void)
{
    uint8_t a = s_u8a;
    uint8_t b = s_u8b;
    uint16_t c = s_u16;
    int8_t e = s_s8;
    int16_t f = s_s16;

    fid_case_begin(C1_PROMOTION);
    fid_put((uint8_t)(a + b));                       /* 44 */
    fid_put((uint32_t)(a + b));                      /* 300 */
    fid_put((a + b) > 255 ? 1U : 0U);                /* 1: comparação em int */
    fid_put((uint16_t)(c + 1U));                     /* 0 */
    fid_put((uint32_t)c * (uint32_t)c);              /* 0xFFFE0001 */
    fid_put(bits_of((int32_t)e));                    /* 0xFFFFFF80 */
    fid_put(bits_of(e * 2));                         /* -256 */
    fid_put(bits_of((int32_t)f));                    /* 0xFFFF8000 */
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t sign_extend8(uint32_t v) { return bits_of((int8_t)(uint8_t)v); }
static NOIPA uint32_t zero_extend8(uint32_t v) { return (uint8_t)v; }
static NOIPA uint32_t sign_extend16(uint32_t v) { return bits_of((int16_t)(uint16_t)v); }
static NOIPA uint32_t zero_extend16(uint32_t v) { return (uint16_t)v; }
static NOIPA uint32_t s64_high(uint32_t v) { return (uint32_t)((uint64_t)(int64_t)signed_of(v) >> 32); }
static NOIPA uint32_t u64_high(uint32_t v) { return (uint32_t)((uint64_t)v >> 32); }
static NOIPA uint32_t negate_to_unsigned(uint32_t v) { return 0U - v; }

/*
 * (int8_t)(uint8_t)v e (int16_t)(uint16_t)v convertem valores fora da faixa
 * do tipo com sinal: resultado definido pela implementação (C17 6.3.1.3);
 * no GCC é a redução módulo 2^N (documentação do GCC, "Integers").
 */
static void case_conversion(void)
{
    fid_case_begin(C1_CONVERSION);
    for (uint32_t i = 0U; i < COUNT(CONVERSION_VALUES); ++i) {
        uint32_t v = CONVERSION_VALUES[i];
        fid_put(v);
        fid_put(sign_extend8(v));
        fid_put(zero_extend8(v));
        fid_put(sign_extend16(v));
        fid_put(zero_extend16(v));
        fid_put(s64_high(v));
        fid_put(u64_high(v));
        fid_put(negate_to_unsigned(v));
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint64_t u64_add(uint64_t a, uint64_t b) { return a + b; }
static NOIPA uint64_t u64_sub(uint64_t a, uint64_t b) { return a - b; }
static NOIPA uint64_t u64_mul(uint64_t a, uint64_t b) { return a * b; }
static NOIPA uint64_t u64_div(uint64_t a, uint64_t b) { return a / b; }

static void put_u64(uint64_t v)
{
    fid_put((uint32_t)v);
    fid_put((uint32_t)(v >> 32));
}

static void case_u64_ops(void)
{
    fid_case_begin(C1_U64_OPS);
    for (uint32_t i = 0U; i < COUNT(U64_PAIRS); ++i) {
        uint64_t a = ((uint64_t)U64_PAIRS[i][1] << 32) | U64_PAIRS[i][0];
        uint64_t b = ((uint64_t)U64_PAIRS[i][3] << 32) | U64_PAIRS[i][2];
        put_u64(a);
        put_u64(b);
        put_u64(u64_add(a, b));
        put_u64(u64_sub(a, b));
        put_u64(u64_mul(a, b));
        put_u64(u64_div(a, b));                      /* b != 0 */
    }
    fid_case_end(FID_CASE_OK);
}

/* ─────────────────────────────── SRAM ─────────────────────────────── */

static volatile uint32_t s_sram[64];

static void case_sram_byte_order(void)
{
    volatile uint8_t *bytes = (volatile uint8_t *)&s_sram[0];
    volatile uint16_t *halves = (volatile uint16_t *)&s_sram[0];

    s_sram[0] = 0x11223344U;
    fid_case_begin(C1_SRAM_BYTE_ORDER);
    fid_put(bytes[0]);
    fid_put(bytes[1]);
    fid_put(bytes[2]);
    fid_put(bytes[3]);
    fid_put(halves[0]);
    fid_put(halves[1]);
    fid_case_end(FID_CASE_OK);
}

/* Escritas de 8/16/32 bits em posições alinhadas de um bloco pré-preenchido:
 * o host confere os 16 bytes, inclusive os vizinhos que não podiam mudar. */
static void case_sram_widths(void)
{
    volatile uint8_t *bytes = (volatile uint8_t *)&s_sram[0];
    volatile uint16_t *halves = (volatile uint16_t *)&s_sram[0];

    for (uint32_t i = 0U; i < 4U; ++i) {
        s_sram[i] = 0xEEEEEEEEU;
    }
    bytes[1] = 0xA1U;
    halves[3] = 0xB2C3U;                             /* bytes 6..7 */
    s_sram[2] = 0xD4E5F607U;                         /* bytes 8..11 */
    bytes[15] = 0x08U;

    fid_case_begin(C1_SRAM_WIDTHS);
    for (uint32_t i = 0U; i < 4U; ++i) {
        fid_put(s_sram[i]);
    }
    fid_put(bytes[1]);
    fid_put(halves[3]);
    fid_put(bytes[15]);
    fid_case_end(FID_CASE_OK);
}

static void case_sram_patterns(void)
{
    static const uint32_t patterns[] = {0x00000000U, 0xFFFFFFFFU, 0xAAAAAAAAU, 0x55555555U};

    fid_case_begin(C1_SRAM_PATTERNS);
    for (uint32_t p = 0U; p < COUNT(patterns); ++p) {
        for (uint32_t i = 0U; i < 16U; ++i) {
            s_sram[i] = patterns[p];
        }
        for (uint32_t i = 0U; i < 16U; ++i) {
            fid_put(s_sram[i]);
        }
    }
    fid_case_end(FID_CASE_OK);
}

static void case_sram_walking(void)
{
    for (uint32_t i = 0U; i < 32U; ++i) {
        s_sram[i] = 1U << i;                         /* um bit em 1 */
        s_sram[32U + i] = ~(1U << i);                /* um bit em 0 */
    }
    fid_case_begin(C1_SRAM_WALKING);
    for (uint32_t i = 0U; i < 64U; ++i) {
        fid_put(s_sram[i]);
    }
    fid_case_end(FID_CASE_OK);
}

/* ─────────────────────────────── flash ─────────────────────────────── */

static void case_flash_words(void)
{
    const volatile uint32_t *table = C1_TABLE;

    fid_case_begin(C1_FLASH_WORDS);
    fid_put((uint32_t)(uintptr_t)C1_TABLE);         /* host confere: na flash */
    for (uint32_t i = 0U; i < C1_TABLE_WORDS; ++i) {
        fid_put(table[i]);
    }
    fid_case_end(FID_CASE_OK);
}

/* Leituras de 8/16 bits, com e sem extensão de sinal (LDRB/LDRSB/LDRH/LDRSH). */
static void case_flash_narrow(void)
{
    const volatile uint8_t *u8 = (const volatile uint8_t *)C1_TABLE;
    const volatile int8_t *s8 = (const volatile int8_t *)C1_TABLE;
    const volatile uint16_t *u16 = (const volatile uint16_t *)C1_TABLE;
    const volatile int16_t *s16 = (const volatile int16_t *)C1_TABLE;

    fid_case_begin(C1_FLASH_NARROW);
    for (uint32_t i = 0U; i < 8U; ++i) {
        fid_put(u8[i]);
        fid_put(bits_of(s8[i]));
    }
    for (uint32_t i = 0U; i < 4U; ++i) {
        fid_put(u16[i]);
        fid_put(bits_of(s16[i]));
    }
    fid_case_end(FID_CASE_OK);
}

/* ─────────────────────── cópia e preenchimento ─────────────────────── */

#define BLOCK_BYTES 64U
static uint8_t s_block[BLOCK_BYTES] __attribute__((aligned(4)));

static NOIPA void copy_bytes(uint8_t *dst, const uint8_t *src, uint32_t n)
{
    for (uint32_t i = 0U; i < n; ++i) {
        dst[i] = src[i];
    }
}

static NOIPA void fill_bytes(uint8_t *dst, uint8_t value, uint32_t n)
{
    for (uint32_t i = 0U; i < n; ++i) {
        dst[i] = value;
    }
}

/* Lê o bloco inteiro como palavras (o host confere os 64 bytes). */
static void put_block(void)
{
    const volatile uint32_t *words = (const volatile uint32_t *)s_block;
    for (uint32_t i = 0U; i < BLOCK_BYTES / 4U; ++i) {
        fid_put(words[i]);
    }
}

/* 37 bytes da tabela em flash (a partir do byte 1) para s_block[3..39]. */
static void case_copy_unaligned(void)
{
    fill_bytes(s_block, 0xEEU, BLOCK_BYTES);
    copy_bytes(&s_block[3], (const uint8_t *)C1_TABLE + 1, 37U);
    fid_case_begin(C1_COPY_UNALIGNED);
    put_block();
    fid_case_end(FID_CASE_OK);
}

static void case_fill_region(void)
{
    fill_bytes(s_block, 0xEEU, BLOCK_BYTES);
    fill_bytes(&s_block[5], 0x3CU, 38U);
    fid_case_begin(C1_FILL_REGION);
    put_block();
    fid_case_end(FID_CASE_OK);
}

/* ───────────────────────── pequenos algoritmos ───────────────────────── */

static uint32_t s_sort[16];

static NOIPA void insertion_sort(uint32_t *a, uint32_t n)
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
}

static void case_sort16(void)
{
    for (uint32_t i = 0U; i < 16U; ++i) {
        s_sort[i] = SORT_INPUT[i];
    }
    insertion_sort(s_sort, 16U);
    fid_case_begin(C1_SORT16);
    for (uint32_t i = 0U; i < 16U; ++i) {
        fid_put(((volatile uint32_t *)s_sort)[i]);
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t gcd(uint32_t a, uint32_t b)
{
    while (b != 0U) {
        uint32_t r = a % b;
        a = b;
        b = r;
    }
    return a;
}

static void case_gcd(void)
{
    run_binary(C1_GCD, gcd, GCD_PAIRS, COUNT(GCD_PAIRS));
}

/* switch denso: o GCC gera tabela de salto (TBB) — controle indireto. */
static NOIPA uint32_t dispatch(uint32_t k)
{
    switch (k) {
    case 0U: return 0x10U;
    case 1U: return 0x21U;
    case 2U: return 0x32U;
    case 3U: return 0x43U;
    case 4U: return 0x54U;
    case 5U: return 0x65U;
    case 6U: return 0x76U;
    case 7U: return 0x87U;
    case 8U: return 0x98U;
    case 9U: return 0xA9U;
    default: return 0xFFFFFFFFU;
    }
}

static void case_switch(void)
{
    fid_case_begin(C1_SWITCH);
    for (uint32_t k = 0U; k < 12U; ++k) {
        fid_put(k);
        fid_put(dispatch(k));
    }
    fid_case_end(FID_CASE_OK);
}

static NOIPA uint32_t fibonacci(uint32_t n)
{
    return (n < 2U) ? n : fibonacci(n - 1U) + fibonacci(n - 2U);
}

static void case_recursion(void)
{
    fid_case_begin(C1_RECURSION);
    for (uint32_t i = 0U; i < COUNT(RECURSION_INPUTS); ++i) {
        fid_put(RECURSION_INPUTS[i]);
        fid_put(fibonacci(RECURSION_INPUTS[i]));
    }
    fid_case_end(FID_CASE_OK);
}

/* ─────────────────────────────── main ─────────────────────────────── */

int main(void)
{
    board_init();
    fid_init(FIRMWARE_ID, C1_CASE_COUNT);

    run_binary(C1_U32_ADD, op_add, U32_PAIRS, COUNT(U32_PAIRS));
    run_binary(C1_U32_SUB, op_sub, U32_PAIRS, COUNT(U32_PAIRS));
    run_binary(C1_U32_MUL, op_mul, U32_PAIRS, COUNT(U32_PAIRS));
    case_u32_mul_wide();
    case_u32_divrem();
    case_s32_addsub();
    case_s32_mul();
    case_s32_divrem();
    case_compare();
    case_bit_logic();
    case_shifts();
    case_rotate();
    case_bitfield();
    case_bitcount();
    case_promotion();
    case_conversion();
    case_u64_ops();
    case_sram_byte_order();
    case_sram_widths();
    case_sram_patterns();
    case_sram_walking();
    case_flash_words();
    case_flash_narrow();
    case_copy_unaligned();
    case_fill_region();
    case_sort16();
    case_gcd();
    case_switch();
    case_recursion();

    fid_finish();
}
