/**
 * @file    src/c1/common/c1.h
 * @brief   Registro de resultados do C1 ("C1S1") e interface comum.
 *
 * Um run = reset → main → um LOTE escolhido pelo host → c1_complete().
 * Tudo o que o host precisa fica em UM objeto, `c1_snapshot`, lido pelo GDB
 * depois que o firmware para em c1_complete(). Nada é lido durante a
 * execução. O firmware NÃO compara nada: grava saídas brutas, e o host
 * (scripts/c1) aplica o oráculo.
 *
 * Layout (little-endian, só palavras de 32 bits, sem `packed`):
 *
 *   header   C1Header                     64 palavras (256 B)
 *   records  C1Record[C1_MAX_RECORDS]     um por forma/variante executada
 *   words    uint32_t[C1_MAX_WORDS]       saídas brutas, em sequência
 *
 * Os offsets de header usados pelo assembly (fault.S, startup.S) estão
 * fixados por _Static_assert abaixo; o decodificador (scripts/c1/abi.py)
 * espelha este arquivo.
 *
 * Bloco do host (`c1_host`): o GDB escreve nonce, lote e parâmetros quando o
 * alvo para em main. O nonce aleatório, copiado para o header, prova que o
 * snapshot coletado foi produzido NESTE run (a SRAM da placa sobrevive ao
 * reset).
 */
#ifndef C1_H
#define C1_H

#include <stddef.h>
#include <stdint.h>
#include "c1_config.h"
#include "stm32f1xx.h"

#define C1_MAGIC        UINT32_C(0x31533143)   /* bytes 'C' '1' 'S' '1' */
#define C1_ABI_VERSION  1U
#define C1_HOST_MAGIC   UINT32_C(0x54534F48)   /* bytes 'H' 'O' 'S' 'T' */
#define C1_HEADER_WORDS 64U

#ifndef C1_MAX_RECORDS
#define C1_MAX_RECORDS 128U
#endif
#ifndef C1_MAX_WORDS
#define C1_MAX_WORDS 2048U
#endif

/* Identificação do firmware (header.preset). */
enum C1Preset {
    C1_PRESET_FUNC = 1,
    C1_PRESET_LAYOUT = 2,
    C1_PRESET_CYCLE = 3
};

enum C1State {
    C1_STATE_INIT = 0,        /* .bss zerado: c1_init ainda não rodou */
    C1_STATE_RUNNING = 1,
    C1_STATE_DONE = 2,        /* lote executado até o fim */
    C1_STATE_FAILED = 3       /* falha do INSTRUMENTO (ver error) */
};

/* Bits de header.error: todos tornam o run EVIDÊNCIA INVÁLIDA. */
#define C1_ERR_RECORDS_FULL (1U << 0)
#define C1_ERR_WORDS_FULL   (1U << 1)
#define C1_ERR_PROTOCOL     (1U << 2)   /* begin/put/end fora de ordem */
#define C1_ERR_FAULT        (1U << 3)   /* falta sem aterrissagem publicada */
#define C1_ERR_STACK        (1U << 4)   /* pintura da pilha toda consumida */
#define C1_ERR_HOST         (1U << 5)   /* bloco do host ausente/inválido */
#define C1_ERR_BATCH        (1U << 6)   /* lote inexistente para o preset */
#define C1_ERR_IRQ          (1U << 7)   /* exceção assíncrona inesperada */
#define C1_ERR_SETUP        (1U << 8)   /* pré-condição de um caso falhou */

/* Status de um registro. */
enum C1RecordStatus {
    C1_REC_OPEN = 0,
    C1_REC_OK = 1
};

/* Escrito pelo host (GDB) quando o alvo para em main. */
typedef struct {
    uint32_t magic;           /* C1_HOST_MAGIC */
    uint32_t nonce;           /* aleatório por run */
    uint32_t batch;           /* lote (ou modo) a executar */
    uint32_t iters;           /* repetições quentes (só c1-cycle) */
    uint32_t flags;           /* C1_HOST_* */
    uint32_t reserved[3];
} C1Host;

#define C1_HOST_TRACE (1U << 0)   /* só o 1º vetor de cada forma (traço stepi) */

