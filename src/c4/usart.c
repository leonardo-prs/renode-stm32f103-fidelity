/**
 * @file    src/c4/usart.c
 * @brief   C4 — USART1 em loopback físico PA9 (TX) → PA10 (RX), por polling.
 *
 * Pergunta: o Renode reproduz integridade, quadro, divisor de baud, flags e
 * comportamento sob sobrecarga da USART1 como a placa?
 *
 * Concorrência neste cenário (recorte do autor): transmissão e recepção em
 * andamento enquanto o SOFTWARE tem capacidade limitada de atender a
 * recepção (leitura atrasada / produtor mais rápido que o consumidor). Não
 * há IRQ da USART: a matriz de preempção do NVIC é do C3.
 *
 * Limitação do loopback: a própria USART gera o estímulo que recebe. Mesmo
 * quadro em TX e RX permite verificar dados, configuração e tempo, mas NÃO
 * exercita detecção de erro de paridade/enquadramento (exigiria estímulo
 * divergente controlado).
 *
 * Clock: PCLK2 = HCLK = 8 MHz. BRR = USARTDIV × 16 (RM0008 §27.3.4,
 * oversampling 16): o host calcula o baud REALIZADO a partir do BRR gravado.
 * Timestamps vêm de polling (resolução = uma volta do laço) e marcam quando
 * o SOFTWARE viu a flag, não bordas na linha.
 *
 * As esperas deste cenário têm limites em ticks derivados do quadro.
 */
#include "board.h"
#include "fidelity.h"

#define FIRMWARE_ID 0x0401U
/* Versão LOCAL do payload C4; ABI FID3 externa permanece igual. O host
 * rejeita explicitamente snapshots anteriores, sem reinterpretar campos. */
#define C4_PAYLOAD 0x43340002U

/* BRR para PCLK2 = 8 MHz, oversampling 16. */
#define BRR_9600    0x0341U      /* 52 + 1/16   → 9603,8 baud */
#define BRR_115200  0x0045U      /* 4 + 5/16    → 115942 baud */
#define BRR_500000  0x0010U      /* 1           → 500000 baud */

/* Quadro 8N1 com BRR=69: 690 ticks, baud realizado ≈115942. */
#define FRAME_115200 690U

/* Formatos de quadro (CR1: M, PCE, PS; CR2: STOP). */
#define FMT_8N1  0U
#define FMT_7E1  (USART_CR1_PCE)
#define FMT_7O1  (USART_CR1_PCE | USART_CR1_PS)
#define FMT_8E1  (USART_CR1_M | USART_CR1_PCE)
#define FMT_9N1  (USART_CR1_M)
#define STOP_1   0U
#define STOP_2   USART_CR2_STOP_1

#define SR_ERRORS (USART_SR_PE | USART_SR_FE | USART_SR_NE | USART_SR_ORE)

#define SR_FLAGS (USART_SR_TXE | USART_SR_TC | USART_SR_RXNE | USART_SR_IDLE | USART_SR_ORE)

static uint32_t s_errors;
static uint32_t s_frame_ticks = FRAME_115200;   /* ticks de um quadro na config. atual */

/* ───────────────────────────── utilidades ───────────────────────────── */

/* Flags amostradas antes de qualquer DR; SR→DR pode limpar os erros. */
static uint32_t read_sr(void)
{
    uint32_t sr = USART1->SR;
    s_errors |= sr & SR_ERRORS;
    return sr;
}

static uint32_t limit_ticks(uint32_t frames)
{
    return frames * s_frame_ticks;
}

/* Espera (SR & mask) != 0 por até `frames` quadros. 1 = viu; 0 = timeout. */
static uint32_t wait_flag(uint32_t mask, uint32_t frames, uint32_t *when)
{
    uint32_t t0 = fid_now();
    while ((read_sr() & mask) == 0U) {
        if ((fid_now() - t0) > limit_ticks(frames)) {
            *when = 0U;
            return 0U;
        }
    }
    *when = fid_now();
    return 1U;
}

