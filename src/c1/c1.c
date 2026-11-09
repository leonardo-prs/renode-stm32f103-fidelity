/*
 * src/c1/c1.c — C1, the core (board oracle, #oP): the SAME binary runs on the
 * board and in Renode, no wire, and the record of both is compared item by item.
 *
 * Points are representative: one per equivalence class or boundary of each
 * operation (ARMv7-M ARM, pseudocode of each instruction). Where the instruction
 * itself, the APSR flags, an unaligned/multi-register addressing mode or an
 * exact cycle window is the object, the sequence is fixed in inline assembly.
 * One case per boot (selected_case); record per case:
 *
 *   1  c1_01_arithmetic        per point: op, a, b, APSR in, result, high word, APSR out
 *   2  c1_02_conversions       per value: SXTB, UXTB, SXTH, UXTH; narrow loads with
 *                              sign/zero extension and truncating stores; per pair:
 *                              APSR after CMP and the mask of the 14 conditions
 *   3  c1_03_memory            words read back (layout in scripts/c1.py)
 *   4  c1_04_timebase          consecutive DWT_CYCCNT reads, counter disabled, DWT × TIM2
 *   5  c1_05_instruction_cost  per window: DWT Δ of its 1st and 2nd execution
 *   6  c1_06_exception_frame   STKALIGN at reset; per point: stack pointers, registers after the return, frame, EXC_RETURN
 *
 * The point tables are repeated in scripts/c1.py, in the same order.
 * Clock: HSI 8 MHz, AHB/APB1/APB2 ÷ 1, flash 0 wait states with prefetch, so one
 * cycle = one tick of DWT_CYCCNT and of TIM2 (PSC = 0). Each case enables only the
 * peripheral clocks it uses, and only c1_04_timebase runs TIM2. No pin is driven:
 * GPIOA stays as input (reset state); c1_05_instruction_cost writes 0 to GPIOA_BSRR,
 * which changes nothing.
 */
#include "case.h"
#include "stm32f1xx.h"
#include "stm32f1xx_ll_bus.h"
#include "stm32f1xx_ll_rcc.h"
#include "stm32f1xx_ll_system.h"
#include "stm32f1xx_ll_tim.h"

extern uint32_t _estack[];

static void exception_frame_handler(void);

__attribute__((section(".isr_vector"), used))
void (*const c1_vectors[16])(void) = {
    (void (*)(void))_estack, Reset_Handler,
    [2 ... 10] = unexpected_exception,
    [11] = exception_frame_handler,             /* only SVC is used */
    [12 ... 15] = unexpected_exception,
};

#define N_OF(a) (sizeof(a) / sizeof((a)[0]))
#define C       0x20000000U     /* APSR.C */
#define V       0x10000000U     /* APSR.V */
#define Q       0x08000000U     /* APSR.Q */
#define NZCV    0xF0000000U

/* ────────────────────── C1-01: c1_01_arithmetic ────────────────────── */

/* One operation: APSR_nzcvq ← flags_in; the instruction; then the flags out. result[0] = low word,
 * result[1] = high word (long multiplies), result[2] = APSR. */
typedef void (*operation_function)(uint32_t first, uint32_t second, uint32_t flags_in, uint32_t result[3]);

#define OPERATION(name, instruction)                                                                \
    static void name(uint32_t first, uint32_t second, uint32_t flags_in, uint32_t result[3])        \
    {                                                                                               \
        uint32_t value, apsr;                                                                       \
        __asm volatile("msr APSR_nzcvq, %[flags_in]\n\t"                                            \
                       instruction " %[value], %[first], %[second]\n\t"                             \
                       "mrs %[apsr], APSR"                                                          \
                       : [value] "=&r"(value), [apsr] "=&r"(apsr)                                   \
                       : [first] "r"(first), [second] "r"(second), [flags_in] "r"(flags_in)         \
                       : "cc");                                                                     \
        result[0] = value;                                                                          \
        result[1] = 0U;                                                                             \
        result[2] = apsr;                                                                           \
    }

#define OPERATION_LONG(name, instruction)                                                           \
    static void name(uint32_t first, uint32_t second, uint32_t flags_in, uint32_t result[3])        \
    {                                                                                               \
        uint32_t low_word, high_word, apsr;                                                         \
        __asm volatile("msr APSR_nzcvq, %[flags_in]\n\t"                                            \
                       instruction " %[low_word], %[high_word], %[first], %[second]\n\t"            \
                       "mrs %[apsr], APSR"                                                          \
                       : [low_word] "=&r"(low_word), [high_word] "=&r"(high_word), [apsr] "=&r"(apsr)\
                       : [first] "r"(first), [second] "r"(second), [flags_in] "r"(flags_in)         \
                       : "cc");                                                                     \
        result[0] = low_word;                                                                       \
        result[1] = high_word;                                                                      \
        result[2] = apsr;                                                                           \
    }

#define OPERATION_SATURATING(name, instruction)                                                     \
    static void name(uint32_t first, uint32_t second, uint32_t flags_in, uint32_t result[3])        \
    {                                                                                               \
        uint32_t value, apsr;                                                                       \
        (void)second;                                                                               \
        __asm volatile("msr APSR_nzcvq, %[flags_in]\n\t"                                            \
                       instruction " %[value], #8, %[first]\n\t"                                    \
                       "mrs %[apsr], APSR"                                                          \
                       : [value] "=&r"(value), [apsr] "=&r"(apsr)                                   \
                       : [first] "r"(first), [flags_in] "r"(flags_in)                               \
                       : "cc");                                                                     \
        result[0] = value;                                                                          \
        result[1] = 0U;                                                                             \
        result[2] = apsr;                                                                           \
    }

