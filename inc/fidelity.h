/**
 * @file    inc/fidelity.h
 * @brief   ABI v2 do snapshot de fidelidade (HW × Renode).
 *
 * Um firmware final = um experimento finito. Ele escreve resultados em UM
 * objeto global (`fidelity_snapshot`), congela-o em `fidelity_finish()` e
 * para em `fidelity_complete()`, onde o coletor (GDB) faz o dump binário.
 * O mesmo ELF roda na bancada e no Renode; só o ambiente muda.
 *
 * Layout (little-endian, só uint32_t, sem packed):
 *   header  : 32 words (128 B)
 *   rows    : [FIDELITY_ROWS][8]  — {trial, condition, v0..v5}
 *   trace   : [3][FIDELITY_TRACE] — {ticks, event, trial, arg}
 * As capacidades vão no header; o decodificador nunca as presume.
 *
 * Domínios de tempo: `ticks` = DWT->CYCCNT. No HW são ciclos do núcleo
 * (HCLK = HSI). No Renode são ticks de um contador derivado do TEMPO
 * VIRTUAL (frequency 8 MHz no .repl) — não ciclos microarquiteturais.
 */
#ifndef FIDELITY_H
#define FIDELITY_H

#include <stddef.h>
#include <stdint.h>
#include "stm32f1xx.h"

#ifndef FIDELITY_ROWS
#define FIDELITY_ROWS 128U
#endif
#ifndef FIDELITY_TRACE
#define FIDELITY_TRACE 128U
#endif

#define FIDELITY_MAGIC   UINT32_C(0x46494432)   /* "FID2" */
#define FIDELITY_VERSION 2U
#define FIDELITY_CORE_HZ 8000000U
#define FIDELITY_WRITERS 3U

/* Bits de erro (header.error). Valores < 0x10000 são livres p/ o cenário. */
#define FIDELITY_ERR_ROWS_FULL  UINT32_C(0x80000000)
#define FIDELITY_ERR_TIMEOUT    UINT32_C(0x40000000)
#define FIDELITY_ERR_CHECK      UINT32_C(0x20000000)

enum FidelityState {
    FIDELITY_INIT = 0,
    FIDELITY_RUNNING = 1,
    FIDELITY_DONE = 2,
    FIDELITY_FAILED = 3
};

/* Canais físicos de escrita: um escritor por canal, fixo ao contexto
 * (MAIN, ou um handler específico). Nunca roteado por papel/prioridade. */
enum FidelityWriter {
    FIDELITY_MAIN = 0,
    FIDELITY_IRQ_A = 1,
    FIDELITY_IRQ_B = 2
};

/* Eventos genéricos; cada cenário define os seus a partir de 0x100*N. */
enum FidelityEvent {
    FIDELITY_EV_BOOT = 1,
    FIDELITY_EV_BEGIN = 2,     /* arg = condição */
    FIDELITY_EV_END = 3        /* arg = condição */
};

typedef struct {
    uint32_t ticks;
    uint32_t event;
    uint32_t trial;
    uint32_t arg;
} FidelityTraceEntry;

typedef struct {
    uint32_t magic;            /*  0 */
    uint32_t version;          /*  1 */
    uint32_t scenario;         /*  2: 1..4 */
    uint32_t variant;          /*  3: firmware dentro do cenário, 1.. */
    uint32_t state;            /*  4: FidelityState */
    uint32_t error;            /*  5 */
    uint32_t core_hz;          /*  6: nominal */
    uint32_t seed;             /*  7 */
    uint32_t row_capacity;     /*  8 */
    uint32_t row_count;        /*  9 */
    uint32_t trace_capacity;   /* 10: por canal */
    uint32_t trace_count[FIDELITY_WRITERS];  /* 11..13 */
    uint32_t trace_drop[FIDELITY_WRITERS];   /* 14..16 */
    uint32_t cpuid;            /* 17: SCB->CPUID */
    uint32_t rcc_cr;           /* 18 */
    uint32_t rcc_cfgr;         /* 19 */
    uint32_t flash_acr;        /* 20 */
    uint32_t dwt_ctrl;         /* 21 */
    uint32_t aircr;            /* 22: SCB->AIRCR (PRIGROUP) */
    uint32_t dbgmcu_cr;        /* 23: DBGMCU->CR (escrito pelo debugger) */
    uint32_t observer_ticks;   /* 24: mínimo de 2 leituras DWT seguidas */
    uint32_t end_ticks;        /* 25: DWT em fidelity_finish */
    uint32_t reserved[6];      /* 26..31 */
} FidelityHeader;

typedef struct {
    FidelityHeader header;
    uint32_t rows[FIDELITY_ROWS][8];
    FidelityTraceEntry trace[FIDELITY_WRITERS][FIDELITY_TRACE];
} FidelitySnapshot;

_Static_assert(sizeof(FidelityTraceEntry) == 16U, "trace entry ABI");
_Static_assert(sizeof(FidelityHeader) == 128U, "header ABI");
_Static_assert(offsetof(FidelityHeader, trace_count) == 11U * 4U, "trace_count");
_Static_assert(offsetof(FidelityHeader, cpuid) == 17U * 4U, "cpuid");
_Static_assert(offsetof(FidelityHeader, reserved) == 26U * 4U, "reserved");
_Static_assert(offsetof(FidelitySnapshot, rows) == 128U, "rows offset");
_Static_assert(offsetof(FidelitySnapshot, trace) == 128U + FIDELITY_ROWS * 32U,
               "trace offset");
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Fidelity ABI requires little-endian storage"
#endif

extern volatile FidelitySnapshot fidelity_snapshot;

/** Leitura do contador de tempo (DWT CYCCNT). Inline: 1 LDR no caminho. */
static inline uint32_t fidelity_now(void)
{
    return DWT->CYCCNT;
}

/**
 * Zera o snapshot, liga/zera o DWT e publica RUNNING + BOOT. Chamar uma vez,
 * com todas as fontes de IRQ do experimento quiescentes.
 */
void fidelity_init(uint32_t scenario, uint32_t variant, uint32_t seed);

/** Append-only no canal `writer`; esgotado → drop contado, nunca sobrescreve. */
void fidelity_trace(uint32_t writer, uint32_t event, uint32_t trial, uint32_t arg);

/** Idem, com timestamp já medido pelo chamador (spans exatos de brackets). */
void fidelity_trace_at(uint32_t writer, uint32_t ticks, uint32_t event,
                       uint32_t trial, uint32_t arg);

/** Uma linha de resultado. Só MAIN, com as ISRs do ensaio quiescentes. */
void fidelity_row(uint32_t trial, uint32_t condition,
                  uint32_t v0, uint32_t v1, uint32_t v2,
                  uint32_t v3, uint32_t v4, uint32_t v5);

/** Marca erro sem terminar (ex.: timeout de um ensaio). */
void fidelity_flag(uint32_t error_bits);

/**
 * Termina: desabilita IRQs, captura registradores de contexto, publica
 * DONE/FAILED e entra em fidelity_complete() (ponto de dump do coletor).
 * O cenário deve parar suas fontes de periférico antes.
 */
_Noreturn void fidelity_finish(void);
_Noreturn void fidelity_complete(void) __attribute__((noinline));

#endif /* FIDELITY_H */
