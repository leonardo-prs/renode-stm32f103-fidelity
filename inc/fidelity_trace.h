#ifndef FIDELITY_TRACE_H
#define FIDELITY_TRACE_H

#include <stdint.h>

#define FIDELITY_TRACE_CAPACITY 128U
#define FIDELITY_WRITER_COUNT 3U

/* Physical single-writer channels: never swap channels with priority roles.
 * MAIN owns 0, the fixed IRQ_A handler owns 1, IRQ_B owns 2. No reentrant
 * writer, shared head++, IRQ masking, or ring overwrite is permitted.
 * Count publishes an entire entry; drop records capacity exhaustion.
 */
enum FidelityWriter {
    FIDELITY_MAIN = 0,
    FIDELITY_IRQ_A = 1,
    FIDELITY_IRQ_B = 2
};

enum FidelityEvent {
    FIDELITY_BOOT = 1,
    FIDELITY_PHASE = 2,
    FIDELITY_ERROR = 3,
    FIDELITY_S1_BEGIN = 0x100,
    FIDELITY_S1_END = 0x101,
    FIDELITY_S2_ENTER = 0x200,
    FIDELITY_S2_EXIT = 0x201,
    FIDELITY_S2_MASK = 0x202,
    FIDELITY_S2_RELEASE = 0x203,
    FIDELITY_S3_TX = 0x300,
    FIDELITY_S3_RX = 0x301,
    FIDELITY_S3_SR = 0x302,
    FIDELITY_S4_LENTER = 0x400,
    FIDELITY_S4_REQUEST = 0x401,
    FIDELITY_S4_HENTER = 0x402,
    FIDELITY_S4_HEXIT = 0x403,
    FIDELITY_S4_RESUME = 0x404,
    FIDELITY_S4_LEXIT = 0x405,
    FIDELITY_S4_ARB_ENTER = 0x406,
    FIDELITY_S4_ARB_EXIT = 0x407
};

typedef struct {
    uint32_t ticks;
    uint32_t event;
    uint32_t trial;
    uint32_t arg;
} FidelityTraceEntry;

_Static_assert(sizeof(FidelityTraceEntry) == 16U, "trace entry ABI");

#endif
