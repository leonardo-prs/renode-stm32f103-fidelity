/*
 * src/c2/mon.c — C2, etapa 3: pedidos pelo monitor (04-c2.typ).
 *
 * Os pedidos vêm do monitor (escrita no ISPR com a simulação parada, num
 * instante exato; scripts/c2_mon.py). O firmware só prepara as linhas,
 * anuncia em c2_pronto a rodada em que está e espera os atendimentos num
 * laço ocioso. A ordem e o tempo vêm dos ganchos e do traço; o registro do
 * firmware (c2_rec) guarda as contagens por rodada.
 *
 *   7  C2-07  chegada tardia             L = IRQ0 (prioridade 12), H = IRQ42 (4), 25 rodadas
 *   8  C2-08  chegada durante o retorno  X = IRQ0 (4), Y = IRQ42 (8), 13 rodadas
 *   9  C2-09  WFI e PRIMASK              W = IRQ20 (8), (a) PRIMASK = 0, (b) PRIMASK = 1
 */
#include "c2.h"

#define L_07 0U
#define H_07 42U
#define RODADAS_07 25U
#define X_08 0U
#define Y_08 42U
#define RODADAS_08 13U
#define W_09 20U

/* Exceção cujo tratador se alonga (C2-07: o de menor prioridade continua em
 * execução em toda a faixa varrida). Escrito só por main, antes dos pedidos. */
static volatile uint32_t lento;

void c2_irq(void)
{
    uint32_t exc = c2_anota();
    if (exc == lento) {
        c2_espera(20U);
    }
}

/* Rodadas: anuncia a rodada r + 1 e espera a linha `espera` ser atendida
 * r + 1 vezes. Grava as contagens das duas linhas ao fim de cada rodada. */
static void rodadas(uint32_t a, uint32_t b, uint32_t espera, uint32_t n)
{
    for (uint32_t r = 0U; r < n; r++) {
        c2_pronto = r + 1U;
        while (c2_vezes[16U + espera] <= r) {
        }
        c2_grava(c2_vezes[16U + a] | (c2_vezes[16U + b] << 16));
    }
}

static void caso_07(void)
{
    c2_prepara(L_07, 12U);
    c2_prepara(H_07, 4U);
    lento = 16U + L_07;
    NVIC_EnableIRQ((IRQn_Type)L_07);
    NVIC_EnableIRQ((IRQn_Type)H_07);
    c2_barreira();
    rodadas(L_07, H_07, L_07, RODADAS_07);  /* L termina por último em toda a faixa */
}

static void caso_08(void)
{
    c2_prepara(X_08, 4U);
    c2_prepara(Y_08, 8U);
    NVIC_EnableIRQ((IRQn_Type)X_08);
    NVIC_EnableIRQ((IRQn_Type)Y_08);
    c2_barreira();
    rodadas(X_08, Y_08, Y_08, RODADAS_08);  /* Y é atendida depois de X em toda a faixa */
}

/* ── C2-09 ── registro: atendimentos de W logo depois do WFI em (a); logo
 * depois do WFI em (b), ainda com PRIMASK = 1; depois de PRIMASK = 0. */
static void caso_09(void)
{
    c2_prepara(W_09, 8U);
    NVIC_EnableIRQ((IRQn_Type)W_09);
    __set_BASEPRI(0U);
    __enable_fault_irq();
    __enable_irq();
    c2_barreira();
    c2_pronto = 1U;                         /* (a) PRIMASK = 0 */
    __WFI();
    c2_grava(c2_vezes[16U + W_09]);
    __disable_irq();                        /* (b) PRIMASK = 1 */
    c2_barreira();
    c2_pronto = 2U;
    __WFI();
    c2_grava(c2_vezes[16U + W_09]);
    __enable_irq();
    __ISB();
    c2_grava(c2_vezes[16U + W_09]);
}

int main(void)
{
    c2_init();
    switch (c2_caso) {
    case 7U: caso_07(); break;
    case 8U: caso_08(); break;
    case 9U: caso_09(); break;
    default: c2_falha();
    }
    c2_encerra();
}
