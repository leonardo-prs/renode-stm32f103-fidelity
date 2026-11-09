/*
 * src/c4/c4.c — C4, serial link: USART2 (transmitter, TX on PA2) → link L1 →
 * USART3 (receiver, RX on PB11), by polling; only C4-05 takes an interrupt.
 *
 * One case per boot (selected_case); each case is a list of bursts. c4_link()
 * configures both ends; c4_burst() sends a list of words and records, as it
 * happens, each write and each read:
 *
 *   record: [count] then count events of 2 words (only the first C4_MAX_EVENTS
 *           are recorded; count is the total, so an overflow is visible):
 *     word 0  DWT_CYCCNT at the event
 *     word 1  kind << 30 | SR << 16 | value
 *             kind 0 (C4_WRITE): SR of USART2 read just before the write, value written
 *             kind 1 (C4_READ):  SR of USART3 read just before DR, DR read
 *             kind 2 (C4_SEEN):  first RXNE seen while the read is deferred (value 0)
 *
 *   Document oracle (Renode)
 *   1  c4_01_link_enable        per point: 2 spaced words; only the control has every enable on
 *   2  c4_02_equal_link         per rate: the 8 words by TXE
 *   3  c4_03_frame_format       per format, the same at both ends: 4 words by TXE
 *   4  c4_04_slow_consumer      per delay: 6 words by TXE, read D cycles after RXNE
 *   5  c4_05_receive_interrupt  RXNEIE off, then on: USART3 served by its handler
 *   Board oracle (the same binary in Renode and on the board)
 *   6  c4_06_line_mismatch      per point (a transmitter rate or format the receiver does not
 *                               expect, or PA2 not connected): 8 words by TXE
 *
 * The same layout is decoded by scripts/c4.py. The point tables are repeated
 * in scripts/c4.py, in the same order. Clock: HSI 8 MHz, AHB/APB1/APB2 ÷ 1,
 * flash 0 wait states with prefetch, so f_CK of USART2/3 = PCLK1 = 8 MHz and
 * one bit lasts 16·USARTDIV = BRR cycles (RM0008 §27.3.4). Electrical rule (one
 * driver on the wire): PB11 stays an input with pull-up; PA2 becomes
 * alternate-function push-pull only after USART2 is enabled with TE (idle high).
 */
#include "case.h"
#include "stm32f1xx.h"
#include "stm32f1xx_ll_bus.h"
#include "stm32f1xx_ll_gpio.h"
#include "stm32f1xx_ll_rcc.h"
#include "stm32f1xx_ll_system.h"

extern uint32_t _estack[];

void USART3_IRQHandler(void);

/* Only the USART3 line has a handler (C4-05): any other exception ends the run. */
__attribute__((section(".isr_vector"), used))
void (*const c4_vectors[16 + USART3_IRQn + 1])(void) = {
    [0] = (void (*)(void))_estack,
    [1] = Reset_Handler,
    [2 ... 16 + USART3_IRQn - 1] = unexpected_exception,
    [16 + USART3_IRQn] = USART3_IRQHandler,
};

#define N_OF(a) (sizeof(a) / sizeof((a)[0]))

#define BRR_9600   832U                 /* USARTDIV 52: 9615.4 baud, bit 832 cycles */
#define BRR_115200 69U                  /* USARTDIV 4 + 5/16: 115 942 baud, bit 69 cycles */
#define M          USART_CR1_M
#define PCE        USART_CR1_PCE
#define PS         USART_CR1_PS
#define STOP2      USART_CR2_STOP_1
#define TX_ON      (USART_CR1_UE | USART_CR1_TE)
#define RX_ON      (USART_CR1_UE | USART_CR1_RE)

#define C4_MAX_EVENTS 24U
#define C4_WRITE      0U
#define C4_READ       1U
#define C4_SEEN       2U

/* One end of the link: BRR value (= bit time in HCLK cycles at f_CK = HCLK),
 * the whole CR1 (enables and frame bits M, PCE, PS) and CR2 (STOP). */
struct c4_end {
    uint16_t brr;
    uint16_t cr1;
    uint16_t cr2;
};