OPERATION(operation_adds, "adds")
OPERATION(operation_adcs, "adcs")
OPERATION(operation_subs, "subs")
OPERATION(operation_sbcs, "sbcs")
OPERATION(operation_mul, "mul")
OPERATION_LONG(operation_umull, "umull")
OPERATION_LONG(operation_smull, "smull")
OPERATION(operation_udiv, "udiv")
OPERATION(operation_sdiv, "sdiv")
OPERATION(operation_lsls, "lsls")
OPERATION(operation_lsrs, "lsrs")
OPERATION(operation_asrs, "asrs")
OPERATION(operation_rors, "rors")
OPERATION_SATURATING(operation_ssat, "ssat")
OPERATION_SATURATING(operation_usat, "usat")

/* Order = operation number in the record; the same names are in scripts/c1.py (ARITHMETIC_OPS). */
static const operation_function ARITHMETIC_OPS[] = {
    operation_adds, operation_adcs, operation_subs, operation_sbcs, operation_mul,
    operation_umull, operation_smull, operation_udiv, operation_sdiv, operation_lsls,
    operation_lsrs, operation_asrs, operation_rors, operation_ssat, operation_usat,
};

struct arithmetic_point {
    uint8_t operation;
    uint32_t first, second, flags_in;
};

/* Each point is one equivalence class or boundary of the operation. */
static const struct arithmetic_point ARITHMETIC_POINTS[] = {
    {0, 1U, 2U, 0U},                        /* ADDS: no flag */
    {0, 0x7FFFFFFFU, 1U, 0U},               /* signed overflow: N, V */
    {0, 0xFFFFFFFFU, 1U, 0U},               /* unsigned carry out to zero: Z, C */
    {0, 0x80000000U, 0x80000000U, 0U},      /* both: Z, C, V */
    {0, 1U, 2U, NZCV | Q},                  /* carry in ignored, NZCV rewritten, Q not touched */
    {1, 1U, 2U, 0U},                        /* ADCS: no carry in */
    {1, 1U, 2U, C},                         /* carry in added */
    {1, 0xFFFFFFFFU, 0U, C},                /* carry in propagates to zero: Z, C */
    {1, 0x7FFFFFFFU, 0U, C},                /* carry in overflows: N, V */
    {2, 2U, 1U, 0U},                        /* SUBS: no borrow: C */
    {2, 0U, 1U, 0U},                        /* borrow: N, C = 0 */
    {2, 5U, 5U, 0U},                        /* equal: Z, C */
    {2, 0x80000000U, 1U, 0U},               /* signed overflow: V */
    {3, 5U, 5U, 0U},                        /* SBCS: borrow in (C = 0): −1 */
    {3, 5U, 5U, C},                         /* no borrow in: 0 */
    {4, 0x12345678U, 0x9ABCDEF0U, 0U},      /* MUL: low 32 bits */
    {4, 0x00010000U, 0x00010000U, 0U},      /* 2^32 wraps to 0 */
    {4, 0xFFFFFFFFU, 0xFFFFFFFFU, 0U},      /* (−1)(−1) low word 1 */
    {4, 7U, 7U, NZCV},                      /* no S: NZCV preserved */
    {5, 0xFFFFFFFFU, 0xFFFFFFFFU, 0U},      /* UMULL: largest product */
    {5, 0x80000000U, 2U, 0U},               /* carry into the high word */
    {5, 7U, 7U, NZCV},                      /* NZCV preserved */
    {6, 0xFFFFFFFFU, 0xFFFFFFFFU, 0U},      /* SMULL: (−1)(−1) = 1 */
    {6, 0x80000000U, 0x80000000U, 0U},      /* (−2^31)^2 = 2^62 */
    {6, 0x80000000U, 1U, 0U},               /* sign extension of the high word */
    {7, 7U, 2U, 0U},                        /* UDIV: truncation */
    {7, 0xFFFFFFFFU, 1U, 0U},               /* largest dividend */
    {7, 7U, 0U, 0U},                        /* ÷ 0 = 0 (DIV_0_TRP = 0) */
    {7, 7U, 2U, NZCV},                      /* NZCV preserved */
    {8, 0xFFFFFFF9U, 2U, 0U},               /* SDIV: −7 / 2 = −3 (toward zero) */
    {8, 7U, 0xFFFFFFFEU, 0U},               /* 7 / −2 = −3 */
    {8, 0x80000000U, 0xFFFFFFFFU, 0U},      /* −2^31 / −1 = −2^31 (no trap) */
    {8, 5U, 0U, 0U},                        /* ÷ 0 = 0 */
    {8, 0xFFFFFFF9U, 2U, NZCV},             /* NZCV preserved */
    {9, 0x80000001U, 1U, 0U},               /* LSLS by register: bit out to C */
    {9, 1U, 31U, 0U},                       /* largest in-range shift: N */
    {9, 1U, 32U, 0U},                       /* shift 32: 0, C = bit 0 */
    {9, 1U, 33U, 0U},                       /* shift > 32: 0, C = 0 */
    {9, 1U, 0U, C},                         /* shift 0: C unchanged */
    {9, 1U, 256U, C},                       /* only the low byte counts: shift 0 */
    {9, 1U, 1U, V},                         /* a shift does not touch V */
    {10, 0x80000001U, 1U, 0U},              /* LSRS: bit out to C */
    {10, 0x80000000U, 32U, 0U},             /* shift 32: 0, C = bit 31 */
    {10, 0x80000000U, 33U, 0U},             /* shift > 32: 0, C = 0 */
    {11, 0x80000000U, 31U, 0U},             /* ASRS: sign fills: −1 */
    {11, 0x80000000U, 32U, 0U},             /* shift 32: −1, C = 1 */
    {11, 0x40000000U, 40U, 0U},             /* shift > 32 of a positive: 0 */
    {12, 1U, 1U, 0U},                       /* RORS: bit 0 to bit 31 and C */
    {12, 0x92345678U, 32U, 0U},             /* rotation 32: unchanged, C = bit 31 (not C in) */
    {12, 1U, 33U, 0U},                      /* rotation > 32: by 33 mod 32 */
    {13, 127U, 0U, 0U},                     /* SSAT #8: in range, Q = 0 */
    {13, 128U, 0U, 0U},                     /* above: 127, Q = 1 */
    {13, 0xFFFFFF80U, 0U, 0U},              /* −128 in range */
    {13, 0xFFFFFF7FU, 0U, 0U},              /* −129: −128, Q = 1 */
    {13, 127U, 0U, Q},                      /* in range: Q stays set (cumulative) */
    {13, 128U, 0U, NZCV},                   /* above: Q set, NZCV preserved */
    {14, 255U, 0U, 0U},                     /* USAT #8: in range */
    {14, 256U, 0U, 0U},                     /* above: 255, Q = 1 */
    {14, 0xFFFFFFFFU, 0U, 0U},              /* negative: 0, Q = 1 */
};