/* Drenagem de duração fixa e limitada a 3 quadros, após término de TX.
 * Não prolonga indefinidamente a espera se um periférico não esvaziar. */
static uint32_t drain(void)
{
    uint32_t n = 0U;
    uint32_t t0 = fid_now();
    while ((fid_now() - t0) < 3U * s_frame_ticks) {
        if ((read_sr() & USART_SR_RXNE) != 0U) {
            (void)USART1->DR;
            ++n;
        }
    }
    (void)read_sr();
    (void)USART1->DR;
    return n;
}

/* Configura a USART1 (UE = 0 durante a mudança) e espera o quadro de idle
 * que a habilitação de TE envia (TC = 1), depois esvazia o receptor. */
static uint32_t usart_config(uint32_t brr, uint32_t frame_bits, uint32_t cr1_format,
                             uint32_t cr2_stop)
{
    USART1->CR1 = 0U;
    USART1->BRR = brr;
    USART1->CR2 = cr2_stop;
    USART1->CR3 = 0U;
    /* Um bit dura 16·USARTDIV/PCLK2 = BRR ciclos de PCLK2 = BRR ticks (PCLK2 = HCLK). */
    s_frame_ticks = brr * frame_bits;
    USART1->CR1 = USART_CR1_UE | cr1_format | USART_CR1_TE | USART_CR1_RE;
    /* TC pode ainda estar em 1 (reset/ensaio anterior): aguarda o preâmbulo
     * antes de confiar nele. Nenhum dado experimental é escrito aqui. */
    fid_delay(2U * s_frame_ticks);
    uint32_t when;
    uint32_t ok = wait_flag(USART_SR_TC, 4U, &when);
    (void)drain();
    return ok;
}

static void put_bytes_packed(const uint8_t *bytes, uint32_t n)
{
    for (uint32_t i = 0U; i < n; i += 4U) {
        uint32_t w = 0U;
        for (uint32_t k = 0U; k < 4U && (i + k) < n; ++k) {
            w |= (uint32_t)bytes[i + k] << (8U * k);
        }
        fid_put(w);
    }
}

static uint8_t pattern(uint32_t i)
{
    return (uint8_t)(i * 37U + 11U);       /* 37 ímpar: 256 valores distintos */
}

/* Prefixo: versão, BRR/CR1/CR2/CR3 efetivamente lidos. Sufixo: erros
 * acumulados, SR final, término TX confirmado. Expectativas ficam no host. */
static void begin(uint32_t case_id)
{
    s_errors = 0U;
    fid_case_begin(case_id);
    fid_put(C4_PAYLOAD);
    fid_put(USART1->BRR);
    fid_put(USART1->CR1);
    fid_put(USART1->CR2);
    fid_put(USART1->CR3);
}

static void end(uint32_t ok)
{
    uint32_t when;
    uint32_t tx_done = wait_flag(USART_SR_TC, 4U, &when);
    uint32_t sr = read_sr();
    fid_put(s_errors);
    fid_put(sr & SR_FLAGS);
    fid_put(tx_done);
    fid_case_end(ok && tx_done ? FID_CASE_OK : FID_CASE_TIMEOUT);
}

/* ───────────────────────── integridade ───────────────────────── */

#define SEQ_N 64U
static uint8_t s_rx[SEQ_N];
static uint32_t s_t_write[SEQ_N];
static uint32_t s_t_read[SEQ_N];

/* U1: um byte isolado. */
static void case_single_byte(void)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(0x01U);
    uint32_t when;
    ok &= wait_flag(USART_SR_TXE, 4U, &when);
    uint32_t t_w = fid_now();
    USART1->DR = 0xA5U;
    uint32_t t_r;
    ok &= wait_flag(USART_SR_RXNE, 4U, &t_r);
    uint32_t sr = read_sr();
    uint32_t value = USART1->DR;
    fid_put(t_w);
    fid_put(t_r);
    fid_put(sr);
    fid_put(value);
    end(ok);
}