struct c4_burst {
    const uint16_t *data;   /* words written to USART2_DR */
    uint32_t n;
    uint32_t spacing;       /* 0: write when TXE = 1; else write k at k·spacing cycles from the start */
    uint32_t defer;         /* 0: read at each RXNE; else read only `defer` cycles after the 1st RXNE */
};

#define FRAME_MAX_BITS 11U      /* start + 9 data/parity + 1 stop; 8N2 also has 11 */
#define IDLE_FRAMES    4U       /* a burst ends after this many receiver frames without activity */

static void c4_wait(uint32_t cycles)
{
    uint32_t t0 = DWT->CYCCNT;
    while (DWT->CYCCNT - t0 < cycles) {
    }
}

static void c4_init(void)
{
    SCB->VTOR = (uint32_t)c4_vectors;
    __disable_irq();
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

    LL_RCC_SetSysClkSource(LL_RCC_SYS_CLKSOURCE_HSI);   /* HSI 8 MHz, AHB/APB1/APB2 ÷ 1 */
    LL_RCC_SetAHBPrescaler(LL_RCC_SYSCLK_DIV_1);
    LL_RCC_SetAPB1Prescaler(LL_RCC_APB1_DIV_1);
    LL_RCC_SetAPB2Prescaler(LL_RCC_APB2_DIV_1);
    LL_FLASH_SetLatency(LL_FLASH_LATENCY_0);
    LL_FLASH_EnablePrefetch();
    LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_GPIOA | LL_APB2_GRP1_PERIPH_GPIOB);
    LL_APB1_GRP1_EnableClock(LL_APB1_GRP1_PERIPH_USART2 | LL_APB1_GRP1_PERIPH_USART3);

    /* PB11 input with pull-up, before anything is driven. */
    LL_GPIO_SetPinMode(GPIOB, LL_GPIO_PIN_11, LL_GPIO_MODE_INPUT);
    LL_GPIO_SetPinPull(GPIOB, LL_GPIO_PIN_11, LL_GPIO_PULL_UP);

    USART3->CR1 = 0U;
    USART2->CR1 = 0U;
    USART2->BRR = BRR_115200;   /* direct: the bit time is an exact integer, never LL_USART_SetBaudRate */
    USART2->CR2 = 0U;           /* single writes: the frame is the object, so no read-modify-write */
    USART2->CR1 = USART_CR1_UE | USART_CR1_TE;              /* TX idle (high) */
    /* PA2 alternate-function push-pull only after TE holds the line high. */
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_2, LL_GPIO_MODE_ALTERNATE);
    LL_GPIO_SetPinSpeed(GPIOA, LL_GPIO_PIN_2, LL_GPIO_SPEED_FREQ_LOW);
}

/* Receiver off, transmitter reconfigured (TE sends an idle frame, RM0008
 * §27.3.2), receiver on (with RE it searches for a start bit, §27.3.3), and
 * RXNE/flags discarded after two frames of quiet line. Single CR1/CR2 writes:
 * the frame and the enables of each end are the object of the cases. */
static void c4_link(const struct c4_end *tx, const struct c4_end *rx)
{
    uint32_t slow = tx->brr > rx->brr ? tx->brr : rx->brr;
    USART3->CR1 = 0U;
    USART2->CR1 = 0U;
    USART2->BRR = tx->brr;      /* direct: exact integers, never LL_USART_SetBaudRate */
    USART2->CR2 = tx->cr2;
    USART2->CR1 = tx->cr1;
    c4_wait(2U * FRAME_MAX_BITS * slow);
    USART3->BRR = rx->brr;
    USART3->CR2 = rx->cr2;
    USART3->CR1 = rx->cr1;
    c4_wait(2U * FRAME_MAX_BITS * slow);
    (void)USART3->SR;
    (void)USART3->DR;
    (void)USART2->SR;
}

static uint32_t events;

static void note(uint32_t t, uint32_t kind, uint32_t sr, uint32_t value)
{
    if (events < C4_MAX_EVENTS) {
        record_value(t);
        record_value(kind << 30 | (sr & 0x3FFU) << 16 | (value & 0x1FFU));
    }
    events++;
}

/* Polled SR and DR: the transfer itself is the object, so no interrupt and no
 * LL status helper stands between the case and the flags. */
