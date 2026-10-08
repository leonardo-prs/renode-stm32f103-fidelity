/**
 * @file    src/s4/seq.h
 * @brief   Registro de ORDEM de eventos entre contextos (S4A/S4B).
 *
 * A ordem não pode vir só de timestamps: no Renode o DWT é grosseiro dentro
 * de um bloco traduzido (eventos distintos podem empatar). Cada evento
 * recebe um número de sequência global por incremento atômico LDREX/STREX
 * (sem mascarar IRQ; a entrada/saída de exceção limpa o monitor exclusivo,
 * então um STREX interrompido falha e repete). Cada slot de evento tem um
 * único escritor (o contexto que o produz).
 */
#ifndef S4_SEQ_H
#define S4_SEQ_H

#include "board.h"
#include "fidelity.h"

#define SEQ_EVENTS 16U

typedef struct {
    volatile uint32_t next;
    volatile uint32_t seq[SEQ_EVENTS];     /* 0 = não ocorreu */
    volatile uint32_t ticks[SEQ_EVENTS];
} SeqLog;

static inline void seq_reset(SeqLog *log)
{
    log->next = 0U;
    for (uint32_t i = 0U; i < SEQ_EVENTS; ++i) {
        log->seq[i] = 0U;
        log->ticks[i] = 0U;
    }
}

static inline void seq_mark(SeqLog *log, uint32_t event, uint32_t ticks)
{
    uint32_t n;
    do {
        n = __LDREXW(&log->next) + 1U;
    } while (__STREXW(n, &log->next) != 0U);
    log->seq[event] = n;
    log->ticks[event] = ticks;
}

/* Código de ordem: ids dos eventos ocorridos, em ordem de sequência, um
 * nibble por evento (o 1º no nibble menos significativo). Até 8 eventos. */
static inline uint32_t seq_order_code(const SeqLog *log)
{
    uint32_t code = 0U;
    uint32_t shift = 0U;
    for (uint32_t s = 1U; s <= log->next && shift < 32U; ++s) {
        for (uint32_t e = 1U; e < SEQ_EVENTS; ++e) {
            if (log->seq[e] == s) {
                code |= e << shift;
                shift += 4U;
                break;
            }
        }
    }
    return code;
}

#endif /* S4_SEQ_H */