/*
 * Registro de faltas (fault.S). Offsets fixos, lidos pelo assembly:
 *   +0 CFSR  +4 HFSR  +8 MMFAR  +12 BFAR  +16 PC empilhado  +20 xPSR empilhado
 *   +24 EXC_RETURN  +28 aterrissagem  +32 IPSR  +36 contador de faltas
 */
typedef struct {
    uint32_t cfsr;
    uint32_t hfsr;
    uint32_t mmfar;
    uint32_t bfar;
    uint32_t pc;
    uint32_t xpsr;
    uint32_t exc_return;
    uint32_t landing;         /* publicado pelo caso; 0 = falta inesperada */
    uint32_t ipsr;
    uint32_t count;
} C1Fault;

#define C1_FAULT_WORDS 10U

/*
 * Captura do estado de reset (startup.S), em .noinit. Gravada pelas
 * PRIMEIRAS instruções do Reset_Handler, antes de qualquer escrita em SCB.
 */
typedef struct {
    uint32_t lr;              /*  0 */
    uint32_t sp;              /*  1 */
    uint32_t control;         /*  2 */
    uint32_t primask;         /*  3 */
    uint32_t faultmask;       /*  4 */
    uint32_t basepri;         /*  5 */
    uint32_t ipsr;            /*  6 */
    uint32_t vtor;            /*  7 */
    uint32_t aircr;           /*  8 */
    uint32_t scr;             /*  9 */
    uint32_t ccr;             /* 10 */
    uint32_t shpr1;           /* 11 */
    uint32_t shpr2;           /* 12 */
    uint32_t shpr3;           /* 13 */
    uint32_t shcsr;           /* 14 */
    uint32_t cfsr;            /* 15 */
    uint32_t hfsr;            /* 16 */
    uint32_t dwt_ctrl;        /* 17 */
    uint32_t demcr;           /* 18 */
    uint32_t flash_acr;       /* 19 */
    uint32_t rcc_cr;          /* 20 */
    uint32_t rcc_cfgr;        /* 21 */
    uint32_t boots;           /* 22: incrementado a cada reset (LAY-10) */
    uint32_t magic;           /* 23: C1_RESET_MAGIC quando a captura terminou */
} C1ResetCapture;

#define C1_RESET_WORDS 24U
#define C1_RESET_MAGIC UINT32_C(0x31545352)    /* bytes 'R' 'S' 'T' '1' */

typedef struct {
    uint32_t magic;           /*  0 */
    uint32_t abi_version;     /*  1 */
    uint32_t snapshot_bytes;  /*  2 */
    uint32_t preset;          /*  3: C1Preset */
    uint32_t catalog_hash;    /*  4: hash do catálogo gerado (c1_catalog.h) */
    uint32_t state;           /*  5 */
    uint32_t error;           /*  6 */
    uint32_t nonce;           /*  7 */
    uint32_t batch;           /*  8 */
    uint32_t iters;           /*  9 */
    uint32_t host_flags;      /* 10 */
    uint32_t record_capacity; /* 11 */
    uint32_t record_count;    /* 12 */
    uint32_t word_capacity;   /* 13 */
    uint32_t word_count;      /* 14 */
    uint32_t record_planned;  /* 15 */
    uint32_t observer_ticks;  /* 16: mín. entre duas leituras seguidas do CYCCNT */
    uint32_t cpuid;           /* 17 */
    uint32_t idcode;          /* 18: lê 0 pelo software fora de depuração (ES096 §2.2.2) */
    uint32_t flash_kb;        /* 19 */
    uint32_t uid[3];          /* 20..22 */
    uint32_t rcc_cr;          /* 23 */
    uint32_t rcc_cfgr;        /* 24 */
    uint32_t flash_acr;       /* 25 */
    uint32_t stack_free;      /* 26 */
    uint32_t fault_ipsr;      /* 27: exceção que encontrou a falta inesperada */
    uint32_t fault[C1_FAULT_WORDS];      /* 28..37: cópia de c1_fault na falha */
    uint32_t reset[C1_RESET_WORDS];      /* 38..61: cópia da captura de reset */
    uint32_t reserved[2];                /* 62..63 */
} C1Header;

