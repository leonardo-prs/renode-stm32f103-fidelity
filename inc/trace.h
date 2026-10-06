/**
 * @file    inc/trace.h
 * @brief   Tracer DWT unificado (cenarios S1..S4): ring buffer ISR-safe.
 *
 * Uso: incluir em EXATAMENTE 1 TU por firmware (cenarios sao single-TU; o
 * armazenamento e definido aqui para expor simbolos com linkage C ao GDB:
 * trace_buf, trace_w, trace_lost). trace_init() liga o CYCCNT e registra
 * TRACE_BOOT; trace_emit() grava 1 amostra (5 B).
 *
 * ISR-safe single-writer: publica payload antes do indice; wrap do CYCCNT
 * resolvido no pos-processo (delta unsigned 32-bit). Total emitido (sem
 * saturacao): trace_lost * TRACE_N + trace_w.
 */
#ifndef TRACE_H
#define TRACE_H

#include <stdint.h>
#include "stm32f1xx.h"              /* CMSIS device: DWT, CoreDebug */

/* Profundidade do ring (n. de amostras); sobrescrevivel via -DTRACE_N=. */
#ifndef TRACE_N
#define TRACE_N 2048
#endif

/* ── Mapa de IDs (fixo S1..S4) ── */
/* Comuns */
#define TRACE_BOOT        0x00u     /* primeira amostra (trace_init) */
#define TRACE_ERROR       0xFEu     /* erro/park (ex.: sem CYCCNT) */
#define TRACE_WRAP_RESYNC 0xFFu     /* ressincronia de wrap (uso futuro) */
/* S1: blocos de calibracao (0x01=enter, 0x02=exit; 0x03..0x0F reservados) */
#define TRACE_BLK_ENTER   0x01u
#define TRACE_BLK_EXIT    0x02u
/* S2: IRQ baseline (TIM2 + WFI) */
#define TRACE_TIM2_ENTER  0x10u
#define TRACE_TIM2_EXIT   0x11u
#define TRACE_WFI_ENTER   0x12u
#define TRACE_WFI_EXIT    0x13u
/* S3: ISRs por nome (TIM2 prio 2 = HIGH preempta; TIM3 prio 12 = LOW) + sweep.
 * Nomes L/H preservados p/ compatibilidade: L=TIM2 (0x20/0x21), H=TIM3 (0x22/0x23).
 * A direcao real de preempcao e TIM2 sobre TIM3 (grupo menor = maior prioridade). */
#define TRACE_L_ENTER     0x20u
#define TRACE_L_EXIT      0x21u
#define TRACE_H_ENTER     0x22u
#define TRACE_H_EXIT      0x23u
#define TRACE_SWEEP_MARK  0x24u
/* S4: USART1 (0x30/0x31/0x32 usados; 0x33 reservado — S4 reaproveita
 * 0x10/0x11 p/ bg TIM2). */
#define TRACE_BYTE_TX     0x30u
#define TRACE_BYTE_RX     0x31u
#define TRACE_UIF_POLL    0x32u
#define TRACE_TIM2_BG     0x33u

/* Amostra de 5 B: timestamp CYCCNT absoluto + id do evento. */
typedef struct { uint32_t ts; uint8_t id; } __attribute__((packed)) TracePoint;
_Static_assert(sizeof(TracePoint) == 5u, "TracePoint deve ocupar 5 B");
_Static_assert((TRACE_N) >= 1 && (TRACE_N) <= 65535, "TRACE_N fora do indice u16");

/* Armazenamento com linkage C (dump via GDB); ver nota de 1-TU acima. */
TracePoint trace_buf[TRACE_N];
volatile uint16_t trace_w;          /* proxima posicao de escrita (0..TRACE_N-1) */
volatile uint16_t trace_lost;       /* n. de voltas com sobrescrita (satura em 0xFFFF) */

/**
 * @brief Liga TRCENA+CYCCNT, zera base de tempo/ring e marca TRACE_BOOT.
 */
static inline void trace_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0u;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    trace_w = 0u;
    trace_lost = 0u;
    trace_buf[0u].ts = DWT->CYCCNT;
    trace_buf[0u].id = TRACE_BOOT;
    trace_w = 1u % (uint16_t)(TRACE_N);
}

/**
 * @brief Grava 1 amostra (CYCCNT + id); sobrescreve o mais antigo no wrap.
 *
 * Single-writer (ISR ou thread com IRQ mascarada): sem atomics, sem
 * malloc/printf. Ordem de publicacao (payload, depois indice) permite
 * dump assincrono via GDB sem travar o alvo.
 */
static inline void trace_emit(uint8_t id)
{
    uint16_t w = trace_w;
    trace_buf[w].ts = DWT->CYCCNT;
    trace_buf[w].id = id;
    if (++w >= (uint16_t)(TRACE_N)) {
        w = 0u;
        if (trace_lost != 0xFFFFu) {
            trace_lost++;
        }
    }
    trace_w = w;
}

#endif /* TRACE_H */