/* U2: 64 bytes um por vez (escreve, espera recepção, lê): sem pressão. */
static void case_stop_and_wait(void)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(0x02U);
    uint32_t received = 0U;
    for (uint32_t i = 0U; i < SEQ_N; ++i) {
        uint32_t t_r;
        if (!wait_flag(USART_SR_TC, 4U, &t_r) ||
            !wait_flag(USART_SR_TXE, 4U, &t_r)) {
            ok = 0U;
            break;
        }
        s_t_write[i] = fid_now();
        USART1->DR = pattern(i);
        if (wait_flag(USART_SR_RXNE, 4U, &t_r) == 0U) {
            ok = 0U;
            break;
        }
        s_rx[i] = (uint8_t)USART1->DR;
        s_t_read[i] = t_r;
        ++received;
    }
    fid_put(received);
    put_bytes_packed(s_rx, received);
    for (uint32_t i = 0U; i < received; ++i) {
        fid_put(s_t_read[i] - s_t_write[i]);
    }
    end(ok);
}

/*
 * Rajada full duplex: um laço único que escreve sempre que TXE = 1 e lê
 * sempre que RXNE = 1, até receber `n` bytes ou estourar o tempo. Registra
 * os instantes de escrita e de leitura de cada byte e se ORE apareceu.
 */
static uint32_t burst(uint32_t n, uint32_t *ore_seen, uint32_t *sent_out)
{
    uint32_t sent = 0U;
    uint32_t received = 0U;
    uint32_t t0 = fid_now();
    *ore_seen = 0U;
    while (received < n) {
        uint32_t sr = read_sr();
        if (sent < n && (sr & USART_SR_TXE) != 0U) {
            s_t_write[sent] = fid_now();
            USART1->DR = pattern(sent);
            ++sent;
        }
        if ((sr & USART_SR_ORE) != 0U) {
            *ore_seen = 1U;
        }
        if ((sr & USART_SR_RXNE) != 0U) {
            s_t_read[received] = fid_now();
            s_rx[received] = (uint8_t)USART1->DR;
            ++received;
        }
        if ((fid_now() - t0) > limit_ticks(n + 8U)) {
            break;
        }
    }
    *sent_out = sent;
    return received;
}

/* U3: rajada de 64 bytes em full duplex. */
static void case_burst(void)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(0x03U);
    uint32_t ore, sent;
    uint32_t received = burst(SEQ_N, &ore, &sent);
    ok &= (received == SEQ_N) ? 1U : 0U;
    fid_put(sent);
    fid_put(received);
    fid_put(ore);
    put_bytes_packed(s_rx, received);
    for (uint32_t i = 0U; i < sent; ++i) {
        fid_put(s_t_write[i]);
    }
    for (uint32_t i = 0U; i < received; ++i) {
        fid_put(s_t_read[i]);
    }
    end(ok);
}

/* U4: três taxas (BRR); 16 bytes em rajada; instantes de recepção. */
static void case_baud(uint32_t case_id, uint32_t brr)
{
    uint32_t ok = usart_config(brr, 10U, FMT_8N1, STOP_1);
    begin(case_id);
    uint32_t ore, sent;
    uint32_t received = burst(16U, &ore, &sent);
    ok &= (received == 16U) ? 1U : 0U;
    fid_put(sent);
    fid_put(received);
    fid_put(ore);
    put_bytes_packed(s_rx, received);
    fid_put(sent > 0U ? s_t_write[0] : 0U);
    for (uint32_t i = 0U; i < received; ++i) {
        fid_put(s_t_read[i]);
    }
    end(ok);
}

/*
 * U5: formatos de quadro. Com paridade, o bit de paridade ocupa o MSB da
 * palavra (bit 7 se M = 0, bit 8 se M = 1) e é lido em DR (RM0008 §27.3.7).
 * Dados úteis: 7 bits (7E1/7O1), 8 bits (8E1, 8N2), 9 bits (9N1).
 */
