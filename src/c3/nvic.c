/**
 * @file    src/c3/nvic.c
 * @brief   C3 — seleção e atendimento de exceções pelo NVIC.
 *
 * Pergunta: o Renode escolhe e atende interrupções na mesma ordem da placa
 * (grupo, subprioridade, número), com a mesma preempção, encadeamento e
 * mascaramento (PRIMASK/BASEPRI), e em quanto tempo?
 *
 * Estímulos: duas IRQs implementadas e ociosas — A = EXTI0 (IRQ 6) e
 * B = EXTI1 (IRQ 7) — PENDIDAS POR SOFTWARE (NVIC->ISPR). Nenhum periférico
 * gera estímulo; o C3 não depende do comportamento temporal dos timers (C2).
 *
 * Prioridades (PM0056 §4.4.5, AIRCR.PRIGROUP): o STM32F103 implementa 4
 * bits (7:4). Usamos PRIGROUP = 5: bits 7:6 = prioridade de GRUPO (0..3),
 * bits 5:4 = SUBPRIORIDADE (0..3). Valor MENOR = prioridade MAIOR. Só o
 * grupo decide preempção; sub e depois o número da exceção desempatam a
 * escolha entre pendentes.
 *
 * Registro: cada handler escreve SÓ no seu anel (A → IRQ1, B → IRQ2) e
 * guarda TODAS as ocorrências (entrada k, k = 0, 1, ...), nunca uma posição
 * por identificador. A ordem global vem dos tickets (inc/fidelity.h): o
 * logger não mascara interrupções. Ações dos handlers são lidas de uma
 * tabela escrita por MAIN antes do estímulo; cada contador de entradas só
 * é escrito pelo próprio handler.
 *
 * Após cada NVIC_SetPendingIRQ vem DSB + ISB: garante que a exceção, se
 * puder preemptar, torna-se observável após a sincronização (mesma sequência
 * nos dois ambientes).
 */
#include "board.h"
#include "fidelity.h"

#define FIRMWARE_ID 0x0301U

#define IRQ_A EXTI0_IRQn
#define IRQ_B EXTI1_IRQn
#define PRIGROUP 5U

/* Eventos do C3. */
#define EV_ENTER      0x300U   /* handler: arg = nº da entrada | IPSR << 8 */
#define EV_AFTER_PEND 0x301U   /* handler: 1º registro após pender; arg = IRQn pendida */
#define EV_EXIT       0x302U   /* handler: arg = nº da entrada */
#define EV_REQUEST    0x310U   /* MAIN: antes de pender; arg = IRQn */
#define EV_RELEASE    0x311U   /* MAIN: antes de liberar a máscara */
#define EV_BACK       0x312U   /* MAIN: de volta à thread */

enum { H_A = 0, H_B = 1 };

/* O que cada handler faz na sua PRIMEIRA entrada do caso. */
typedef struct {
    uint32_t pend_other;       /* 1 = pende a outra IRQ */
    uint32_t pend_self;        /* 1 = pende a si mesma (repetição) */
} Action;

static volatile Action s_action[2];
static volatile uint32_t s_entries[2];        /* cada um escrito só pelo seu handler */

static const IRQn_Type IRQ_OF[2] = {IRQ_A, IRQ_B};
static const uint32_t WRITER_OF[2] = {FID_IRQ1, FID_IRQ2};

/* ───────────────────────────── handlers ───────────────────────────── */

static void pend(IRQn_Type irq)
{
    NVIC_SetPendingIRQ(irq);
    __DSB();
    __ISB();
}

static void handler(uint32_t h)
{
    uint32_t n = s_entries[h];
    fid_log(WRITER_OF[h], EV_ENTER, n | (__get_IPSR() << 8));
    s_entries[h] = n + 1U;
    if (n == 0U && s_action[h].pend_other != 0U) {
        pend(IRQ_OF[1U - h]);
        fid_log(WRITER_OF[h], EV_AFTER_PEND, (uint32_t)IRQ_OF[1U - h]);
    }
    if (n == 0U && s_action[h].pend_self != 0U) {
        pend(IRQ_OF[h]);
        fid_log(WRITER_OF[h], EV_AFTER_PEND, (uint32_t)IRQ_OF[h]);
    }
    fid_log(WRITER_OF[h], EV_EXIT, n);
}

void EXTI0_IRQHandler(void);
void EXTI1_IRQHandler(void);

void EXTI0_IRQHandler(void) { handler(H_A); }
void EXTI1_IRQHandler(void) { handler(H_B); }

/* ───────────────────────────── utilidades ───────────────────────────── */

/* Prioridade lógica CMSIS (0..15), não byte IPR (bits 7:4). */
static uint32_t prio(uint32_t group, uint32_t sub)
{
    return NVIC_EncodePriority(PRIGROUP, group, sub);
}

