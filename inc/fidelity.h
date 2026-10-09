/**
 * @file    inc/fidelity.h
 * @brief   ABI v3 ("FID3") do registro de resultados e eventos em SRAM.
 *
 * Um firmware = um experimento finito. Tudo que o host precisa fica em UM
 * objeto global, `fid_snapshot`, lido pelo GDB (bancada ou Renode) depois
 * que o firmware para em `fid_complete()`. Nada é lido durante a medição.
 *
 * Layout (little-endian, só campos de largura fixa, sem `packed`):
 *
 *   header  FidHeader                    40 palavras (160 B)
 *   cases   FidCase[FID_MAX_CASES]       resultado por caso (só MAIN escreve)
 *   words   uint32_t[FID_MAX_WORDS]      dados dos casos, em sequência
 *   ring    FidEvent[FID_WRITERS][FID_RING]  eventos, um anel por escritor
 *
 * As capacidades são gravadas no header; o decodificador nunca as presume.
 *
 * Escritores (writer) são CONTEXTOS FÍSICOS fixos: 0 = MAIN, 1..3 = um
 * handler de IRQ cada. Um anel só é escrito pelo seu contexto, então não há
 * posição global compartilhada nem máscara de IRQ no caminho do registro.
 *
 * Ordem global: cada evento recebe um `ticket` de um contador global
 * incrementado com LDREX/STREX. Se uma exceção acontece entre o LDREX e o
 * STREX, o monitor exclusivo é limpo (ARMv7-M: entrada/saída de exceção
 * executa ClearExclusiveLocal) e o STREX falha → o laço repete e relê o
 * timestamp. Assim, ticket e timestamp são obtidos "atomicamente" e a ordem
 * dos tickets é a ordem real dos registros, sem desabilitar interrupções.
 *
 * Tempo: `ticks` = DWT->CYCCNT. Na placa: ciclos do núcleo (HCLK). No
 * Renode: contador derivado do TEMPO VIRTUAL (frequency do .repl), não
 * ciclos microarquiteturais. O CYCCNT é pré-carregado em FID_DWT_START,
 * perto do estouro de 32 bits; runs acima de 2^20 ticks exercitam a
 * reconstrução do rollover no host (ver scripts/fidelity/abi.py).
 */
#ifndef FIDELITY_H
#define FIDELITY_H

#include <stddef.h>
#include <stdint.h>
#include "stm32f1xx.h"

/* Capacidades: cada firmware pode redefinir via CMake (FID_MAX_CASES=...). */
#ifndef FID_MAX_CASES
#define FID_MAX_CASES 64U
#endif
#ifndef FID_MAX_WORDS
#define FID_MAX_WORDS 1024U
#endif
#ifndef FID_RING
#define FID_RING 64U               /* eventos por escritor; potência de 2 */
#endif

#define FID_MAGIC       UINT32_C(0x33444946)   /* bytes 'F' 'I' 'D' '3' */
#define FID_ABI_VERSION 3U
#define FID_WRITERS     4U
#define FID_DWT_START   UINT32_C(0xFFF00000)   /* estoura após 2^20 ticks */
#define FID_CORE_HZ     8000000U               /* HCLK nominal (HSI) */

/* Contextos escritores fixos. Cada cenário dá nome aos IRQ1..IRQ3. */
enum FidWriter {
    FID_MAIN = 0,
    FID_IRQ1 = 1,
    FID_IRQ2 = 2,
    FID_IRQ3 = 3
};

enum FidState {
    FID_STATE_INIT = 0,       /* .bss zerado: fid_init ainda não rodou */
    FID_STATE_RUNNING = 1,
    FID_STATE_DONE = 2,       /* terminou todos os casos, instrumento íntegro */
    FID_STATE_FAILED = 3      /* falha do INSTRUMENTO (ver error) */
};

