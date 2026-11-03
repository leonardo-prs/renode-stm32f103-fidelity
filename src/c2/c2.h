/*
 * src/c2/c2.h — comum aos firmwares do C2 (04-c2.typ). Rodam só no Renode.
 *
 * Cada firmware (sw.c, mon.c, tim.c) define main() e o tratador c2_irq,
 * para o qual apontam todas as linhas de interrupção. O caso a executar é
 * gravado pelo monitor em c2_caso antes da partida (instrumento verificado
 * no Q-01). O que o firmware viu vai para c2_rec; o gancho em c2_fim
 * despeja c2_status, c2_nrec e c2_rec[0..c2_nrec).
 *
 * Registro de atendimentos: c2_irq acrescenta o número da exceção (IPSR) a
 * c2_log, circular, e conta o atendimento em c2_vezes[exceção]. c2_nlog e
 * c2_log só são escritos por c2_irq; main só lê. Os casos que usam a ordem
 * de c2_log garantem que nenhuma preempção cai no meio de um acréscimo: os
 * pedidos acontecem em pontos fixos, e o acréscimo é o primeiro trabalho do
 * tratador. Cada elemento de c2_vezes só é escrito pelo tratador da própria
 * exceção (que não preempta a si mesmo), e vale em qualquer caso.
 * c2_pronto: rodada em que main está (só main escreve; o monitor lê).
 */
#ifndef C2_H
#define C2_H

#include <stdint.h>

#include "stm32f1xx.h"

#define C2_N_IRQ   43U          /* IRQ 0..42 da família medium-density (RM0008 Tab. 63) */
#define C2_N_LIVRE 15U
#define C2_LOG     64U          /* potência de 2: índice = c2_nlog % C2_LOG */
#define C2_REC     4608U        /* palavras de c2_rec */

/* Linhas sem fonte ligada na plataforma do projeto (renode/stm32f103_hsi8.repl):
 * WWDG, PVD, TAMPER, RTC, FLASH, RCC, ADC1_2, USB/CAN (4), SPI1, SPI2,
 * RTCAlarm, USBWakeUp. A mesma lista está em scripts/c2_comum.py (LIVRES). */
extern const uint8_t c2_livres[C2_N_LIVRE];

extern volatile uint32_t c2_caso;
extern volatile uint32_t c2_log[C2_LOG];
extern volatile uint32_t c2_nlog;
extern volatile uint32_t c2_vezes[16 + C2_N_IRQ];
extern volatile uint32_t c2_pronto;
extern volatile uint32_t c2_rec[C2_REC];
extern volatile uint32_t c2_nrec;
extern volatile uint32_t c2_status;

int main(void);
__attribute__((noreturn)) void Reset_Handler(void);
__attribute__((noipa, noreturn)) void c2_falha(void);
__attribute__((noipa)) void c2_fim(void);
__attribute__((noreturn)) void c2_encerra(void);
void c2_irq(void);
void c2_init(void);
void c2_grava(uint32_t valor);
void c2_espera(uint32_t voltas);

/* Primeiro trabalho de c2_irq: acrescenta a exceção em execução ao registro
 * e conta o atendimento. */
static inline uint32_t c2_anota(void)
{
    uint32_t exc = __get_IPSR() & 0x1FFU;
    uint32_t n = c2_nlog;
    c2_log[n % C2_LOG] = exc;
    c2_nlog = n + 1U;
    if (exc < 16U + C2_N_IRQ) {
        c2_vezes[exc]++;
    }
    return exc;
}

/* Exceção do k-ésimo atendimento (k = valor de c2_nlog antes dele). */
static inline uint32_t c2_atendido(uint32_t k)
{
    return c2_log[k % C2_LOG];
}

/* Recomendação da ARM depois de escrever no NVIC ou nas máscaras: o efeito
 * vale nas instruções seguintes. */
static inline void c2_barreira(void)
{
    __DSB();
    __ISB();
}

/* Linha desabilitada, sem pendência e com a prioridade dada (0..15). */
static inline void c2_prepara(uint32_t linha, uint32_t prio)
{
    NVIC_DisableIRQ((IRQn_Type)linha);
    NVIC_ClearPendingIRQ((IRQn_Type)linha);
    NVIC_SetPriority((IRQn_Type)linha, prio);
    c2_barreira();
}

#endif
