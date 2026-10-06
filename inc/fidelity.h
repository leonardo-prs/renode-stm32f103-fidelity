#ifndef FIDELITY_H
#define FIDELITY_H

#include <stddef.h>
#include <stdint.h>
#include "fidelity_trace.h"

#define FIDELITY_MAGIC UINT32_C(0x46494431)
#define FIDELITY_VERSION 1U
#define FIDELITY_CORE_HZ 8000000U
#define FIDELITY_RESULT_CAPACITY 128U
#define FIDELITY_ERROR_RESULT_OVERFLOW UINT32_C(0x80000000)

enum FidelityState {
    FIDELITY_INIT = 0,
    FIDELITY_RUNNING = 1,
    FIDELITY_DONE = 2,
    FIDELITY_FAILED = 3
};

/* ABI v1: little-endian uint32 words, no packed/unaligned accesses.
 * Snapshot is immutable after terminal state publication. All consumers
 * must check state, error, bounded counts, drops and counter wrap.
 */
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t scenario;
    uint32_t state;
    uint32_t error;
    uint32_t core_hz;
    uint32_t result_count;
    uint32_t trace_capacity;
    uint32_t result_capacity;
    uint32_t trace_enabled;
    uint32_t seed;
    uint32_t rcc_cr;
    uint32_t rcc_cfgr;
    uint32_t flash_acr;
    uint32_t dwt_ctrl;
    uint32_t prigroup;
    uint32_t trace_count[FIDELITY_WRITER_COUNT];
    uint32_t trace_drop[FIDELITY_WRITER_COUNT];
    uint32_t reserved[10];
} FidelityHeader;

typedef struct {
    FidelityHeader header;
    uint32_t results[FIDELITY_RESULT_CAPACITY][8];
    FidelityTraceEntry trace[FIDELITY_WRITER_COUNT][FIDELITY_TRACE_CAPACITY];
} FidelitySnapshot;

#define FIDELITY_HEADER_OFFSET(field, word) \
    _Static_assert(offsetof(FidelityHeader, field) == (word) * 4U, "header " #field)
FIDELITY_HEADER_OFFSET(magic, 0);
FIDELITY_HEADER_OFFSET(version, 1);
FIDELITY_HEADER_OFFSET(scenario, 2);
FIDELITY_HEADER_OFFSET(state, 3);
FIDELITY_HEADER_OFFSET(error, 4);
FIDELITY_HEADER_OFFSET(core_hz, 5);
FIDELITY_HEADER_OFFSET(result_count, 6);
FIDELITY_HEADER_OFFSET(trace_capacity, 7);
FIDELITY_HEADER_OFFSET(result_capacity, 8);
FIDELITY_HEADER_OFFSET(trace_enabled, 9);
FIDELITY_HEADER_OFFSET(seed, 10);
FIDELITY_HEADER_OFFSET(rcc_cr, 11);
FIDELITY_HEADER_OFFSET(rcc_cfgr, 12);
FIDELITY_HEADER_OFFSET(flash_acr, 13);
FIDELITY_HEADER_OFFSET(dwt_ctrl, 14);
FIDELITY_HEADER_OFFSET(prigroup, 15);
FIDELITY_HEADER_OFFSET(trace_count, 16);
FIDELITY_HEADER_OFFSET(trace_drop, 19);
FIDELITY_HEADER_OFFSET(reserved, 22);
#undef FIDELITY_HEADER_OFFSET
_Static_assert(sizeof(uint32_t) == 4U, "32-bit ABI words");
_Static_assert(sizeof(FidelityHeader) == 128U, "header ABI");
_Static_assert(offsetof(FidelitySnapshot, header) == 0U, "header offset");
_Static_assert(offsetof(FidelitySnapshot, results) == 128U, "results offset");
_Static_assert(sizeof(((FidelitySnapshot *)0)->results) == 4096U, "results ABI");
_Static_assert(offsetof(FidelitySnapshot, trace) == 4224U, "trace offset");
_Static_assert(sizeof(((FidelitySnapshot *)0)->trace) == 6144U, "trace ABI");
_Static_assert(sizeof(FidelitySnapshot) == 10368U, "snapshot ABI");
_Static_assert(offsetof(FidelityTraceEntry, ticks) == 0U, "ticks offset");
_Static_assert(offsetof(FidelityTraceEntry, event) == 4U, "event offset");
_Static_assert(offsetof(FidelityTraceEntry, trial) == 8U, "trial offset");
_Static_assert(offsetof(FidelityTraceEntry, arg) == 12U, "arg offset");
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Fidelity ABI requires little-endian storage"
#endif

_Alignas(16) extern volatile FidelitySnapshot fidelity_snapshot;

/* Call once, with experiment IRQ sources quiescent. Reset DWT before BOOT;
 * do not reset it later. Hardware ticks are core cycles; Renode ticks are
 * virtual-clock ticks, NOT physical microarchitectural cycles. Reading DWT
 * has observer cost and is not assumed to take one cycle.
 */
void fidelity_init(uint32_t scenario, uint32_t seed);
uint32_t fidelity_ticks(void);
void fidelity_trace(uint32_t writer, uint32_t event, uint32_t trial, uint32_t arg);
/* MAIN only, after relevant ISR activity has quiesced. */
void fidelity_result(uint32_t trial, uint32_t condition,
                     uint32_t a, uint32_t b, uint32_t c,
                     uint32_t d, uint32_t e, uint32_t f);
/* Caller must first stop owned peripheral sources. Finish disables IRQs,
 * captures readback and publishes frozen DONE/FAILED before the GDB symbol.
 */
_Noreturn void fidelity_finish(uint32_t error);
_Noreturn void fidelity_complete(void) __attribute__((noinline));

#endif