/* Status por caso (independe de o resultado estar "certo": isso é do host). */
enum FidCaseStatus {
    FID_CASE_OPEN = 0,        /* começou e não terminou (não deveria sobrar) */
    FID_CASE_OK = 1,          /* protocolo do caso executado até o fim */
    FID_CASE_TIMEOUT = 2      /* uma espera obrigatória do caso expirou */
};

/* Bits de header.error: todos indicam instrumento inválido. */
#define FID_ERR_CASES_FULL  (1U << 0)
#define FID_ERR_WORDS_FULL  (1U << 1)
#define FID_ERR_PROTOCOL    (1U << 2)   /* begin/end/put fora de ordem */
#define FID_ERR_FAULT       (1U << 3)   /* HardFault/BusFault/... */
#define FID_ERR_STACK       (1U << 4)   /* pintura da pilha totalmente consumida */
#define FID_ERR_WRITER      (1U << 5)   /* índice de escritor inválido */
#define FID_ERR_PLAN        (1U << 6)   /* nº de casos ≠ planejado */

/* Eventos genéricos; cada cenário define os seus a partir de 0x100. */
enum FidEventId {
    FID_EV_BOOT = 1,          /* arg = firmware_id */
    FID_EV_CALIBRATE = 2,     /* registros usados p/ medir o custo do logger */
    FID_EV_CASE_BEGIN = 3,    /* arg = case_id */
    FID_EV_CASE_END = 4,      /* arg = status */
    FID_EV_FINISH = 5
};

typedef struct {
    uint32_t ticks;           /* DWT->CYCCNT bruto */
    uint32_t ticket;          /* ordem global dos registros */
    uint16_t event;           /* FidEventId ou evento do cenário */
    uint16_t case_id;         /* caso corrente quando o registro foi feito */
    uint32_t arg;
} FidEvent;

typedef struct {
    uint32_t case_id;
    uint32_t status;          /* FidCaseStatus */
    uint32_t first_word;      /* índice em words[] */
    uint32_t word_count;
} FidCase;

typedef struct {
    uint32_t magic;           /*  0 */
    uint32_t abi_version;     /*  1 */
    uint32_t snapshot_bytes;  /*  2: sizeof(FidSnapshot) */
    uint32_t firmware_id;     /*  3: 0xCCVV (cenário, variante) */
    uint32_t state;           /*  4: FidState */
    uint32_t error;           /*  5: FID_ERR_* */
    uint32_t run_nonce;       /*  6: escrito pelo host em main (prova de run) */
    uint32_t case_planned;    /*  7 */
    uint32_t case_capacity;   /*  8 */
    uint32_t case_count;      /*  9 */
    uint32_t word_capacity;   /* 10 */
    uint32_t word_count;      /* 11 */
    uint32_t ring_capacity;   /* 12: eventos por escritor */
    uint32_t writer_count;    /* 13 */
    uint32_t ring_head[FID_WRITERS];  /* 14..17: total escrito (monotônico) */
    uint32_t ticket_next;     /* 18: próximo ticket global */
    uint32_t dwt_start;       /* 19: valor carregado no CYCCNT */
    uint32_t dwt_end;         /* 20: CYCCNT em fid_finish */
    uint32_t observer_ticks;  /* 21: min. entre duas leituras seguidas do CYCCNT */
    uint32_t log_ticks;       /* 22: min. entre dois fid_log seguidos (MAIN) */
    uint32_t core_hz;         /* 23: HCLK nominal configurado */
    uint32_t cpuid;           /* 24: SCB->CPUID */
    uint32_t idcode;          /* 25: DBGMCU->IDCODE */
    uint32_t flash_kb;        /* 26: registrador de tamanho da flash (F_SIZE) */
    uint32_t uid[3];          /* 27..29: Unique device ID */
    uint32_t rcc_cr;          /* 30 */
    uint32_t rcc_cfgr;        /* 31 */
    uint32_t flash_acr;       /* 32 */
    uint32_t dbgmcu_cr;       /* 33 */
    uint32_t aircr;           /* 34: SCB->AIRCR (PRIGROUP) */
    uint32_t stack_free;      /* 35: bytes de pilha nunca tocados */
    uint32_t fault_pc;        /* 36: PC empilhado na falha (se houver) */
    uint32_t fault_cfsr;      /* 37: SCB->CFSR na falha */
    uint32_t reserved[2];     /* 38..39 */
} FidHeader;

