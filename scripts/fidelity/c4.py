"""C4 — oráculos e métricas (USART1 em loopback PA9 → PA10, polling).

Expectativas (RM0008 Rev. 21, cap. 27):
  - §27.3.4: baud = PCLK2 / (16 · USARTDIV), BRR = USARTDIV · 16; um bit
    dura BRR ciclos de PCLK2 (= HCLK aqui). Quadro = 1 start + palavra
    (8 ou 9 bits, M) + stop (1 ou 2). Com paridade, a palavra INCLUI o bit
    de paridade no MSB (§27.3.7): 7E1/7O1 = 7 dados, 8E1 = 8 dados.
  - §27.6.1 (SR): TXE = TDR vazio; TC = fim de quadro com TXE = 1; RXNE =
    dado em RDR; IDLE = linha ociosa após recepção; ORE = novo byte
    completo com RXNE = 1 (o byte novo se perde; RDR mantém o anterior).
    RXNE/IDLE/ORE limpos pela sequência leitura de SR → leitura de DR.
  - RE = 0: receptor desligado, nada é recebido.
Expectativa de PARIDADE recebida: o bit lido no MSB de DR é a paridade
calculada pelo transmissor (o loopback não injeta erro: PE nunca deve
aparecer e isto NÃO testa a detecção de erro).
Timestamps vêm de polling (RES_POLL) e marcam quando o software viu a
flag; não são bordas na linha.
"""
from __future__ import annotations

from statistics import median

from .abi import unwrap_from
from .model import RES_POLL, RunEval

SR_TXE, SR_TC, SR_RXNE, SR_IDLE, SR_ORE = 0x80, 0x40, 0x20, 0x10, 0x08
CR1_M, CR1_PCE, CR1_PS = 1 << 12, 1 << 10, 1 << 9
CR2_STOP2 = 1 << 13

FORMATS = {0x21: "7E1", 0x22: "7O1", 0x23: "8E1", 0x24: "8N2", 0x25: "9N1"}
CASES = {0x01: "byte isolado", 0x02: "64 bytes sem pressão (stop-and-wait)",
         0x03: "rajada full duplex 64 bytes", 0x11: "baud 9600", 0x12: "baud 115200",
         0x13: "baud 500000", **{k: f"quadro {v}" for k, v in FORMATS.items()},
         0x06: "sequência de flags TXE/TC/RXNE/IDLE",
         0x31: "leitura atrasada k=1", 0x32: "leitura atrasada k=2",
         0x33: "leitura atrasada k=3", 0x34: "leitura atrasada k=4",
         0x35: "leitura atrasada k=8", 0x41: "pressão TX n=1", 0x42: "pressão TX n=4",
         0x43: "pressão TX n=16", 0x44: "pressão TX n=64", 0x09: "RE desligado"}
PLANNED = [0x01, 0x02, 0x03, 0x11, 0x12, 0x13, 0x21, 0x22, 0x23, 0x24, 0x25, 0x06,
           0x31, 0x32, 0x33, 0x34, 0x35, 0x41, 0x42, 0x43, 0x44, 0x09]
GROUP = {0x01: "integridade", 0x02: "integridade", 0x03: "rajada full duplex",
         0x11: "divisor de baud", 0x12: "divisor de baud", 0x13: "divisor de baud",
         **{k: "formato de quadro (paridade/stop/9 bits)" for k in FORMATS},
         0x06: "flags TXE/TC/RXNE/IDLE",
         **{k: "sobrecarga RX (ORE, leitura atrasada)" for k in range(0x31, 0x36)},
         **{k: "pressão TX (TXE, buffering)" for k in range(0x41, 0x45)},
         0x09: "habilitação do receptor (RE)"}


def label(case_id: int) -> str:
    return f"c4/{case_id:02x}"


def pattern(i: int) -> int:
    return (i * 37 + 11) & 0xFF


def unpack_bytes(words, n):
    out = []
    for w in words:
        out += [(w >> (8 * k)) & 0xFF for k in range(4)]
    return out[:n]


def frame_bits(cr1: int, cr2: int) -> int:
    return 1 + (9 if cr1 & CR1_M else 8) + (2 if cr2 & CR2_STOP2 else 1)


def parity_word(value: int, cr1: int) -> int:
    """Palavra que o receptor lê em DR para o valor escrito (com paridade no MSB)."""
    word_bits = 9 if cr1 & CR1_M else 8
    if not cr1 & CR1_PCE:
        return value & ((1 << word_bits) - 1)
    data_bits = word_bits - 1
    data = value & ((1 << data_bits) - 1)
    ones = bin(data).count("1")
    parity = ones & 1 if not cr1 & CR1_PS else (ones + 1) & 1     # par: total par
    return data | (parity << data_bits)