static void c4_burst(const struct c4_burst *b)
{
    uint32_t idle = IDLE_FRAMES * FRAME_MAX_BITS * USART3->BRR;
    uint32_t head = record_length;
    record_value(0U);
    events = 0U;
    uint32_t sent = 0U;
    uint32_t seen = 0U;             /* 1 after the first RXNE in a deferred read */
    uint32_t t_seen = 0U;
    uint32_t t0 = DWT->CYCCNT;
    uint32_t last = t0;             /* last write, read or first RXNE */
    for (;;) {
        uint32_t now = DWT->CYCCNT;
        if (sent < b->n) {
            uint32_t sr = USART2->SR;
            uint32_t due = b->spacing ? (now - t0 >= sent * b->spacing) : (sr & USART_SR_TXE);
            if (due) {
                uint32_t t = DWT->CYCCNT;
                USART2->DR = b->data[sent];
                note(t, C4_WRITE, sr, b->data[sent]);
                sent++;
                last = t;
                continue;
            }
        }
        uint32_t rsr = USART3->SR;
        if (rsr & USART_SR_RXNE) {
            uint32_t t = DWT->CYCCNT;
            if (b->defer && !seen) {
                seen = 1U;
                t_seen = t;
                last = t;
                note(t, C4_SEEN, rsr, 0U);
                continue;
            }
            if (!b->defer || t - t_seen >= b->defer) {
                uint32_t dr = USART3->DR;
                note(t, C4_READ, rsr, dr);
                last = t;
                continue;
            }
        }
        if (now - last >= idle) {
            break;
        }
    }
    if (head < RECORD_CAPACITY) {
        record[head] = events;
    }
}

/* ── C4-01 ── the link exists only when configured: the control, then one enable
 * missing per point. Words spaced by two frames, so no point depends on TXE. */
static const struct c4_end TX_01[3] = {
    {BRR_115200, TX_ON, 0U},            /* control */
    {BRR_115200, TX_ON, 0U},            /* receiver without RE */
    {BRR_115200, USART_CR1_UE, 0U},     /* transmitter without TE */
};
static const struct c4_end RX_01[3] = {
    {BRR_115200, RX_ON, 0U},
    {BRR_115200, USART_CR1_UE, 0U},
    {BRR_115200, RX_ON, 0U},
};
static const uint16_t WORDS_01[2] = {0x5AU, 0xA5U};
#define SPACING_01 (2U * 10U * BRR_115200)

static void c4_01_link_enable(void)
{
    const struct c4_burst b = {WORDS_01, N_OF(WORDS_01), SPACING_01, 0U};
    for (uint32_t k = 0U; k < N_OF(TX_01); k++) {
        c4_link(&TX_01[k], &RX_01[k]);
        c4_burst(&b);
    }
}

/* ── C4-02 ── the two rates; extremes, alternating patterns and an isolated bit at each end. */
static const uint16_t WORDS_02[8] = {0x00U, 0xFFU, 0x55U, 0xAAU, 0x01U, 0x80U, 0x7FU, 0xFEU};
static const uint16_t BRR_02[2] = {BRR_9600, BRR_115200};

static void c4_02_equal_link(void)
{
    for (uint32_t k = 0U; k < N_OF(BRR_02); k++) {
        const struct c4_end tx = {BRR_02[k], TX_ON, 0U};
        const struct c4_end rx = {BRR_02[k], RX_ON, 0U};
        const struct c4_burst b = {WORDS_02, N_OF(WORDS_02), 0U, 0U};
        c4_link(&tx, &rx);
        c4_burst(&b);
    }
}

/* ── C4-03 ── per format, the same at both ends: words whose MSB is written equal to
 * and different from what the frame carries there, with parity 0 and 1; 8N2 adds a
 * stop bit. */