typedef struct {
    FidHeader header;
    FidCase cases[FID_MAX_CASES];
    uint32_t words[FID_MAX_WORDS];
    FidEvent ring[FID_WRITERS][FID_RING];
} FidSnapshot;

_Static_assert(sizeof(FidEvent) == 16U, "FidEvent ABI");
_Static_assert(sizeof(FidCase) == 16U, "FidCase ABI");
_Static_assert(sizeof(FidHeader) == 160U, "FidHeader ABI");
_Static_assert(offsetof(FidHeader, ring_head) == 14U * 4U, "ring_head");
_Static_assert(offsetof(FidHeader, uid) == 27U * 4U, "uid");
_Static_assert(offsetof(FidHeader, reserved) == 38U * 4U, "reserved");
_Static_assert(offsetof(FidSnapshot, cases) == 160U, "cases offset");
_Static_assert((FID_RING & (FID_RING - 1U)) == 0U, "FID_RING potência de 2");
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "ABI FID3 exige little-endian"
#endif

extern volatile FidSnapshot fid_snapshot;

/** Escrito pelo host (GDB) ao parar em main; copiado para header.run_nonce. */
extern volatile uint32_t fid_host_nonce;

/** Leitura do contador de tempo: um LDR do DWT->CYCCNT. */
static inline uint32_t fid_now(void)
{
    return DWT->CYCCNT;
}

/** Espera ativa de `ticks` (diferença sem sinal: imune ao rollover). */
static inline void fid_delay(uint32_t ticks)
{
    uint32_t t0 = fid_now();
    while ((fid_now() - t0) < ticks) {
    }
}

/**
 * Inicia o experimento: zera o snapshot, pinta a pilha, liga o DWT a partir
 * de FID_DWT_START, mede o custo do observador e do logger e publica
 * RUNNING. Chamar uma vez, logo após board_init(), com todas as IRQs do
 * experimento ainda desligadas.
 */
void fid_init(uint32_t firmware_id, uint32_t case_planned);

/** Registra um evento no anel do `writer` (contexto que chama). */
void fid_log(uint32_t writer, uint32_t event, uint32_t arg);

/**
 * Idem, com timestamp já medido pelo chamador (ex.: limites de um bracket).
 * Só para MAIN sem IRQs ativas: a ordem do ticket é a ordem do programa.
 */
void fid_log_at(uint32_t writer, uint32_t ticks, uint32_t event, uint32_t arg);

/* Resultados por caso — apenas MAIN, com os handlers do caso quiescentes. */
void fid_case_begin(uint32_t case_id);
void fid_put(uint32_t value);
void fid_case_end(uint32_t status);

/**
 * Termina: desliga IRQs, captura registradores de contexto e a margem de
 * pilha, publica DONE ou FAILED e para em fid_complete(). O cenário deve
 * parar seus periféricos antes de chamar.
 */
_Noreturn void fid_finish(void);

/** Ponto de coleta: o host coloca um hbreak aqui. */
_Noreturn void fid_complete(void) __attribute__((noinline));

/**
 * Bracket de medição em assembly (lib/fidelity_measure.S):
 *   t0 = CYCCNT; r = fn(a, b); t1 = CYCCNT; out->result = r; out->t0 = t0;
 *   devolve t1 - t0.
 * A ordem LDR/BLX/LDR é fixa no assembly: o compilador não pode mover a
 * chamada para fora das leituras do contador.
 */
typedef uint32_t (*FidFn)(uint32_t a, uint32_t b);
typedef struct {
    uint32_t result;
    uint32_t t0;
} FidSpan;
uint32_t fid_measure(FidFn fn, uint32_t a, uint32_t b, FidSpan *out);

#endif /* FIDELITY_H */