static void c1_01_arithmetic(void)
{
    for (uint32_t k = 0U; k < N_OF(ARITHMETIC_POINTS); k++) {
        const struct arithmetic_point *point = &ARITHMETIC_POINTS[k];
        uint32_t result[3];
        ARITHMETIC_OPS[point->operation](point->first, point->second, point->flags_in, result);
        record_value(point->operation);
        record_value(point->first);
        record_value(point->second);
        record_value(point->flags_in);
        record_value(result[0]);
        record_value(result[1]);
        record_value(result[2]);
    }
}

/* ───────────────────── C1-02: c1_02_conversions ───────────────────── */

/* Values at the boundaries of the byte and of the halfword (the bits above are
 * nonzero where it matters, to show they are discarded). */
static const uint32_t EXTENSION_VALUES[] = {
    0x0000007FU, 0x00000080U, 0x123456FFU, 0x00007FFFU, 0x00008000U, 0xABCD8001U,
};

static void extend_register(uint32_t value, uint32_t extended[4])
{
    uint32_t signed_byte, unsigned_byte, signed_halfword, unsigned_halfword;
    __asm volatile("sxtb %[signed_byte], %[value]\n\t"
                   "uxtb %[unsigned_byte], %[value]\n\t"
                   "sxth %[signed_halfword], %[value]\n\t"
                   "uxth %[unsigned_halfword], %[value]"
                   : [signed_byte] "=&r"(signed_byte), [unsigned_byte] "=&r"(unsigned_byte),
                     [signed_halfword] "=&r"(signed_halfword), [unsigned_halfword] "=&r"(unsigned_halfword)
                   : [value] "r"(value));
    extended[0] = signed_byte;
    extended[1] = unsigned_byte;
    extended[2] = signed_halfword;
    extended[3] = unsigned_halfword;
}

/* Bytes read: 7F 80 FF (+3 only aligns the rest) | halfwords (little-endian): 0x8000, 0x7FFF. */
static volatile uint8_t narrow_bytes[8] __attribute__((aligned(4))) = {
    0x7FU, 0x80U, 0xFFU, 0x01U, 0x00U, 0x80U, 0xFFU, 0x7FU,
};
static volatile uint32_t narrow_word;

static void narrow_loads_and_stores(void)
{
    const volatile uint8_t *address = narrow_bytes;
    for (uint32_t offset = 0U; offset < 3U; offset++) {
        uint32_t signed_value, unsigned_value;
        __asm volatile("ldrsb %[signed_value], [%[address], %[offset]]\n\t"
                       "ldrb %[unsigned_value], [%[address], %[offset]]"
                       : [signed_value] "=&r"(signed_value), [unsigned_value] "=&r"(unsigned_value)
                       : [address] "r"(address), [offset] "r"(offset)
                       : "memory");
        record_value(signed_value);
        record_value(unsigned_value);
    }
    for (uint32_t offset = 4U; offset < 8U; offset += 2U) {
        uint32_t signed_value, unsigned_value;
        __asm volatile("ldrsh %[signed_value], [%[address], %[offset]]\n\t"
                       "ldrh %[unsigned_value], [%[address], %[offset]]"
                       : [signed_value] "=&r"(signed_value), [unsigned_value] "=&r"(unsigned_value)
                       : [address] "r"(address), [offset] "r"(offset)
                       : "memory");
        record_value(signed_value);
        record_value(unsigned_value);
    }
    /* Stores that truncate: STRB of 0x12345680 and STRH of 0x1234ABCD into a word of ones. */
    volatile uint32_t *word = &narrow_word;
    *word = 0xFFFFFFFFU;
    __asm volatile("strb %[value], [%[word]]" : : [value] "r"(0x12345680U), [word] "r"(word) : "memory");
    record_value(*word);
    *word = 0xFFFFFFFFU;
    __asm volatile("strh %[value], [%[word]]" : : [value] "r"(0x1234ABCDU), [word] "r"(word) : "memory");
    record_value(*word);
}

/* Pairs (a, b) of CMP a, b: where signed and unsigned order agree, where they
 * disagree (−1 against 1), where the subtraction overflows, and equality. */
