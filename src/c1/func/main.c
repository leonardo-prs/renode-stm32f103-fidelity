/**
 * @file    src/c1/func/main.c
 * @brief   C1 funcional: executa um lote de vetores e grava as saídas brutas.
 *
 * O host escreve o número do lote em c1_host.batch (GDB, ao parar em main).
 * Cada entrada do lote é um trecho de uma FORMA do catálogo (uma rotina
 * assembly + um gerador de vetores). Para cada vetor:
 *
 *   1. monta as entradas a partir dos eixos (produto cartesiano, o último
 *      eixo varia mais rápido — a mesma ordem que scripts/c1/catalog.py);
 *   2. se a forma toca memória, pré-enche a janela c1_scratch com 0xA5;
 *   3. chama a rotina por c1_call (rótulos fixos para o traço por stepi);
 *   4. anexa a janela de memória e/ou o registro de faltas, conforme a forma.
 *
 * Nada é comparado aqui. O C serve só para percorrer as tabelas.
 */
#include "c1.h"
#include "c1_catalog.h"
#include "func.h"

_Alignas(16) volatile uint32_t c1_scratch[C1_MEM_WORDS];

static void build_inputs(const C1Form *f, uint32_t v, uint32_t *in)
{
    /* Decomposição em base mista: o último eixo é o dígito menos significativo. */
    uint32_t pos = f->nin;
    for (int32_t a = (int32_t)f->naxes - 1; a >= 0; --a) {
        const C1Axis *ax = &c1_axes[f->axis0 + (uint32_t)a];
        uint32_t k = v % ax->rows;
        v /= ax->rows;
        pos -= ax->width;
        for (uint32_t w = 0U; w < ax->width; ++w) {
            in[pos + w] = c1_pool[ax->offset + k * ax->width + w];
        }
    }
}

static void run_entry(const C1Entry *e, uint32_t trace)
{
    const C1Form *f = &c1_forms[e->form];
    uint32_t in[8];
    uint32_t last = trace ? e->first + 1U : e->first + e->count;

    c1_terminal = (f->flags & C1_FORM_TERMINAL) ? 1U : 0U;
    c1_begin(e->form);
    for (uint32_t v = e->first; v < last; ++v) {
        build_inputs(f, v, in);
        if (f->flags & C1_FORM_MEM) {
            for (uint32_t k = 0U; k < C1_MEM_WORDS; ++k) {
                c1_scratch[k] = C1_MEM_FILL;
            }
        }
        volatile uint32_t *out = c1_reserve(f->nout);
        c1_call((uintptr_t)f->fn, (uint32_t)in, (uint32_t)out);
        if (f->flags & C1_FORM_MEM) {
            volatile uint32_t *win = c1_reserve(C1_MEM_WORDS);
            for (uint32_t k = 0U; k < C1_MEM_WORDS; ++k) {
                win[k] = c1_scratch[k];
            }
        }
        if (f->flags & (C1_FORM_FAULT | C1_FORM_TERMINAL)) {
            c1_put_fault();       /* também apaga a aterrissagem não usada */
        }
        func_restore();           /* estado global que um caso pode ter mudado */
    }
    c1_end();
    c1_terminal = 0U;
}

int main(void)
{
    uint32_t batch = c1_host.batch;
    uint32_t trace = c1_host.flags & C1_HOST_TRACE;
    const C1Batch *b = (batch < C1_N_BATCHES) ? &c1_batches[batch] : 0;

    c1_init(C1_PRESET_FUNC, C1_CATALOG_HASH, b ? b->count : 0U);
    if (b == 0) {
        c1_fail(C1_ERR_BATCH);
    }
    c1_enable_fault_handlers();
    func_setup();
    for (uint32_t i = 0U; i < b->count; ++i) {
        run_entry(&c1_entries[b->first + i], trace);
    }
    c1_finish();
}
