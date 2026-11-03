/*
 * src/c2/sw.c — C2, etapas 1 e 2: pedidos por software (04-c2.typ).
 *
 * c2_caso (gravado pelo monitor) escolhe o caso. Cada caso percorre todos
 * os seus pontos numa execução e grava em c2_rec, por ponto, o que o
 * firmware viu. A ordem dos pontos e o leiaute de cada registro estão
 * repetidos em scripts/c2_sw.py, que calcula a resposta do documento.
 *
 *   1  C2-01  pendência e habilitação     15 linhas × {STIR, ISPR}
 *   2  C2-02  prioridade e empate         3 linhas, 16³ prioridades
 *   3  C2-03  preempção aninhada          2 linhas × 2 papéis, 16² prioridades
 *   4  C2-04  máscaras                    PRIMASK, BASEPRI, BASEPRI_MAX
 *   5  C2-05  latência de entrada         15 linhas, STIR + NOPs (observada por ganchos)
 *   6  C2-06  encadeamento                15 linhas pendentes, 2 rodadas (ganchos e traço)
 */
#include "c2.h"

#define MARCA 0x100U                    /* exceção | MARCA: tratador depois do pedido aninhado */

static const uint8_t TRIO[3] = {0, 20, 42};     /* C2-02 */
static const uint8_t PAR[2] = {0, 42};          /* C2-03 */
#define LINHA_04 0U                             /* C2-04 */

/* C2-03: c2_irq faz um pedido aninhado quando atende a exceção AN_EXC.
 * Escritos só por main, com nenhuma das linhas ativa. */
static volatile uint32_t an_exc;
static volatile uint32_t an_linha;

void c2_irq(void)
{
    uint32_t exc = c2_anota();
    if (exc == an_exc) {
        NVIC->STIR = an_linha;
        c2_barreira();
        uint32_t n = c2_nlog;
        c2_log[n % C2_LOG] = exc | MARCA;
        c2_nlog = n + 1U;
    }
}

/* Espera até o registro ter `alvo` atendimentos (ou desistir). */
static void aguarda(uint32_t alvo)
{
    for (uint32_t i = 0U; i < 1000U && c2_nlog < alvo; i++) {
    }
}

/* Até 3 atendimentos a partir de n0, 9 bits cada (exceção | MARCA), e o
 * total nos bits 27..31. */
static uint32_t ordem(uint32_t n0)
{
    uint32_t n = c2_nlog - n0;
    uint32_t v = (n < 31U ? n : 31U) << 27;
    for (uint32_t k = 0U; k < n && k < 3U; k++) {
        v |= (c2_atendido(n0 + k) & 0x1FFU) << (9U * k);
    }
    return v;
}

/* ── C2-01 ── por ponto: linha | mecanismo << 8, depois do pedido (pendente,
 * ativa, atendimentos), depois da habilitação (idem), exceção atendida. */
static void caso_01(void)
{
    for (uint32_t i = 0U; i < C2_N_LIVRE; i++) {
        for (uint32_t mec = 0U; mec < 2U; mec++) {
            uint32_t linha = c2_livres[i];
            IRQn_Type irq = (IRQn_Type)linha;
            c2_prepara(linha, 8U);
            uint32_t n0 = c2_nlog;
            if (mec == 0U) {
                NVIC->STIR = linha;
            } else {
                NVIC_SetPendingIRQ(irq);
            }
            c2_barreira();
            c2_espera(16U);
            c2_grava(linha | (mec << 8));
            c2_grava(NVIC_GetPendingIRQ(irq));
            c2_grava(NVIC_GetActive(irq));
            c2_grava(c2_nlog - n0);
            NVIC_EnableIRQ(irq);
            c2_barreira();
            c2_espera(16U);
            c2_grava(NVIC_GetPendingIRQ(irq));
            c2_grava(NVIC_GetActive(irq));
            c2_grava(c2_nlog - n0);
            c2_grava(c2_atendido(n0));
            NVIC_DisableIRQ(irq);
        }
    }
}