static const uint32_t CMP_LEFT[] = {1U, 2U, 0xFFFFFFFFU, 1U, 0x80000000U, 0x7FFFFFFFU, 5U};
static const uint32_t CMP_RIGHT[] = {2U, 1U, 1U, 0xFFFFFFFFU, 0x7FFFFFFFU, 0x80000000U, 5U};

/* Mask of the conditions true after CMP, bit i in this order (also in scripts/c1.py):
 * EQ NE HS LO MI PL VS VC HI LS GE LT GT LE. */
#define CONDITION(condition_code, mask_bit) \
    "it " condition_code "\n\torr" condition_code " %[true_conditions], %[true_conditions], #" mask_bit "\n\t"

static void compare_conditions(uint32_t first, uint32_t second, uint32_t result[2])
{
    uint32_t true_conditions = 0U, apsr;
    __asm volatile("cmp %[first], %[second]\n\t"
                   "mrs %[apsr], APSR\n\t"
                   CONDITION("eq", "1") CONDITION("ne", "2") CONDITION("hs", "4") CONDITION("lo", "8")
                   CONDITION("mi", "16") CONDITION("pl", "32") CONDITION("vs", "64") CONDITION("vc", "128")
                   CONDITION("hi", "256") CONDITION("ls", "512") CONDITION("ge", "1024") CONDITION("lt", "2048")
                   CONDITION("gt", "4096") CONDITION("le", "8192")
                   : [true_conditions] "+r"(true_conditions), [apsr] "=&r"(apsr)
                   : [first] "r"(first), [second] "r"(second)
                   : "cc");
    result[0] = apsr;
    result[1] = true_conditions;
}

static void c1_02_conversions(void)
{
    for (uint32_t k = 0U; k < N_OF(EXTENSION_VALUES); k++) {
        uint32_t extended[4];
        extend_register(EXTENSION_VALUES[k], extended);
        for (uint32_t i = 0U; i < 4U; i++) {
            record_value(extended[i]);
        }
    }
    narrow_loads_and_stores();
    for (uint32_t k = 0U; k < N_OF(CMP_LEFT); k++) {
        uint32_t result[2];
        compare_conditions(CMP_LEFT[k], CMP_RIGHT[k], result);
        record_value(result[0]);
        record_value(result[1]);
    }
}

/* ────────────────────── C1-03: c1_03_memory ────────────────────── */

static volatile uint32_t memory_buffer[8];