typedef struct {
    uint32_t id;              /* índice da forma/variante no catálogo gerado */
    uint32_t status;          /* C1RecordStatus */
    uint32_t first_word;
    uint32_t word_count;
} C1Record;

typedef struct {
    C1Header header;
    C1Record records[C1_MAX_RECORDS];
    uint32_t words[C1_MAX_WORDS];
} C1Snapshot;

_Static_assert(sizeof(C1Header) == C1_HEADER_WORDS * 4U, "C1Header ABI");
_Static_assert(offsetof(C1Header, fault) == 28U * 4U, "fault offset");
_Static_assert(offsetof(C1Header, reset) == 38U * 4U, "reset offset");
_Static_assert(sizeof(C1Record) == 16U, "C1Record ABI");
_Static_assert(sizeof(C1Fault) == C1_FAULT_WORDS * 4U, "C1Fault ABI");
_Static_assert(offsetof(C1Fault, landing) == 28U, "landing offset (fault.S)");
_Static_assert(offsetof(C1Fault, count) == 36U, "count offset (fault.S)");
_Static_assert(sizeof(C1ResetCapture) == C1_RESET_WORDS * 4U, "C1ResetCapture ABI");
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "ABI C1S1 exige little-endian"
#endif

extern volatile C1Snapshot c1_snapshot;
extern volatile C1Host c1_host;
extern volatile C1Fault c1_fault;
extern volatile C1ResetCapture c1_reset_capture;

/* Rótulos do .ld (endereços; o conteúdo não importa). */
extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _snoinit, _enoinit;
extern uint32_t _siramfunc, _sramfunc, _eramfunc, _sram_vectors, _eram_vectors;
extern uint32_t _spsp, _epsp, _sstack, _estack;
extern const uint32_t c1_vectors[];        /* tabela de vetores da flash */

/* Registradores usados pelo C1 que o CMSIS do F1 não nomeia. */
#define C1_DWT_CYCCNT   (*(volatile uint32_t *)0xE0001004U)

/** Leitura do contador de tempo: um LDR do DWT_CYCCNT. */
static inline uint32_t c1_now(void)
{
    return C1_DWT_CYCCNT;
}

/**
 * Inicia o run: zera o snapshot, valida o bloco do host, pinta a pilha,
 * liga o DWT (TRCENA, CYCCNTENA), copia identidade e captura de reset e
 * publica RUNNING.
 */
void c1_init(uint32_t preset, uint32_t catalog_hash, uint32_t record_planned);

/** Registro de resultados (só Thread, fora de tratadores). */
void c1_begin(uint32_t id);
void c1_put(uint32_t value);
volatile uint32_t *c1_reserve(uint32_t words);   /* área contígua para o asm */
void c1_end(void);

/** Marca falha do instrumento (bits C1_ERR_*) e encerra o run. */
_Noreturn void c1_fail(uint32_t error);

/** Encerra: captura contexto, publica DONE/FAILED e para em c1_complete. */
_Noreturn void c1_finish(void);

/** Ponto de coleta: o host coloca um hbreak aqui. */
_Noreturn void c1_complete(void) __attribute__((noinline));

/**
 * Chamada com rótulos fixos para o traço por stepi (call.S): chama a rotina
 * no endereço `fn` (bit 0 = 1) com (a, b) em r0, r1 e devolve r0.
 *   c1_call_go: o BLX (1ª instrução da janela)   c1_call_back: retorno.
 */
uint32_t c1_call(uintptr_t fn, uint32_t a, uint32_t b);

/** Habilita os tratadores de UsageFault, BusFault e MemManage (SHCSR). */
void c1_enable_fault_handlers(void);

/**
 * Chamado por fault.S quando a aterrissagem está vazia: se o caso corrente
 * é terminal (c1_terminal != 0), grava o registro de faltas como resultado
 * do caso; senão é falta inesperada → EVIDÊNCIA INVÁLIDA.
 */
_Noreturn void c1_fault_stop(void);
extern volatile uint32_t c1_terminal;

/** Copia o registro de faltas para o resultado do caso corrente e o zera. */
void c1_put_fault(void);
void c1_clear_fault(void);

#endif /* C1_H */