/* ── C2-02 ── ponto i: prioridades (i >> 8, (i >> 4) & 15, i & 15) das
 * linhas TRIO; pendentes com PRIMASK = 1, depois liberadas. Registro: ordem(). */
static void caso_02(void)
{
    for (uint32_t i = 0U; i < 4096U; i++) {
        __disable_irq();
        for (uint32_t k = 0U; k < 3U; k++) {
            c2_prepara(TRIO[k], (i >> (8U - 4U * k)) & 15U);
            NVIC_EnableIRQ((IRQn_Type)TRIO[k]);
        }
        uint32_t n0 = c2_nlog;
        for (uint32_t k = 0U; k < 3U; k++) {
            NVIC_SetPendingIRQ((IRQn_Type)TRIO[k]);
        }
        c2_barreira();
        __enable_irq();
        __ISB();
        aguarda(n0 + 3U);
        c2_grava(ordem(n0));
    }
}

/* ── C2-03 ── ponto i: papel = i >> 8 (0: A = PAR[0], B = PAR[1]; 1: o
 * contrário), prioridade de A = (i >> 4) & 15, de B = i & 15. main pede A;
 * o tratador de A pede B e depois anota A | MARCA. Registro: ordem(). */
static void caso_03(void)
{
    for (uint32_t i = 0U; i < 512U; i++) {
        uint32_t a = PAR[i >> 8];
        uint32_t b = PAR[1U - (i >> 8)];
        c2_prepara(a, (i >> 4) & 15U);
        c2_prepara(b, i & 15U);
        NVIC_EnableIRQ((IRQn_Type)a);
        NVIC_EnableIRQ((IRQn_Type)b);
        an_linha = b;
        an_exc = 16U + a;
        c2_barreira();
        uint32_t n0 = c2_nlog;
        NVIC->STIR = a;
        c2_barreira();
        aguarda(n0 + 3U);
        c2_grava(ordem(n0));
        an_exc = 0U;
        NVIC_DisableIRQ((IRQn_Type)a);
        NVIC_DisableIRQ((IRQn_Type)b);
    }
}

/* C2-04: efeito da máscara corrente sobre as 16 prioridades. Para cada
 * prioridade p, a linha recebe p, é pedida e conferida; se ficou pendente
 * (mascarada), a pendência é limpa. Bit p = 1: foi atendida. */
static uint32_t efeito(void)
{
    uint32_t bits = 0U;
    for (uint32_t p = 0U; p < 16U; p++) {
        NVIC_SetPriority((IRQn_Type)LINHA_04, p);
        uint32_t n0 = c2_nlog;
        NVIC_SetPendingIRQ((IRQn_Type)LINHA_04);
        c2_barreira();
        c2_espera(4U);
        if (c2_nlog != n0) {
            bits |= 1U << p;
        }
        NVIC_ClearPendingIRQ((IRQn_Type)LINHA_04);
        c2_barreira();
    }
    return bits;
}

/* ── C2-04 ── três partes, nesta ordem:
 *   PRIMASK      p = 0..15: (atendida com PRIMASK = 1) | pendente << 4 | atendida depois de liberar << 8
 *   BASEPRI      b = 0..255: BASEPRI lido | efeito() << 8
 *   BASEPRI_MAX  c = 0..15, v = 0..255: BASEPRI = c << 4, BASEPRI_MAX = v; lido | efeito() << 8 */
