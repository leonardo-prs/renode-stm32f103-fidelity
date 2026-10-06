/**
 * @file    src/c1_core.c
 * @brief   C1 — calibracao de nucleo: blocos de custo fixo sob DWT CYCCNT.
 *
 * Purpose: medir o custo medio por iteracao de kernels nucleares do
 * Cortex-M3 (STM32F103C8T6 @ HSI 8 MHz) com IRQs mascaradas, de forma
 * identica no hardware e no Renode. Serve de linha de base ("o simulador
 * conta os mesmos ciclos que o silicio?") antes dos cenarios com
 * perifericos/IRQ (C2+).
 *
 * Hipotese H1 (ref): para sequencias deterministas de instrucoes, sem
 * espera de barramento, IRQ ou DMA, o Renode reproduz a contagem de
 * ciclos do hardware dentro de margem aceitavel. C1 testa H1 no caso
 * mais favoravel possivel.
 *
 * Block set (decidido, 6 nucleares + 1 apendice; B9 cortado):
 * | #  | Bloco                  | Kernel por iteracao                        |
 * |----|------------------------|--------------------------------------------|
 * | B1 | ALU                    | add/sub/xor/shift-add                      |
 * | B23| mul+div fundidos       | MUL u32 fixa + DIV u32 + DIV s32 (fixos)   |
 * | B4 | SRAM load/store        | store+load em mem[4] (SRAM, nao-const)     |
 * | B5 | flash literal load     | load de ctab[4] (const -> Flash)           |
 * | B6 | branch taken/not-taken | if alternado (paridade de i^(i>>1))        |
 * | B7 | call/ret               | chamada noinline b7_callee(acc)            |
 * | B8 | GPIO BSRR (apendice)   | set+reset PC13 + acc+=i (fora do nucleo)   |
 *
 * Layout de saida (lido via GDB dump, sem printf/UART):
 *   7 blocos x K=100 repeticoes, N=1000 iteracoes por medida.
 *   c1_results[rep*7+bi] = DELTA BRUTO (t1-t0, uint32, sem divisao —
 *   a media /1000 truncava os deltas virtuais pequenos; a analise
 *   divide offline), ordem de bloco B1,B23,B4,B5,B6,B7,B8. c1_n=700
 *   ao final, c1_done=1 (0xFE = sem CYCCNT no alvo).
 *
 * Fixed-operand rationale: a divisao do M3 e data-dependent (2-12
 * ciclos; quociente pequeno = rapido). Operandos fixos
 * (1000000U/7U, -1000000/7) removem essa fonte de variancia para que
 * HW e Renode comparem o mesmo ponto operacional. O MUL tambem usa
 * operandos fixos pelo mesmo motivo (early-termination do mult).
 *
 * Loop order: para cada rep 0..99 medem-se os 7 blocos em sequencia
 * (rep externo, bloco interno) para intercalar contra deriva lenta
 * (temperatura do HSI, tensao) em vez de medir 100x B1 seguido.
 *
 * Note Debug -O0: a comparacao HW-vs-Renode usa o MESMO ELF; o nivel
 * de -O desloca o custo absoluto (barreira asm + sink volatil impedem
 * eliminacao em qualquer -O) mas afeta ambos os lados por igual.
 */

#include "board.h"                      /* CMSIS (DWT/CoreDebug/__disable_irq) + LED_BUILTIN_* */
#include "periph.h"                     /* led_init() */
#include "trace.h"                      /* trace_init()/trace_emit(): IDs 0x01-0x0E (enter/exit por bloco) */

/* Trace overhead (documentado): cada trace_emit = 1 load (base do ring) +
 * escrita no ring buffer em SRAM, ~10-20 ciclos. Chamadas colocadas FORA
 * das janelas t0/t1, apos o store em c1_results — os deltas DWT por bloco
 * nao incluem o custo do trace. */

/* --- Exported contract (nomes exatos; GDB dump depende) --- */
volatile uint32_t c1_results[700];
volatile uint32_t c1_n;
volatile uint8_t  c1_done;

/* --- File-static data --- */
static volatile uint32_t g_sink;        /* sorvedouro anti-eliminacao (volatil) */

static uint32_t s_mem[4];               /* SRAM: store+load (B4), nao-const de proposito */

static const uint32_t s_ctab[4] = {     /* Flash: tabela literal (B5) */
    0xDEADBEEFU, 0x12345678U, 0x0BADF00DU, 0xFEEDC0DEU
};