#define FMT_N 16U
static uint16_t s_rx9[FMT_N];

static void case_format(uint32_t case_id, uint32_t cr1_format, uint32_t cr2_stop,
                        uint32_t frame_bits, uint32_t data_mask)
{
    uint32_t ok = usart_config(BRR_115200, frame_bits, cr1_format, cr2_stop);
    begin(case_id);
    uint32_t received = 0U;
    uint32_t t_first = fid_now();
    for (uint32_t i = 0U; i < FMT_N; ++i) {
        uint32_t t_r;
        if (!wait_flag(USART_SR_TC, 4U, &t_r) ||
            !wait_flag(USART_SR_TXE, 4U, &t_r)) {
            ok = 0U;
            break;
        }
        if (i == 0U) {
            t_first = fid_now();
        }
        USART1->DR = (i * 73U + 5U) & data_mask;
        if (wait_flag(USART_SR_RXNE, 4U, &t_r) == 0U) {
            ok = 0U;
            break;
        }
        s_rx9[i] = (uint16_t)(USART1->DR & 0x1FFU);
        s_t_read[i] = t_r;
        ++received;
    }
    fid_put(data_mask);
    fid_put(received);
    fid_put(t_first);
    for (uint32_t i = 0U; i < received; i += 2U) {
        uint32_t hi = (i + 1U < received) ? s_rx9[i + 1U] : 0U;
        fid_put(s_rx9[i] | (hi << 16));
    }
    for (uint32_t i = 0U; i < received; ++i) {
        fid_put(s_t_read[i]);
    }
    end(ok);
}

/* ───────────────────────── flags e sobrecarga ───────────────────────── */

/*
 * U6: escreve 1 byte e registra cada mudança de (SR & SR_FLAGS) com o
 * instante, sem ler DR, por 3 quadros (RXNE e IDLE ficam setados). Depois
 * lê SR → DR (limpa RXNE e IDLE) e grava SR final.
 */
#define MAX_TRANSITIONS 8U

static void case_flags(void)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(0x06U);
    uint32_t sr_t[MAX_TRANSITIONS];
    uint32_t sr_v[MAX_TRANSITIONS];
    uint32_t n = 0U;
    uint32_t sr0 = read_sr() & SR_FLAGS;
    uint32_t t_w = fid_now();
    USART1->DR = 0x5AU;
    uint32_t last = sr0;
    uint32_t dropped = 0U;
    while ((fid_now() - t_w) < 3U * s_frame_ticks) {
        uint32_t sr = read_sr() & SR_FLAGS;
        if (sr != last) {
            if (n < MAX_TRANSITIONS) {
                sr_t[n] = fid_now();
                sr_v[n] = sr;
                ++n;
            } else {
                ++dropped;
            }
            last = sr;
        }
    }
    uint32_t t_end = fid_now();
    uint32_t sr_before = read_sr() & SR_FLAGS;
    uint32_t value = USART1->DR;
    uint32_t sr_after = read_sr() & SR_FLAGS;
    fid_put(sr0);
    fid_put(t_w);
    fid_put(n);
    fid_put(dropped);
    fid_put(t_end);
    for (uint32_t i = 0U; i < n; ++i) {
        fid_put(sr_t[i]);
        fid_put(sr_v[i]);
    }
    fid_put(sr_before);
    fid_put(value);
    fid_put(sr_after);
    end(ok);
}

/* U7: oferta espaçada por 1,5 quadro, sem leitura de DR. Espera 3
 * quadros desde a ÚLTIMA escrita e confirma TC antes de drenar. TXE é
 * respeitado e cada escrita/leitura é registrada: desvio da oferta impede
 * atribuir ausência de ORE ao receptor. k=1 é o controle sem sobrecarga.
 * O loopback não é uma fonte externa independente de estímulo. */