static void caso_04(void)
{
    c2_prepara(LINHA_04, 0U);
    for (uint32_t p = 0U; p < 16U; p++) {
        NVIC_SetPriority((IRQn_Type)LINHA_04, p);
        NVIC_EnableIRQ((IRQn_Type)LINHA_04);
        __disable_irq();
        uint32_t n0 = c2_nlog;
        NVIC_SetPendingIRQ((IRQn_Type)LINHA_04);
        c2_barreira();
        c2_espera(4U);
        uint32_t s1 = c2_nlog - n0;
        uint32_t pend = NVIC_GetPendingIRQ((IRQn_Type)LINHA_04);
        __enable_irq();
        __ISB();
        c2_espera(4U);
        c2_grava(s1 | (pend << 4) | ((c2_nlog - n0) << 8));
    }
    NVIC_EnableIRQ((IRQn_Type)LINHA_04);
    for (uint32_t b = 0U; b < 256U; b++) {
        __set_BASEPRI(b);
        c2_barreira();
        uint32_t lido = __get_BASEPRI();
        c2_grava(lido | (efeito() << 8));
        __set_BASEPRI(0U);
        c2_barreira();
    }
    for (uint32_t c = 0U; c < 16U; c++) {
        for (uint32_t v = 0U; v < 256U; v++) {
            __set_BASEPRI(c << 4);
            __set_BASEPRI_MAX(v);
            c2_barreira();
            uint32_t lido = __get_BASEPRI();
            c2_grava(lido | (efeito() << 8));
            __set_BASEPRI(0U);
            c2_barreira();
        }
    }
    NVIC_DisableIRQ((IRQn_Type)LINHA_04);
}

/* ── C2-05 ── por linha livre: habilitada, pedida por STIR com o núcleo
 * executando NOPs. Registro: ordem(). O tempo vem dos ganchos (escrita no
 * STIR e primeiro endereço de c2_irq). */
#define NOP4() do { __NOP(); __NOP(); __NOP(); __NOP(); } while (0)
static void caso_05(void)
{
    for (uint32_t i = 0U; i < C2_N_LIVRE; i++) {
        uint32_t linha = c2_livres[i];
        c2_prepara(linha, 8U);
        NVIC_EnableIRQ((IRQn_Type)linha);
        c2_barreira();
        uint32_t n0 = c2_nlog;
        NVIC->STIR = linha;
        NOP4();
        NOP4();
        NOP4();
        NOP4();
        aguarda(n0 + 1U);
        c2_grava(ordem(n0));
        NVIC_DisableIRQ((IRQn_Type)linha);
    }
}

/* ── C2-06 ── duas rodadas com as 15 linhas livres pendentes com PRIMASK = 1
 * e prioridades distintas (rodada 0: linha i com 14 − i; rodada 1: i),
 * depois liberadas. Registro: as 15 exceções atendidas, em ordem. O tempo e
 * a ausência de instrução do fluxo principal vêm dos ganchos e do traço. */
static void caso_06(void)
{
    for (uint32_t r = 0U; r < 2U; r++) {
        __disable_irq();
        for (uint32_t i = 0U; i < C2_N_LIVRE; i++) {
            c2_prepara(c2_livres[i], r == 0U ? 14U - i : i);
            NVIC_EnableIRQ((IRQn_Type)c2_livres[i]);
        }
        uint32_t n0 = c2_nlog;
        for (uint32_t i = 0U; i < C2_N_LIVRE; i++) {
            NVIC_SetPendingIRQ((IRQn_Type)c2_livres[i]);
        }
        c2_barreira();
        __enable_irq();
        __ISB();
        aguarda(n0 + C2_N_LIVRE);
        for (uint32_t k = 0U; k < C2_N_LIVRE; k++) {
            c2_grava(c2_atendido(n0 + k));
        }
        for (uint32_t i = 0U; i < C2_N_LIVRE; i++) {
            NVIC_DisableIRQ((IRQn_Type)c2_livres[i]);
        }
    }
}

int main(void)
{
    c2_init();
    switch (c2_caso) {
    case 1U: caso_01(); break;
    case 2U: caso_02(); break;
    case 3U: caso_03(); break;
    case 4U: caso_04(); break;
    case 5U: caso_05(); break;
    case 6U: caso_06(); break;
    default: c2_falha();
    }
    c2_encerra();
}