def evaluate(snap) -> RunEval:
    ev = RunEval("c4")
    for case_id in PLANNED:
        name = label(case_id)
        c = snap.case(case_id)
        if c is None:
            ev.problems.append(f"{name}: caso ausente")
            continue
        ev.case_status[name] = c.status
        w = list(c.words)
        brr, cr1, cr2 = w[:3]
        bit = brr                                  # ticks por bit (PCLK2 = HCLK)
        frame = bit * frame_bits(cr1, cr2)
        HANDLERS[case_id](ev, name, case_id, w[3:], brr, cr1, cr2, frame)
    return ev


def _single(ev, name, cid, d, brr, cr1, cr2, frame):
    t_w, t_r, sr, value = d
    ev.check(name, "byte recebido", 0xA5, value & 0xFF)
    ev.check(name, "RXNE visto", True, t_r != 0)
    if t_r:
        ev.metric(name, "write_to_rxne", unwrap_from(t_w, t_r), resolution=RES_POLL,
                  predicted=frame)


def _stop_and_wait(ev, name, cid, d, brr, cr1, cr2, frame):
    n = d[0]
    ev.check(name, "bytes recebidos", 64, n)
    rx = unpack_bytes(d[1:1 + (n + 3) // 4], n)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(64)], rx)
    lat = d[1 + (n + 3) // 4:]
    if lat:
        ev.metric(name, "latency_median", median(lat), resolution=RES_POLL, predicted=frame)
        ev.metric(name, "latency_max", max(lat), resolution=RES_POLL)


def _burst(ev, name, cid, d, brr, cr1, cr2, frame, n_expected=64):
    n, ore = d[0], d[1]
    words_rx = (n + 3) // 4
    rx = unpack_bytes(d[2:2 + words_rx], n)
    ev.check(name, "bytes recebidos", n_expected, n)
    ev.check(name, "ORE durante a rajada", 0, ore)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(n_expected)], rx)
    return rx, d[2 + words_rx:]


def _burst64(ev, name, cid, d, brr, cr1, cr2, frame):
    rx, rest = _burst(ev, name, cid, d, brr, cr1, cr2, frame)
    n = len(rx)
    writes, reads = rest[:64], rest[64:64 + n]
    if n >= 2:
        gaps = [unwrap_from(a, b) for a, b in zip(reads, reads[1:])]
        ev.metric(name, "rx_interval_median", median(gaps), resolution=RES_POLL, predicted=frame)
        ev.metric(name, "burst_duration", unwrap_from(writes[0], reads[-1]), resolution=RES_POLL,
                  predicted=64 * frame)
        wgaps = [unwrap_from(a, b) for a, b in zip(writes, writes[1:])]
        ev.metric(name, "tx_accept_interval_median", median(wgaps), resolution=RES_POLL,
                  predicted=frame)


def _baud(ev, name, cid, d, brr, cr1, cr2, frame):
    n, ore = d[0], d[1]
    rx = unpack_bytes(d[2:6], n)
    ev.check(name, "bytes recebidos", 16, n)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(16)], rx)
    t_first, reads = d[6], d[7:7 + n]
    # baud = PCLK2 / (16·USARTDIV) = PCLK2 / BRR (PCLK2 = HCLK nominal).
    ev.extra.setdefault("baud", {})[name] = {"brr": brr, "baud_realized": 8_000_000 / brr}
    if n >= 2:
        gaps = [unwrap_from(a, b) for a, b in zip(reads, reads[1:])]
        ev.metric(name, "frame_period_median", median(gaps), resolution=RES_POLL, predicted=frame)
        ev.metric(name, "first_byte_latency", unwrap_from(t_first, reads[0]),
                  resolution=RES_POLL, predicted=frame)