static void c1_03_memory(void)
{
    volatile uint32_t *words = memory_buffer;
    volatile uint8_t *bytes = (volatile uint8_t *)memory_buffer;

    /* (a) byte order: a word stored and read back byte by byte. */
    {
        uint32_t byte_0, byte_1, byte_2, byte_3;
        __asm volatile("str %[value], [%[address]]\n\t"
                       "ldrb %[byte_0], [%[address]]\n\t"
                       "ldrb %[byte_1], [%[address], #1]\n\t"
                       "ldrb %[byte_2], [%[address], #2]\n\t"
                       "ldrb %[byte_3], [%[address], #3]"
                       : [byte_0] "=&r"(byte_0), [byte_1] "=&r"(byte_1), [byte_2] "=&r"(byte_2), [byte_3] "=&r"(byte_3)
                       : [value] "r"(0x11223344U), [address] "r"(words)
                       : "memory");
        record_value(byte_0);
        record_value(byte_1);
        record_value(byte_2);
        record_value(byte_3);
    }

    /* (b) narrow stores inside a word: STRB at +1, STRH at +2. */
    {
        uint32_t word;
        __asm volatile("str %[ones], [%[address], #4]\n\t"
                       "strb %[byte_value], [%[address], #5]\n\t"
                       "strh %[halfword_value], [%[address], #6]\n\t"
                       "ldr %[word], [%[address], #4]"
                       : [word] "=&r"(word)
                       : [ones] "r"(0xFFFFFFFFU), [byte_value] "r"(0xAAU), [halfword_value] "r"(0xBBCCU), [address] "r"(words)
                       : "memory");
        record_value(word);
    }

    /* (c) unaligned LDR, LDRH and STR (allowed with UNALIGN_TRP = 0). */
    words[2] = 0x03020100U;
    words[3] = 0x07060504U;
    for (uint32_t offset = 9U; offset < 12U; offset++) {
        uint32_t value;
        __asm volatile("ldr %[value], [%[address], %[offset]]"
                       : [value] "=r"(value)
                       : [address] "r"(bytes), [offset] "r"(offset)
                       : "memory");
        record_value(value);
    }
    for (uint32_t offset = 9U; offset < 12U; offset += 2U) {
        uint32_t value;
        __asm volatile("ldrh %[value], [%[address], %[offset]]"
                       : [value] "=r"(value)
                       : [address] "r"(bytes), [offset] "r"(offset)
                       : "memory");
        record_value(value);
    }
    __asm volatile("str %[value], [%[address], #9]" : : [value] "r"(0xDEADBEEFU), [address] "r"(bytes) : "memory");
    record_value(words[2]);
    record_value(words[3]);

    /* (d) STMIA with writeback and LDMIA: the lowest register goes to the lowest address. */
    {
        uint32_t advanced_address, loaded_r7, loaded_r6, loaded_r5, loaded_r4;
        __asm volatile("mov r4, #0x44\n\t"
                       "mov r5, #0x55\n\t"
                       "mov r6, #0x66\n\t"
                       "mov r7, #0x77\n\t"
                       "mov %[advanced_address], %[address]\n\t"
                       "stmia %[advanced_address]!, {r4-r7}\n\t"
                       "ldmia %[address], {r4-r7}\n\t"
                       "mov %[loaded_r7], r7\n\t"
                       "mov %[loaded_r6], r6\n\t"
                       "mov %[loaded_r5], r5\n\t"
                       "mov %[loaded_r4], r4"
                       : [advanced_address] "=&r"(advanced_address),
                         [loaded_r7] "=&r"(loaded_r7), [loaded_r6] "=&r"(loaded_r6),
                         [loaded_r5] "=&r"(loaded_r5), [loaded_r4] "=&r"(loaded_r4)
                       : [address] "r"(&words[4])
                       : "r4", "r5", "r6", "r7", "memory");
        record_value(advanced_address - (uint32_t)&words[4]);
        for (uint32_t i = 4U; i < 8U; i++) {
            record_value(words[i]);
        }
        record_value(loaded_r7);
        record_value(loaded_r6);
        record_value(loaded_r5);
        record_value(loaded_r4);
    }

    /* (e) PUSH/POP: SP moves 16 bytes; r4 at [SP], r7 at [SP + 12]. */
    {
        uint32_t at_stack_pointer, at_stack_pointer_plus_12, stack_decrease, stack_pointer_after;
        __asm volatile("mov r4, #0x14\n\t"
                       "mov r7, #0x17\n\t"
                       "mov %[stack_decrease], sp\n\t"
                       "push {r4-r7}\n\t"
                       "ldr %[at_stack_pointer], [sp]\n\t"
                       "ldr %[at_stack_pointer_plus_12], [sp, #12]\n\t"
                       "mov %[stack_pointer_after], sp\n\t"
                       "sub %[stack_decrease], %[stack_decrease], %[stack_pointer_after]\n\t"
                       "pop {r4-r7}"
                       : [at_stack_pointer] "=&r"(at_stack_pointer),
                         [at_stack_pointer_plus_12] "=&r"(at_stack_pointer_plus_12),
                         [stack_decrease] "=&r"(stack_decrease),
                         [stack_pointer_after] "=&r"(stack_pointer_after)
                       :
                       : "r4", "r5", "r6", "r7", "memory");
        record_value(stack_decrease);
        record_value(at_stack_pointer);
        record_value(at_stack_pointer_plus_12);
    }

    /* (f) STRD/LDRD: the first register at the lower address. */
    {
        uint32_t first_loaded, second_loaded;
        __asm volatile("strd %[first_stored], %[second_stored], [%[address], #24]\n\t"
                       "ldrd %[first_loaded], %[second_loaded], [%[address], #24]"
                       : [first_loaded] "=&r"(first_loaded), [second_loaded] "=&r"(second_loaded)
                       : [first_stored] "r"(0xA1A2A3A4U), [second_stored] "r"(0xB1B2B3B4U), [address] "r"(words)
                       : "memory");
        record_value(words[6]);
        record_value(words[7]);
        record_value(first_loaded);
        record_value(second_loaded);
    }

    /* (g) pre-indexed with writeback and post-indexed: value and new base. */
    {
        uint32_t pre_indexed_base, pre_indexed_value, post_indexed_base, post_indexed_value;
        words[0] = 0x0000AAAAU;
        words[1] = 0x0000BBBBU;
        __asm volatile("mov %[pre_indexed_base], %[address]\n\t"
                       "ldr %[pre_indexed_value], [%[pre_indexed_base], #4]!\n\t"
                       "mov %[post_indexed_base], %[address]\n\t"
                       "ldr %[post_indexed_value], [%[post_indexed_base]], #4"
                       : [pre_indexed_base] "=&r"(pre_indexed_base), [pre_indexed_value] "=&r"(pre_indexed_value),
                         [post_indexed_base] "=&r"(post_indexed_base), [post_indexed_value] "=&r"(post_indexed_value)
                       : [address] "r"(words)
                       : "memory");
        record_value(pre_indexed_value);
        record_value(pre_indexed_base - (uint32_t)words);
        record_value(post_indexed_value);
        record_value(post_indexed_base - (uint32_t)words);
    }
}

/* ─────────────── measurement windows (C1-04, C1-05) ─────────────── */

/* One window: the body between two reads of DWT_CYCCNT; the result is their difference. What the
 * cost depends on is fixed: the registers (so the encoding, 16-bit forms use r0–r7), the offset of the body in the
 * 64-bit flash line, and the setup, which stays outside the window.
 * r0 = first read, r1 = second read and scratch, r2 = target, r3 = &DWT_CYCCNT, r4–r7 free for the body. */
#define WINDOW(name, offset, setup, target, body)                                                   \
    static uint32_t name(void)                                                                      \
    {                                                                                               \
        register uint32_t time_before __asm("r0");                                                  \
        register uint32_t time_after __asm("r1");                                                   \
        register const volatile void *target_address __asm("r2") = (target);                        \
        register const volatile uint32_t *cycle_counter __asm("r3") = &DWT->CYCCNT;                 \
        __asm volatile(setup ".balign 8\n\t" offset                                                 \
                       "ldr r0, [r3]\n\t" body "ldr r1, [r3]"                                       \
                       : "=&r"(time_before), "=&r"(time_after), "+r"(target_address)                \
                       : "r"(cycle_counter)                                                         \
                       : "cc", "memory", "r4", "r5", "r6", "r7");                                   \
        return time_after - time_before;                                                            \
    }

/* A class is measured at two lengths: (t32 − t16) / 16 is the mean cost of instructions 17 to 32, free
 * of what the neighbouring reads of DWT_CYCCNT add at the ends of the window. */