static void case_delayed_read(uint32_t case_id, uint32_t k)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(case_id);
    uint32_t spacing = (3U * s_frame_ticks) / 2U;
    uint32_t t0 = fid_now();
    uint32_t sent = 0U;
    for (uint32_t i = 0U; i < k; ++i) {
        while ((fid_now() - t0) < i * spacing) {
        }
        uint32_t when;
        if (!wait_flag(USART_SR_TXE, 4U, &when)) {
            ok = 0U;
            break;
        }
        s_t_write[sent] = fid_now();
        USART1->DR = pattern(i);
        ++sent;
    }
    if (sent > 0U) {
        while ((fid_now() - s_t_write[sent - 1U]) < 3U * s_frame_ticks) {
        }
    }
    uint32_t t_tc;
    ok &= wait_flag(USART_SR_TC, 4U, &t_tc);
    uint32_t sr_before = read_sr() & SR_FLAGS;
    uint32_t n = 0U;
    uint32_t ore_seen = (sr_before & USART_SR_ORE) != 0U;
    uint32_t t_d = fid_now();
    while ((fid_now() - t_d) < 3U * s_frame_ticks && n < SEQ_N) {
        uint32_t sr = read_sr();
        ore_seen |= (sr & USART_SR_ORE) != 0U ? 1U : 0U;
        if ((sr & USART_SR_RXNE) != 0U) {
            s_t_read[n] = fid_now();
            s_rx[n] = (uint8_t)USART1->DR;
            ++n;
        }
    }
    /* Limpa também ORE com RXNE=0; não descarta um byte pendente em silêncio. */
    if ((read_sr() & USART_SR_RXNE) == 0U) {
        (void)USART1->DR;
    }
    uint32_t sr_after = read_sr() & SR_FLAGS;
    uint32_t t_r, t_recovery;
    ok &= wait_flag(USART_SR_TXE, 4U, &t_r);
    t_recovery = fid_now();
    USART1->DR = 0xC3U;
    uint32_t rec_ok = wait_flag(USART_SR_RXNE, 4U, &t_r);
    uint32_t rec_sr = read_sr();
    uint32_t recovered = rec_ok ? USART1->DR : 0U;
    ok &= rec_ok;
    fid_put(k);
    fid_put(spacing);
    fid_put(sent);
    fid_put(t_d);
    fid_put(t_tc);
    fid_put(sr_before);
    fid_put(n);
    fid_put(ore_seen);
    fid_put(sr_after);
    fid_put(recovered);
    fid_put(rec_sr);
    fid_put(t_recovery);
    fid_put(t_r);
    put_bytes_packed(s_rx, n);
    for (uint32_t i = 0U; i < sent; ++i) {
        fid_put(s_t_write[i]);
    }
    for (uint32_t i = 0U; i < n; ++i) {
        fid_put(s_t_read[i]);
    }
    end(ok);
}

/*
 * U8: pressão de TX. Escreve n bytes respeitando TXE (produtor o mais
 * rápido que a USART deixa) e drena RX no mesmo laço. Instantes: 1ª e
 * última escrita aceita, TC após a última e último byte recebido.
 */
static void case_tx_pressure(uint32_t case_id, uint32_t n)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(case_id);
    uint32_t ore, sent;
    uint32_t received = burst(n, &ore, &sent);
    uint32_t t_tc;
    ok &= wait_flag(USART_SR_TC, 4U, &t_tc);
    ok &= (received == n) ? 1U : 0U;
    fid_put(n);
    fid_put(sent);
    fid_put(received);
    fid_put(ore);
    fid_put(sent > 0U ? s_t_write[0] : 0U);
    fid_put(sent > 0U ? s_t_write[sent - 1U] : 0U);
    fid_put(t_tc);
    fid_put(received > 0U ? s_t_read[received - 1U] : 0U);
    put_bytes_packed(s_rx, received);
    end(ok);
}

/* U9: RE=0 durante toda a entrega dos quatro quadros. RXNE indevido
 * não abrevia a janela nem contamina o byte novo após reabilitar RE. */