/* --- Prototypes (exigidos por -Wmissing-prototypes; todo handler-free file) --- */
static uint32_t b7_callee(uint32_t x);

/* Callee B7: noinline para que cada iteracao pague call+ret de verdade. */
static uint32_t b7_callee(uint32_t x)
{
    return x + 0x5A5A5A5AU;
}

/**
 * @brief Entry C1 (build/c1/firmware.elf).
 *        Nunca retorna (IRQs mascaradas; GDB externo faz halt p/ dump).
 *
 * Perifericos ligados: SOMENTE GPIOC (PC13, usado pelo bloco B8).
 * Nenhuma IRQ habilitada no NVIC; SysTick no estado de reset (off).
 */
int main(void)
{
    board_init();
    trace_init();                       /* ring de trace antes de qualquer emit */
    led_init();

    SysTick->CTRL = 0U;                 /* defensivo: sem tick durante a calibracao */

    /* DWT: habilita traco + contador de ciclos, zera. */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    DWT->CYCCNT = 0U;
    if ((DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk) != 0U)
    {
        c1_done = 0xFEU;                /* alvo sem CYCCNT: sinaliza e estaciona */
        for (;;)
        {
        }
    }

    __disable_irq();                    /* corrida inteira com IRQs mascaradas */

    for (uint32_t rep = 0U; rep < 100U; ++rep)
    {
        uint32_t t0;
        uint32_t t1;
        uint32_t acc;

        /* B1 ALU */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            acc += 0x11111111U;
            acc -= 0x22222222U;
            acc ^= 0x33333333U;
            acc += (acc << 1);
            __asm__ volatile ("" : "+r" (acc));
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 0U] = (t1 - t0);
        trace_emit(0x01U);                /* B1 enter */
        trace_emit(0x02U);                /* B1 exit */

        /* B23 mul+div fundidos, operandos fixos (div M3 e data-dependent 2-12c) */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            uint32_t p = 0x12345678U * 0x9ABCDEF1U;
            uint32_t q = 1000000U / 7U;
            uint32_t r = (uint32_t)((int32_t)(-1000000) / 7);
            acc += p + q + r;
            __asm__ volatile ("" : "+r" (acc));
            (void)i;
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 1U] = (t1 - t0);
        trace_emit(0x03U);                /* B23 enter */
        trace_emit(0x04U);                /* B23 exit */

        /* B4 SRAM load/store */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            s_mem[i & 3U] = acc + i;
            acc += s_mem[(i + 1U) & 3U];
            __asm__ volatile ("" : "+r" (acc));
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 2U] = (t1 - t0);
        trace_emit(0x05U);                /* B4 enter */
        trace_emit(0x06U);                /* B4 exit */

        /* B5 flash literal load */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            acc += s_ctab[i & 3U];
            __asm__ volatile ("" : "+r" (acc));
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 3U] = (t1 - t0);
        trace_emit(0x07U);                /* B5 enter */
        trace_emit(0x08U);                /* B5 exit */

        /* B6 branch taken/not-taken alternado */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            if (((i ^ (i >> 1)) & 1U) != 0U)
            {
                acc += i;
            }
            else
            {
                acc -= i;
            }
            __asm__ volatile ("" : "+r" (acc));
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 4U] = (t1 - t0);
        trace_emit(0x09U);                /* B6 enter */
        trace_emit(0x0AU);                /* B6 exit */

        /* B7 call/ret */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            acc = b7_callee(acc);
            __asm__ volatile ("" : "+r" (acc));
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 5U] = (t1 - t0);
        trace_emit(0x0BU);                /* B7 enter */
        trace_emit(0x0CU);                /* B7 exit */

        /* B8 GPIO BSRR (apendice: unico bloco fora do nucleo CPU/mem) */
        t0 = DWT->CYCCNT;
        acc = 0U;
        for (uint32_t i = 0U; i < 1000U; ++i)
        {
            LL_GPIO_SetOutputPin(LED_BUILTIN_GPIO_Port, LED_BUILTIN_Pin);
            LL_GPIO_ResetOutputPin(LED_BUILTIN_GPIO_Port, LED_BUILTIN_Pin);
            acc += i;
            __asm__ volatile ("" : "+r" (acc));
        }
        t1 = DWT->CYCCNT;
        g_sink = acc;
        c1_results[rep * 7U + 6U] = (t1 - t0);
        trace_emit(0x0DU);                /* B8 enter */
        trace_emit(0x0EU);                /* B8 exit */
    }

    c1_n = 700U;
    __DSB();
    c1_done = 1U;
    for (;;)
    {
    }
}