#define COST(name, offset, setup, target, instruction)                                              \
    WINDOW(window_##name##_16, offset, setup, target, ".rept 16\n\t" instruction "\n\t.endr\n\t")   \
    WINDOW(window_##name##_32, offset, setup, target, ".rept 32\n\t" instruction "\n\t.endr\n\t")

#define AT_LINE_START "nop.n\n\tnop.n\n\tnop.n\n\t"     /* first read at +6, body at the next line */
#define AT_LINE_PLUS_2 ""                               /* first read at +0, body at +2 */

WINDOW(window_empty, AT_LINE_START, "", 0, "")                                       /* two reads, nothing between */
COST(nop, AT_LINE_START, "", 0, "nop.n")                                             /* the base cost, 1 cycle */

/* ───────────────────── C1-04: c1_04_timebase ───────────────────── */

/* TIM2 free-running at f_CK_INT = 8 MHz (PSC = 0), 16 bits. */
static void start_tim2_free_running(void)
{
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    LL_TIM_SetPrescaler(TIM2, 0U);
    LL_TIM_SetAutoReload(TIM2, 0xFFFFU);
    LL_TIM_GenerateEvent_UPDATE(TIM2);          /* loads PSC */
    LL_TIM_EnableCounter(TIM2);
}

/* Four consecutive reads: the interval between pipelined reads, and the counter advances. */
__attribute__((noinline)) static void consecutive_reads(uint32_t intervals[3])
{
    register uint32_t first_read __asm("r0");
    register uint32_t second_read __asm("r1");
    register uint32_t third_read __asm("r2");
    register uint32_t fourth_read __asm("r4");
    register const volatile uint32_t *cycle_counter __asm("r3") = &DWT->CYCCNT;
    __asm volatile(".balign 8\n\t"
                   "ldr r0, [r3]\n\t"
                   "ldr r1, [r3]\n\t"
                   "ldr r2, [r3]\n\t"
                   "ldr r4, [r3]"
                   : "=&r"(first_read), "=&r"(second_read), "=&r"(third_read), "=&r"(fourth_read)
                   : "r"(cycle_counter)
                   : "memory");
    intervals[0] = second_read - first_read;
    intervals[1] = third_read - second_read;
    intervals[2] = fourth_read - third_read;
}

/* One function called at both ends of the interval: the same two instructions at the same address,
 * so equal rates give ΔCNT = ΔDWT. */
__attribute__((noinline)) static void read_dwt_then_tim2(uint32_t readings[2])
{
    register uint32_t time __asm("r0");
    register uint32_t count __asm("r1");
    register const volatile uint32_t *timer_count __asm("r2") = &TIM2->CNT;
    register const volatile uint32_t *cycle_counter __asm("r3") = &DWT->CYCCNT;
    __asm volatile(".balign 8\n\t"
                   "ldr r0, [r3]\n\t"
                   "ldr r1, [r2]"
                   : "=&r"(time), "=&r"(count)
                   : "r"(timer_count), "r"(cycle_counter)
                   : "memory");
    readings[0] = time;
    readings[1] = count;
}

/* DWT × TIM2 waits (cycles): short and close to the 16-bit range of TIM2. */
static const uint32_t TIMEBASE_WAITS[] = {1000U, 50000U};

static void c1_04_timebase(void)
{
    /* (a) consecutive reads. */
    uint32_t intervals[3];
    consecutive_reads(intervals);
    for (uint32_t i = 0U; i < 3U; i++) {
        record_value(intervals[i]);
    }

    /* (b) CYCCNTENA = 0: the counter holds across 16 NOPs; set again, it advances. */
    DWT->CTRL &= ~DWT_CTRL_CYCCNTENA_Msk;
    uint32_t held = window_nop_16();
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    record_value(held);
    record_value(window_nop_16());

    /* (c) DWT and TIM2 over the same interval. */
    start_tim2_free_running();
    for (uint32_t k = 0U; k < N_OF(TIMEBASE_WAITS); k++) {
        uint32_t wait_ticks = TIMEBASE_WAITS[k], start[2], end[2];
        read_dwt_then_tim2(start);
        while (DWT->CYCCNT - start[0] < wait_ticks) {
        }
        read_dwt_then_tim2(end);
        record_value(end[0] - start[0]);
        record_value((end[1] - start[1]) & 0xFFFFU);
    }
}

/* ───────────────── C1-05: c1_05_instruction_cost ───────────────── */

#define LOOP "1:\n\tsubs r1, r1, #1\n\tbne.n 1b\n\t"

#define DIVIDE_BY_ZERO "movs r1, #7\n\tmovs r2, #0\n\t"                              /* ÷ 0: earliest end */
#define LARGEST_QUOTIENT "mov r1, #0xFFFFFFFF\n\tmovs r2, #1\n\t"                    /* largest quotient: latest end */
#define SMALL_OPERANDS "movs r1, #7\n\tmovs r2, #7\n\t"                              /* operands < 64 K: earliest end */
#define LARGEST_OPERANDS "mov r1, #0xFFFFFFFF\n\tmov r2, #0xFFFFFFFF\n\t"            /* largest operands: latest end */
#define ZERO_IN_R1 "movs r1, #0\n\t"

static volatile uint32_t sram_target;
static const uint32_t flash_target = 0x11223344U;
static volatile uint32_t load_multiple_target[4];

/* Each class is one row or note of Cortex-M3 TRM r1p1 §18 (P = pipeline reload) or one access target. */
COST(branch, AT_LINE_START, "", 0, "b.n 1f\n\t1:")                                   /* taken, immediate: 1 + P */
WINDOW(window_loop_16, AT_LINE_START, "movs r1, #16\n\t", 0, LOOP)                   /* the form of a wait loop */
WINDOW(window_loop_32, AT_LINE_START, "movs r1, #32\n\t", 0, LOOP)
COST(ldr_sram, AT_LINE_START, "", &sram_target, "ldr r1, [r2]")                      /* pipelined load (§18.3) */
COST(str_sram, AT_LINE_START, ZERO_IN_R1, &sram_target, "str r1, [r2]")              /* store with offset (§18.3) */
COST(ldrw_sram_word, AT_LINE_START, "", &sram_target, "ldr.w r1, [r2]")              /* 32-bit, word-aligned */
COST(ldrw_sram_halfword, AT_LINE_PLUS_2, "", &sram_target, "ldr.w r1, [r2]")         /* 32-bit, not: fetch boundary */
COST(ldr_flash, AT_LINE_START, "", &flash_target, "ldr r1, [r2]")                    /* data on the instruction memory */
COST(ldr_apb2, AT_LINE_START, "", &GPIOA->IDR, "ldr r1, [r2]")                       /* AHB/APB2 bridge */
COST(str_apb2, AT_LINE_START, ZERO_IN_R1, &GPIOA->BSRR, "str r1, [r2]")              /* BSRR = 0 changes no pin */
COST(ldr_apb1, AT_LINE_START, "", &TIM2->CNT, "ldr r1, [r2]")                        /* AHB/APB1 bridge, counter stopped */
COST(dsb, AT_LINE_START, "", 0, "dsb")                                               /* barrier, nothing pending */
COST(isb, AT_LINE_START, "", 0, "isb")                                               /* barrier that reloads the pipeline */
COST(udiv_min, AT_LINE_START, DIVIDE_BY_ZERO, 0, "udiv r4, r1, r2")                  /* bottom of 2–12 cycles */
COST(udiv_max, AT_LINE_START, LARGEST_QUOTIENT, 0, "udiv r4, r1, r2")                /* top of 2–12 cycles */
COST(umull_min, AT_LINE_START, SMALL_OPERANDS, 0, "umull r4, r5, r1, r2")            /* bottom of 3–5 cycles */
COST(umull_max, AT_LINE_START, LARGEST_OPERANDS, 0, "umull r4, r5, r1, r2")          /* top of 3–5 cycles */
COST(ldm, AT_LINE_START, "", load_multiple_target, "ldmia r2, {r4-r7}")              /* load multiple: 1 + N */
COST(push_pop, AT_LINE_START, "", 0, "push {r4-r7}\n\tpop {r4-r7}")                  /* stack: (1 + N) twice */
/* byte, halfword, byte */
COST(ldr_unaligned_byte, AT_LINE_START, "", (const volatile uint8_t *)load_multiple_target + 1, "ldr r1, [r2]")
/* two halfwords */
COST(ldr_unaligned_halfword, AT_LINE_START, "", (const volatile uint8_t *)load_multiple_target + 2, "ldr r1, [r2]")

#define BOTH_LENGTHS(name) window_##name##_16, window_##name##_32

/* Order = record order; the same classes are in scripts/c1.py (COST_CLASSES). */
static uint32_t (*const COST_SEQUENCES[])(void) = {
    window_empty,
    BOTH_LENGTHS(nop), BOTH_LENGTHS(branch), BOTH_LENGTHS(loop),
    BOTH_LENGTHS(ldr_sram), BOTH_LENGTHS(str_sram),
    BOTH_LENGTHS(ldrw_sram_word), BOTH_LENGTHS(ldrw_sram_halfword),
    BOTH_LENGTHS(ldr_flash), BOTH_LENGTHS(ldr_apb2), BOTH_LENGTHS(str_apb2), BOTH_LENGTHS(ldr_apb1),
    BOTH_LENGTHS(dsb), BOTH_LENGTHS(isb),
    BOTH_LENGTHS(udiv_min), BOTH_LENGTHS(udiv_max), BOTH_LENGTHS(umull_min), BOTH_LENGTHS(umull_max),
    BOTH_LENGTHS(ldm), BOTH_LENGTHS(push_pop),
    BOTH_LENGTHS(ldr_unaligned_byte), BOTH_LENGTHS(ldr_unaligned_halfword),
};

static void c1_05_instruction_cost(void)
{
    /* Only so that the two registers answer: the reads do not depend on a running peripheral. */
    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_GPIOA);
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_TIM2);
    for (uint32_t k = 0U; k < N_OF(COST_SEQUENCES); k++) {
        uint32_t first = COST_SEQUENCES[k]();
        uint32_t second = COST_SEQUENCES[k]();
        record_value(first);
        record_value(second);
    }
}