static void case_receiver_disabled(void)
{
    uint32_t ok = usart_config(BRR_115200, 10U, FMT_8N1, STOP_1);
    begin(0x09U);
    USART1->CR1 &= ~USART_CR1_RE;
    uint32_t rxne_seen = 0U;
    for (uint32_t i = 0U; i < 4U; ++i) {
        uint32_t when;
        if (!wait_flag(USART_SR_TXE, 4U, &when)) {
            ok = 0U;
            break;
        }
        uint32_t t_w = fid_now();
        USART1->DR = pattern(i);
        while ((fid_now() - t_w) < 2U * s_frame_ticks) {
            rxne_seen |= read_sr() & USART_SR_RXNE;
        }
        ok &= wait_flag(USART_SR_TC, 4U, &when);
    }
    uint32_t sr_off = read_sr() & SR_FLAGS;
    uint32_t discarded = drain();
    USART1->CR1 |= USART_CR1_RE;
    fid_delay(2U * s_frame_ticks);
    uint32_t t_r;
    ok &= wait_flag(USART_SR_TXE, 4U, &t_r);
    USART1->DR = 0x3CU;
    uint32_t received = wait_flag(USART_SR_RXNE, 4U, &t_r);
    uint32_t sr_on = read_sr();
    uint32_t value = received ? USART1->DR : 0U;
    ok &= received;
    fid_put(rxne_seen);
    fid_put(sr_off);
    fid_put(discarded);
    fid_put(sr_on);
    fid_put(value);
    end(ok);
}

/* ───────────────────────────── main ───────────────────────────── */

static void gpio_usart1_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN;
    (void)RCC->APB2ENR;
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_9, LL_GPIO_MODE_ALTERNATE);
    LL_GPIO_SetPinSpeed(GPIOA, LL_GPIO_PIN_9, LL_GPIO_SPEED_FREQ_HIGH);
    LL_GPIO_SetPinOutputType(GPIOA, LL_GPIO_PIN_9, LL_GPIO_OUTPUT_PUSHPULL);
    LL_GPIO_SetPinMode(GPIOA, LL_GPIO_PIN_10, LL_GPIO_MODE_INPUT);
    LL_GPIO_SetPinPull(GPIOA, LL_GPIO_PIN_10, LL_GPIO_PULL_UP);   /* linha ociosa em 1 */
}

#define CASE_COUNT 22U

int main(void)
{
    board_init();
    fid_init(FIRMWARE_ID, CASE_COUNT);
    gpio_usart1_init();

    case_single_byte();                              /* 0x01 */
    case_stop_and_wait();                            /* 0x02 */
    case_burst();                                    /* 0x03 */
    case_baud(0x11U, BRR_9600);
    case_baud(0x12U, BRR_115200);
    case_baud(0x13U, BRR_500000);
    case_format(0x21U, FMT_7E1, STOP_1, 10U, 0x7FU);
    case_format(0x22U, FMT_7O1, STOP_1, 10U, 0x7FU);
    case_format(0x23U, FMT_8E1, STOP_1, 11U, 0xFFU);
    case_format(0x24U, FMT_8N1, STOP_2, 11U, 0xFFU);
    case_format(0x25U, FMT_9N1, STOP_1, 11U, 0x1FFU);
    case_flags();                                    /* 0x06 */
    case_delayed_read(0x31U, 1U);
    case_delayed_read(0x32U, 2U);
    case_delayed_read(0x33U, 3U);
    case_delayed_read(0x34U, 4U);
    case_delayed_read(0x35U, 8U);
    case_tx_pressure(0x41U, 1U);
    case_tx_pressure(0x42U, 4U);
    case_tx_pressure(0x43U, 16U);
    case_tx_pressure(0x44U, 64U);
    case_receiver_disabled();                        /* 0x09 */

    USART1->CR1 = 0U;                                /* desliga antes de terminar */
    fid_finish();
}