/* Abre um caso: prioridades, ações e contadores zerados (sem IRQ ativa). */
static void begin(uint32_t case_id, uint32_t prio_a, uint32_t prio_b,
                  Action action_a, Action action_b)
{
    /* Sem escritores ativos durante configuração e abertura do caso. */
    NVIC_DisableIRQ(IRQ_A);
    NVIC_DisableIRQ(IRQ_B);
    __set_BASEPRI(0U);
    __enable_irq();
    __ISB();
    NVIC_ClearPendingIRQ(IRQ_A);
    NVIC_ClearPendingIRQ(IRQ_B);
    NVIC_SetPriority(IRQ_A, prio_a);
    NVIC_SetPriority(IRQ_B, prio_b);
    s_action[H_A] = action_a;
    s_action[H_B] = action_b;
    s_entries[H_A] = 0U;
    s_entries[H_B] = 0U;
    fid_case_begin(case_id);
    fid_put(NVIC_GetPriority(IRQ_A));
    fid_put(NVIC_GetPriority(IRQ_B));
    fid_put(action_a.pend_other | (action_a.pend_self << 1));
    fid_put(action_b.pend_other | (action_b.pend_self << 1));
    __DSB();
    NVIC_EnableIRQ(IRQ_A);
    NVIC_EnableIRQ(IRQ_B);
    __DSB();
    __ISB();
}

static void end(void)
{
    NVIC_DisableIRQ(IRQ_A);
    NVIC_DisableIRQ(IRQ_B);
    __DSB();
    fid_put(s_entries[H_A]);
    fid_put(s_entries[H_B]);
    fid_put(NVIC_GetPendingIRQ(IRQ_A));
    fid_put(NVIC_GetPendingIRQ(IRQ_B));
    fid_case_end(FID_CASE_OK);
}

static const Action NONE = {0U, 0U};
static const Action PEND_OTHER = {1U, 0U};
static const Action PEND_SELF = {0U, 1U};

/* ───────────────────────────── casos ───────────────────────────── */

/*
 * Arbitragem: as duas pendentes com PRIMASK = 1, depois liberadas. A ordem
 * de solicitação (first, second) varia nos empates para separar "ordem do
 * pedido" de "regra arquitetural" (número menor vence).
 */
static void case_arbitration(uint32_t case_id, uint32_t prio_a, uint32_t prio_b,
                             IRQn_Type first, IRQn_Type second)
{
    begin(case_id, prio_a, prio_b, NONE, NONE);
    __disable_irq();
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)first);
    pend(first);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)second);
    pend(second);
    fid_log(FID_MAIN, EV_RELEASE, 0U);
    __enable_irq();
    __ISB();
    fid_log(FID_MAIN, EV_BACK, 0U);
    end();
}

/* Preempção: MAIN pende `first`; na 1ª entrada, o handler pende a outra. */
static void case_preemption(uint32_t case_id, uint32_t prio_a, uint32_t prio_b, uint32_t first)
{
    Action action_a = (first == H_A) ? PEND_OTHER : NONE;
    Action action_b = (first == H_B) ? PEND_OTHER : NONE;
    begin(case_id, prio_a, prio_b, action_a, action_b);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_OF[first]);
    pend(IRQ_OF[first]);
    fid_log(FID_MAIN, EV_BACK, 0U);
    end();
}

/* PRIMASK: pendente sem execução até __enable_irq. */
static void case_primask(uint32_t case_id)
{
    begin(case_id, prio(1U, 0U), prio(2U, 0U), NONE, NONE);
    __disable_irq();
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_A);
    pend(IRQ_A);
    uint32_t pending = NVIC_GetPendingIRQ(IRQ_A);
    uint32_t entries0 = s_entries[H_A];
    fid_delay(1000U);
    uint32_t entries1 = s_entries[H_A];
    fid_log(FID_MAIN, EV_RELEASE, 0U);
    __enable_irq();
    __ISB();
    fid_log(FID_MAIN, EV_BACK, 0U);
    fid_put(pending);
    fid_put(entries0);
    fid_put(entries1);
    end();
}

/*
 * BASEPRI = limiar: só exceções de prioridade de grupo numericamente MENOR
 * que o limiar são atendidas. A (prio_a) é pendida primeiro, B (prio_b)
 * depois; em seguida BASEPRI = 0 (sem máscara) libera o que ficou pendente.
 */
static void case_basepri(uint32_t case_id, uint32_t threshold, uint32_t prio_a, uint32_t prio_b)
{
    begin(case_id, prio_a, prio_b, NONE, NONE);
    __set_BASEPRI(threshold << (8U - __NVIC_PRIO_BITS));
    __DSB();
    __ISB();
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_A);
    pend(IRQ_A);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_B);
    pend(IRQ_B);
    uint32_t entries_a = s_entries[H_A];
    uint32_t entries_b = s_entries[H_B];
    uint32_t pending_a = NVIC_GetPendingIRQ(IRQ_A);
    uint32_t pending_b = NVIC_GetPendingIRQ(IRQ_B);
    uint32_t basepri = __get_BASEPRI();
    fid_log(FID_MAIN, EV_RELEASE, 0U);
    __set_BASEPRI(0U);
    __ISB();
    fid_log(FID_MAIN, EV_BACK, 0U);
    fid_put(basepri);
    fid_put(entries_a);
    fid_put(entries_b);
    fid_put(pending_a);
    fid_put(pending_b);
    end();
}