def _format(ev, name, cid, d, brr, cr1, cr2, frame):
    mask, n, t_first = d[0], d[1], d[2]
    values = []
    for wv in d[3:3 + (n + 1) // 2]:
        values += [wv & 0xFFFF, wv >> 16]
    values = values[:n]
    reads = d[3 + (n + 1) // 2:3 + (n + 1) // 2 + n]
    sent = [(i * 73 + 5) & mask for i in range(16)]
    expected = [parity_word(v, cr1) for v in sent]
    ev.check(name, "palavras recebidas", 16, n)
    ev.check(name, "dados úteis (sem o bit de paridade)", [v & mask for v in sent],
             [v & mask for v in values])
    if cr1 & CR1_PCE:
        ev.check(name, "bit de paridade lido no MSB de DR", expected, values)
    else:
        ev.check(name, "palavra completa recebida", expected, values)
    if n >= 2:
        # Stop-and-wait: intervalo entre RXNE = quadro + tempo de software.
        ev.metric(name, "write_to_rxne_first", unwrap_from(t_first, reads[0]),
                  resolution=RES_POLL, predicted=frame)


def _flags(ev, name, cid, d, brr, cr1, cr2, frame):
    sr0, t_w, n = d[0], d[1], d[2]
    trans = [(d[3 + 2 * i], d[4 + 2 * i]) for i in range(n)]
    sr_before, value, sr_after = d[3 + 2 * n:6 + 2 * n]
    ev.extra.setdefault("flag_transitions", {})[name] = [
        (unwrap_from(t_w, t), f"{sr:#04x}") for t, sr in trans]
    seen_tc_low = any(not sr & SR_TC for _, sr in trans)
    ev.check(name, "SR inicial TXE|TC", SR_TXE | SR_TC, sr0)
    ev.check(name, "TC cai durante a transmissão", True, seen_tc_low)
    ev.check(name, "RXNE e IDLE setados ao fim (sem ler DR)", SR_RXNE | SR_IDLE,
             sr_before & (SR_RXNE | SR_IDLE))
    ev.check(name, "byte recebido", 0x5A, value & 0xFF)
    ev.check(name, "SR → DR limpa RXNE e IDLE", 0, sr_after & (SR_RXNE | SR_IDLE))

    def first(mask, on=True):
        for t, sr in trans:
            if bool(sr & mask) == on:
                return unwrap_from(t_w, t)
        return None
    for flag, mask, pred in (("rxne", SR_RXNE, frame), ("idle", SR_IDLE, 2 * frame),
                             ("tc", SR_TC, frame)):
        when = first(mask, True) if flag != "tc" or seen_tc_low else None
        if when is not None:
            ev.metric(name, f"write_to_{flag}", when, resolution=RES_POLL, predicted=pred)


def _delayed(ev, name, cid, d, brr, cr1, cr2, frame):
    k, spacing, sr_before, n, ore, sr_after, recovered = d[:7]
    rx = unpack_bytes(d[7:], n)
    if k == 1:
        ev.check(name, "bytes preservados", [pattern(0)], rx)
        ev.check(name, "ORE", 0, ore)
    else:
        ev.check(name, "bytes preservados (RDR mantém o 1º)", [pattern(0)], rx)
        ev.check(name, "ORE observado", 1, ore)
    ev.check(name, "flags limpas após drenagem", 0, sr_after & (SR_RXNE | SR_ORE))
    ev.check(name, "recuperação: byte seguinte íntegro", 0xC3, recovered & 0xFF)
    ev.metric(name, "bytes_buffered", n, unit="bytes", resolution=0)
    ev.extra.setdefault("buffered", {})[name] = {"k": k, "received": rx}


def _tx_pressure(ev, name, cid, d, brr, cr1, cr2, frame):
    n, received, ore, t_first, t_last_w, t_tc, t_last_r = d[:7]
    rx = unpack_bytes(d[7:], received)
    ev.check(name, "bytes recebidos", n, received)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(n)], rx)
    ev.check(name, "TC observado ao fim", True, t_tc != 0)
    # Produtor limitado por TXE: TDR + registrador de deslocamento →
    # a n-ésima escrita só é aceita ~ (n − 2) quadros depois da 1ª.
    ev.metric(name, "producer_time", unwrap_from(t_first, t_last_w), resolution=RES_POLL,
              predicted=max(n - 2, 0) * frame)
    if t_tc:
        ev.metric(name, "write_to_tc", unwrap_from(t_first, t_tc), resolution=RES_POLL,
                  predicted=n * frame)
    if received:
        ev.metric(name, "delivery_time", unwrap_from(t_first, t_last_r), resolution=RES_POLL,
                  predicted=n * frame)


def _receiver_disabled(ev, name, cid, d, brr, cr1, cr2, frame):
    rxne_seen, sr_off, value = d
    ev.check(name, "RXNE com RE = 0", 0, rxne_seen)
    ev.check(name, "byte após religar RE", 0x3C, value & 0xFF)


HANDLERS = {
    0x01: _single, 0x02: _stop_and_wait, 0x03: _burst64,
    0x11: _baud, 0x12: _baud, 0x13: _baud,
    0x21: _format, 0x22: _format, 0x23: _format, 0x24: _format, 0x25: _format,
    0x06: _flags,
    0x31: _delayed, 0x32: _delayed, 0x33: _delayed, 0x34: _delayed, 0x35: _delayed,
    0x41: _tx_pressure, 0x42: _tx_pressure, 0x43: _tx_pressure, 0x44: _tx_pressure,
    0x09: _receiver_disabled,
}