static const struct c4_end TX_03[4] = {
    {BRR_115200, TX_ON | M, 0U},        /* 9N1 */
    {BRR_115200, TX_ON | M | PCE, 0U},  /* 8E1 */
    {BRR_115200, TX_ON | PCE, 0U},      /* 7E1 */
    {BRR_115200, TX_ON, STOP2},         /* 8N2 */
};
static const struct c4_end RX_03[4] = {
    {BRR_115200, RX_ON | M, 0U},        /* 9N1 */
    {BRR_115200, RX_ON | M | PCE, 0U},  /* 8E1 */
    {BRR_115200, RX_ON | PCE, 0U},      /* 7E1 */
    {BRR_115200, RX_ON, STOP2},         /* 8N2 */
};
static const uint16_t WORDS_03[4][4] = {
    {0x1A5U, 0x0A5U, 0x15AU, 0x05AU},   /* bit 8 = 1, 0, 1, 0 */
    {0x0A5U, 0x1A5U, 0x1A7U, 0x0A7U},   /* 0xA5 has 4 ones, parity 0; 0xA7 has 5, parity 1: bit 8 equal, different */
    {0x0A5U, 0x025U, 0x027U, 0x0A7U},   /* 0x25 has 3 ones, parity 1; 0x27 has 4, parity 0: bit 7 equal, different */
    {0x0A5U, 0x0A7U, 0x05AU, 0x000U},   /* words with no role in the frame */
};

static void c4_03_frame_format(void)
{
    for (uint32_t k = 0U; k < N_OF(TX_03); k++) {
        const struct c4_burst b = {WORDS_03[k], N_OF(WORDS_03[k]), 0U, 0U};
        c4_link(&TX_03[k], &RX_03[k]);
        c4_burst(&b);
    }
}

/* ── C4-04 ── contiguous frames (TX by TXE); the consumer reads only D cycles
 * after the first RXNE: 0.5, 1.5 and 3.5 frames of 690 cycles. */
static const uint16_t D_04[3] = {345U, 1035U, 2415U};
static const uint16_t WORDS_04[6] = {0x61U, 0x62U, 0x63U, 0x64U, 0x65U, 0x66U};

static void c4_04_slow_consumer(void)
{
    const struct c4_end tx = {BRR_115200, TX_ON, 0U};
    const struct c4_end rx = {BRR_115200, RX_ON, 0U};
    for (uint32_t k = 0U; k < N_OF(D_04); k++) {
        const struct c4_burst b = {WORDS_04, N_OF(WORDS_04), 0U, D_04[k]};
        c4_link(&tx, &rx);
        c4_burst(&b);
    }
}

/* ── C4-05 ── USART3 by interrupt. Written by the handler (and by main while RXNEIE = 0). */
static volatile uint32_t irq_entries;
static volatile uint32_t irq_t[C4_MAX_EVENTS];
static volatile uint32_t irq_sr[C4_MAX_EVENTS];
static volatile uint32_t irq_dr[C4_MAX_EVENTS];

void USART3_IRQHandler(void)
{
    uint32_t t = DWT->CYCCNT;
    uint32_t sr = USART3->SR;
    uint32_t dr = USART3->DR;           /* clears RXNE, so the line falls before the return */
    uint32_t n = irq_entries;
    if (n < C4_MAX_EVENTS) {
        irq_t[n] = t;
        irq_sr[n] = sr;
        irq_dr[n] = dr;
    }
    irq_entries = n + 1U;
}

static void c4_send(const uint16_t *data, uint32_t n)
{
    for (uint32_t i = 0U; i < n; i++) {
        while ((USART2->SR & USART_SR_TXE) == 0U) {
        }
        USART2->DR = data[i];
    }
}

/* One burst with what the handler saw so far. */
static void record_handler_entries(void)
{
    uint32_t n = irq_entries;
    record_value(n);
    events = 0U;
    for (uint32_t i = 0U; i < n && i < C4_MAX_EVENTS; i++) {
        note(irq_t[i], C4_READ, irq_sr[i], irq_dr[i]);
    }
}

static const uint16_t WORDS_05[4] = {0x31U, 0x32U, 0x33U, 0x34U};
#define WAIT_05 ((N_OF(WORDS_05) + IDLE_FRAMES) * FRAME_MAX_BITS * BRR_115200)

/* Three bursts: entries with RXNEIE = 0 (one word sent), the word read from the flag, entries
 * with RXNEIE = 1 (all words sent). The line and PRIMASK stay open in both, so only RXNEIE differs. */