/* Encadeamento: A (grupo 1) pende B (grupo 2) e termina; B roda na saída
 * de A, sem voltar à thread. Os timestamps incluem logger e epílogo/
 * prólogo; não medem isoladamente os ciclos de tail-chaining. */
static void case_tail_chain(uint32_t case_id)
{
    begin(case_id, prio(1U, 0U), prio(2U, 0U), PEND_OTHER, NONE);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_A);
    pend(IRQ_A);
    fid_log(FID_MAIN, EV_BACK, 0U);
    end();
}

/* Controle do encadeamento: A sozinha volta à thread; MAIN então pende B. */
static void case_chain_control(uint32_t case_id)
{
    begin(case_id, prio(1U, 0U), prio(2U, 0U), NONE, NONE);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_A);
    pend(IRQ_A);
    fid_log(FID_MAIN, EV_BACK, 0U);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_B);
    pend(IRQ_B);
    fid_log(FID_MAIN, EV_BACK, 0U);
    end();
}

/* Repetição: as duas pendentes sob PRIMASK; o handler `repeater` se pende
 * de novo na 1ª entrada → 2 entradas/saídas dele, na ordem certa com a outra. */
static void case_repend(uint32_t case_id, uint32_t prio_a, uint32_t prio_b, uint32_t repeater)
{
    Action action_a = (repeater == H_A) ? PEND_SELF : NONE;
    Action action_b = (repeater == H_B) ? PEND_SELF : NONE;
    begin(case_id, prio_a, prio_b, action_a, action_b);
    __disable_irq();
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_A);
    pend(IRQ_A);
    fid_log(FID_MAIN, EV_REQUEST, (uint32_t)IRQ_B);
    pend(IRQ_B);
    fid_log(FID_MAIN, EV_RELEASE, 0U);
    __enable_irq();
    __ISB();
    fid_log(FID_MAIN, EV_BACK, 0U);
    end();
}

/* ───────────────────────────── main ───────────────────────────── */

#define CASE_COUNT 18U

int main(void)
{
    board_init();
    fid_init(FIRMWARE_ID, CASE_COUNT);
    NVIC_SetPriorityGrouping(PRIGROUP);
    /* Linhas EXTI0/1 sem estímulos periféricos, inclusive após reset
     * do debugger: somente ISPR gera pedidos neste cenário. */
    RCC->APB2ENR |= RCC_APB2ENR_AFIOEN;
    (void)RCC->APB2ENR;
    EXTI->IMR &= ~3U;
    EXTI->EMR &= ~3U;
    EXTI->RTSR &= ~3U;
    EXTI->FTSR &= ~3U;
    EXTI->PR = 3U;
    __DSB();

    /* Arbitragem entre pendentes (ids 0x01..0x06). */
    case_arbitration(0x01U, prio(1U, 0U), prio(2U, 0U), IRQ_A, IRQ_B);   /* grupo: A */
    case_arbitration(0x02U, prio(2U, 0U), prio(1U, 0U), IRQ_A, IRQ_B);   /* grupo: B */
    case_arbitration(0x03U, prio(1U, 0U), prio(1U, 1U), IRQ_A, IRQ_B);   /* sub: A */
    case_arbitration(0x04U, prio(1U, 1U), prio(1U, 0U), IRQ_A, IRQ_B);   /* sub: B */
    case_arbitration(0x05U, prio(1U, 1U), prio(1U, 1U), IRQ_A, IRQ_B);   /* empate */
    case_arbitration(0x06U, prio(1U, 1U), prio(1U, 1U), IRQ_B, IRQ_A);   /* empate, ordem invertida */

    /* Preempção durante um handler (ids 0x11..0x15). */
    case_preemption(0x11U, prio(2U, 0U), prio(1U, 0U), H_A);   /* B grupo maior: preempta */
    case_preemption(0x12U, prio(1U, 1U), prio(1U, 0U), H_A);   /* mesmo grupo, sub maior: não */
    case_preemption(0x13U, prio(1U, 0U), prio(2U, 0U), H_A);   /* B grupo menor: não */
    case_preemption(0x14U, prio(1U, 0U), prio(2U, 0U), H_B);   /* papéis invertidos: A preempta B */
    case_preemption(0x15U, prio(1U, 1U), prio(1U, 1U), H_A);   /* empate total: não */

    /* Mascaramento (ids 0x21..0x23). */
    case_primask(0x21U);
    case_basepri(0x22U, prio(1U, 0U), prio(0U, 0U), prio(2U, 0U));  /* limiar grupo 1: A passa, B espera */
    case_basepri(0x23U, prio(1U, 0U), prio(1U, 0U), prio(1U, 2U));  /* igual ao limiar (sub ignorada): esperam */

    /* Encadeamento e controle (ids 0x31..0x32). */
    case_tail_chain(0x31U);
    case_chain_control(0x32U);

    /* Repetição (ids 0x41..0x42). */
    case_repend(0x41U, prio(1U, 0U), prio(2U, 0U), H_A);       /* A, A, B */
    case_repend(0x42U, prio(2U, 0U), prio(1U, 0U), H_B);       /* B, B, A */

    fid_finish();
}