/* ─────────────────── C1-06: c1_06_exception_frame ─────────────────── */

/* Registers with known values when SVC is taken; the handler reads the frame the hardware
 * stacked and EXC_RETURN. On the main and on the process stack, with SP aligned to 8 or not,
 * with STKALIGN 0 (its reset value in r1p1) and 1. */
#define FRAME_WORDS 8U
#define PROBE_WORDS 8U

/* (use the process stack, SP misaligned, STKALIGN) */
static const uint8_t FRAME_POINTS[][3] = {
    {0U, 0U, 0U}, {0U, 1U, 0U}, {0U, 0U, 1U}, {0U, 1U, 1U},
    {1U, 0U, 0U}, {1U, 1U, 0U}, {1U, 0U, 1U}, {1U, 1U, 1U},
};

static volatile uint32_t frame_on_process_stack;
static volatile uint32_t frame_copy[FRAME_WORDS];
static volatile uint32_t frame_address;
static volatile uint32_t frame_exc_return;

__attribute__((used, noipa)) static void store_frame(uint32_t main_stack, uint32_t process_stack, uint32_t exc_return)
{
    uint32_t address = frame_on_process_stack != 0U ? process_stack : main_stack;
    const uint32_t *frame = (const uint32_t *)address;
    for (uint32_t k = 0U; k < FRAME_WORDS; k++) {
        frame_copy[k] = frame[k];
    }
    frame_address = address;
    frame_exc_return = exc_return;
}