static void c4_05_receive_interrupt(void)
{
    const struct c4_end tx = {BRR_115200, TX_ON, 0U};
    const struct c4_end rx_off = {BRR_115200, RX_ON, 0U};
    const struct c4_end rx_on = {BRR_115200, RX_ON | USART_CR1_RXNEIE, 0U};
    NVIC_EnableIRQ(USART3_IRQn);
    __enable_irq();

    c4_link(&tx, &rx_off);
    c4_send(WORDS_05, 1U);
    c4_wait(WAIT_05);
    record_handler_entries();
    uint32_t sr = USART3->SR;
    uint32_t dr = USART3->DR;
    record_value(1U);
    events = 0U;
    note(DWT->CYCCNT, C4_READ, sr, dr);

    irq_entries = 0U;                   /* main writes it only with RXNEIE = 0: no entry can happen */
    c4_link(&tx, &rx_on);
    c4_send(WORDS_05, N_OF(WORDS_05));
    c4_wait(WAIT_05);
    __disable_irq();
    record_handler_entries();
}

/* ── C4-06 ── the line: the receiver (9600, BRR 832, fraction 0, 8N1) gets a rate or a
 * format it does not expect, then the control with PA2 not connected. Δ = BRR_TX / 832 − 1
 * is the deviation of the bit time of the transmitter (RM0008 Tab. 193 read in bit time,
 * see scripts/c4.py). Each point is a class: the control, one divider step, inside the guaranteed
 * 3.75 % on each side, just outside it, far outside on each side, and a format mismatch. */
static const struct c4_end TX_06[9] = {
    {832U, TX_ON, 0U},                  /* Δ = 0: control */
    {831U, TX_ON, 0U},                  /* −0.12 %: one divider step */
    {808U, TX_ON, 0U},                  /* −2.88 %: inside the guaranteed 3.75 % */
    {858U, TX_ON, 0U},                  /* +3.12 %: inside, slow side */
    {800U, TX_ON, 0U},                  /* −3.85 %: just outside */
    {770U, TX_ON, 0U},                  /* −7.45 %: far outside */
    {904U, TX_ON, 0U},                  /* +8.65 %: far outside, slow side */
    {BRR_9600, TX_ON, STOP2},           /* 8N2 → 8N1: a stop bit more than the receiver */
    {BRR_9600, TX_ON | PCE, 0U},        /* 7E1 → 7O1: the opposite parity */
};
static const struct c4_end RX_06[9] = {
    {BRR_9600, RX_ON, 0U}, {BRR_9600, RX_ON, 0U}, {BRR_9600, RX_ON, 0U}, {BRR_9600, RX_ON, 0U},
    {BRR_9600, RX_ON, 0U}, {BRR_9600, RX_ON, 0U}, {BRR_9600, RX_ON, 0U}, {BRR_9600, RX_ON, 0U},
    {BRR_9600, RX_ON | PCE | PS, 0U},
};
#define WORD_06  0x55U          /* 4 ones in 7 bits: even parity 0, so 7O1 sees a parity error */
#define WORDS_06 8U

static void c4_06_line_mismatch(void)
{
    uint16_t words[WORDS_06];
    for (uint32_t i = 0U; i < WORDS_06; i++) {
        words[i] = WORD_06;
    }
    const struct c4_burst b = {words, WORDS_06, 0U, 0U};
    for (uint32_t k = 0U; k < N_OF(TX_06); k++) {
        c4_link(&TX_06[k], &RX_06[k]);
        c4_burst(&b);
    }
    /* The control with PA2 not alternate function: on the chip only the pull-up of PB11 holds the line. */
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_2, LL_GPIO_MODE_FLOATING);
    c4_link(&TX_06[0], &RX_06[0]);
    c4_burst(&b);
}

int main(void)
{
    c4_init();
    switch (selected_case) {
    case 1U: c4_01_link_enable(); break;
    case 2U: c4_02_equal_link(); break;
    case 3U: c4_03_frame_format(); break;
    case 4U: c4_04_slow_consumer(); break;
    case 5U: c4_05_receive_interrupt(); break;
    case 6U: c4_06_line_mismatch(); break;
    default: unexpected_exception();
    }
    finish_case();
}