__attribute__((naked, aligned(8))) static void exception_frame_handler(void)
{
    __asm volatile("mrs r0, msp\n\t"
                   "mrs r1, psp\n\t"
                   "mov r2, lr\n\t"
                   "push {r3, lr}\n\t"
                   "bl store_frame\n\t"
                   "pop {r3, lr}\n\t"
                   "bx lr");
}

/* SVC is synchronous, so frame_return_point is exactly the stacked return address.
 * results: SP before, r0–r3, r12, lr and SP after the return. Runs on the stack given,
 * the main stack restored at the end. */
__attribute__((naked, noipa, aligned(8)))
static void take_exception_with_known_registers(__attribute__((unused)) uint32_t stack_top,
                                                __attribute__((unused)) uint32_t use_process_stack,
                                                __attribute__((unused)) uint32_t *results)
{
    __asm volatile("push {r4, r5, r6, r7, lr}\n\t"
                   "mov r4, sp\n\t"
                   "mov r5, r2\n\t"
                   "mrs r6, control\n\t"
                   "cbz r1, 1f\n\t"
                   "msr psp, r0\n\t"
                   "orr.w r7, r6, #2\n\t"
                   "msr control, r7\n\t"
                   "isb\n\t"
                   "b 2f\n\t"
                   "1:\n\t"
                   "mov sp, r0\n\t"
                   "2:\n\t"
                   "mov r7, sp\n\t"
                   "str r7, [r5, #0]\n\t"
                   "ldr r0, =0xA0A0A0A0\n\t"
                   "ldr r1, =0xA1A1A1A1\n\t"
                   "ldr r2, =0xA2A2A2A2\n\t"
                   "ldr r3, =0xA3A3A3A3\n\t"
                   "ldr r12, =0xACACACAC\n\t"
                   "ldr lr, =0xAEAEAEAE\n\t"
                   "svc 0\n\t"
                   "frame_return_point:\n\t"
                   "str r0, [r5, #4]\n\t"
                   "str r1, [r5, #8]\n\t"
                   "str r2, [r5, #12]\n\t"
                   "str r3, [r5, #16]\n\t"
                   "str r12, [r5, #20]\n\t"
                   "str lr, [r5, #24]\n\t"
                   "mov r7, sp\n\t"
                   "str r7, [r5, #28]\n\t"
                   "msr control, r6\n\t"
                   "isb\n\t"
                   "mov sp, r4\n\t"
                   "pop {r4, r5, r6, r7, pc}\n\t"
                   ".ltorg");
}

static void c1_06_exception_frame(void)
{
    __enable_irq();                             /* SVC with PRIMASK = 1 would escalate */
    record_value((SCB->CCR & SCB_CCR_STKALIGN_Msk) >> SCB_CCR_STKALIGN_Pos);
    for (uint32_t k = 0U; k < N_OF(FRAME_POINTS); k++) {
        uint32_t use_process_stack = FRAME_POINTS[k][0];
        uint32_t misaligned = FRAME_POINTS[k][1];
        uint32_t stkalign = FRAME_POINTS[k][2];
        uint32_t results[PROBE_WORDS];
        uint32_t stack_top = ((__get_MSP() - 128U) & ~7U) - (misaligned != 0U ? 4U : 0U);
        if (stkalign != 0U) {
            SCB->CCR |= SCB_CCR_STKALIGN_Msk;
        } else {
            SCB->CCR &= ~SCB_CCR_STKALIGN_Msk;
        }
        __DSB();
        __ISB();
        frame_on_process_stack = use_process_stack;
        take_exception_with_known_registers(stack_top, use_process_stack, results);
        for (uint32_t i = 0U; i < PROBE_WORDS; i++) {
            record_value(results[i]);
        }
        record_value(frame_address);
        record_value(frame_exc_return);
        for (uint32_t i = 0U; i < FRAME_WORDS; i++) {
            record_value(frame_copy[i]);
        }
    }
    SCB->CCR &= ~SCB_CCR_STKALIGN_Msk;
    __disable_irq();
}

/* ───────────────────────────── boot ───────────────────────────── */

static void c1_init(void)
{
    SCB->VTOR = (uint32_t)c1_vectors;
    __disable_irq();
    SCB->CCR &= ~(SCB_CCR_DIV_0_TRP_Msk | SCB_CCR_UNALIGN_TRP_Msk);   /* written explicitly */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_HSI);      /* HSI 8 MHz, written explicitly */
    LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
    LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
    LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
    LL_FLASH_SetLatency(LL_FLASH_LATENCY_0);
    LL_FLASH_EnablePrefetch();
    __DSB();
    __ISB();
}

int main(void)
{
    c1_init();
    switch (selected_case) {
    case 1U: c1_01_arithmetic(); break;
    case 2U: c1_02_conversions(); break;
    case 3U: c1_03_memory(); break;
    case 4U: c1_04_timebase(); break;
    case 5U: c1_05_instruction_cost(); break;
    case 6U: c1_06_exception_frame(); break;
    default: unexpected_exception();
    }
    finish_case();
}
