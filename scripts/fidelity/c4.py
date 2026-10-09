"""C4 — oráculos e métricas (USART1 em loopback PA9 → PA10, polling).

Expectativas (RM0008 Rev. 21, cap. 27):
  - §27.3.4: baud = PCLK2 / (16 · USARTDIV), BRR = USARTDIV · 16; um bit
    dura BRR ciclos de PCLK2 (= HCLK aqui). Quadro = 1 start + palavra
    (8 ou 9 bits, M) + stop (1 ou 2). Com paridade, a palavra INCLUI o bit
    de paridade no MSB (§27.3.7): 7E1/7O1 = 7 dados, 8E1 = 8 dados.
  - §27.6.1 (SR): TXE = TDR vazio; TC = fim de quadro com TXE = 1; RXNE =
    dado em RDR; IDLE = linha ociosa após recepção; ORE = novo byte
    completo com RXNE = 1 (o byte novo se perde; RDR mantém o anterior).
    RXNE limpo por leitura de DR; IDLE/ORE por leitura de SR → DR.
  - RE = 0: receptor desligado, nada é recebido.
Expectativa de PARIDADE recebida: o bit lido no MSB de DR é a paridade
calculada pelo transmissor (§27.6.2). O loopback não injeta erro: PE não deve
aparecer em condições normais; isto NÃO testa a detecção de erro.
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


def frame_bits(cr1: int, cr2: int) -> float:
    stop = (1, 0.5, 2, 1.5)[(cr2 >> 12) & 3]
    return 1 + (9 if cr1 & CR1_M else 8) + stop


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


# Contratos fixos por ID, independentes dos registradores observados.
CONFIG = {cid: (69, 0, 0) for cid in PLANNED}
CONFIG.update({0x11: (833, 0, 0), 0x13: (16, 0, 0),
               0x21: (69, CR1_PCE, 0), 0x22: (69, CR1_PCE | CR1_PS, 0),
               0x23: (69, CR1_M | CR1_PCE, 0), 0x24: (69, 0, CR2_STOP2),
               0x25: (69, CR1_M, 0)})
MASKS = {0x21: 0x7F, 0x22: 0x7F, 0x23: 0xFF, 0x24: 0xFF, 0x25: 0x1FF}
DELAYED_K = {0x31: 1, 0x32: 2, 0x33: 3, 0x34: 4, 0x35: 8}
PRESSURE_N = {0x41: 1, 0x42: 4, 0x43: 16, 0x44: 64}
PAYLOAD_VERSION = 0x43340002
CR1_ENABLE = (1 << 13) | (1 << 3) | (1 << 2)  # UE, TE, RE; IRQs desligadas
SR_LINE_ERRORS = 0x07                          # PE, FE, NE
SR_FLAGS = SR_TXE | SR_TC | SR_RXNE | SR_IDLE | SR_ORE
CORE_HZ = 8_000_000


def _length(d, expected):
    if len(d) != expected:
        raise ValueError(f"payload tem {len(d)} palavras; esperado {expected}")


def _count(n, maximum=64):
    if not 0 <= n <= maximum:
        raise ValueError(f"contagem {n} fora de 0..{maximum}")


def _ordered(ticks):
    # Também rejeita intervalos negativos/ambíguos sem inventar múltiplos wraps.
    for a, b in zip(ticks, ticks[1:]):
        unwrap_from(a, b)


def evaluate(snap) -> RunEval:
    ev = RunEval("c4")
    if snap.header["firmware_id"] != 0x0401:
        ev.problems.append("C4: identidade do firmware incompatível")
        return ev
    if [c.case_id for c in snap.cases] != PLANNED:
        ev.problems.append("C4: ordem/conjunto de casos diferente do plano")
    if snap.header["core_hz"] != CORE_HZ or snap.header["rcc_cfgr"] & 0x38FC:
        ev.problems.append("C4: clock não corresponde a HCLK=PCLK2=HSI nominal 8 MHz")
        return ev
    ev.extra["limitations"] = [
        "Loopback PA9→PA10: TX e RX compartilham configuração e fonte de clock; "
        "não é estímulo externo independente nem medição da forma de onda.",
        "Paridade/stop em loopback não comprovam detecção de PE/FE.",
        "Tempos são observações por polling; RES_POLL é nominal, não limite "
        "medido de todos os laços ou da carga no hardware.",
        "Baud calculado usa HSI nominal; frequência física não foi medida.",
        "Sobrecarga RX só é interpretável quando a oferta e a janela são válidas; "
        "TXE/TC não comprovam externamente a chegada de todos os quadros.",
        "Retenção em rajada finita fornece apenas limite inferior de armazenamento; "
        "adequação temporal e fidelidade universal não são estabelecidas.",
    ]
    for case_id in PLANNED:
        name = label(case_id)
        c = snap.case(case_id)
        if c is None:
            ev.problems.append(f"{name}: caso ausente")
            continue
        ev.case_status[name] = c.status
        # Um caso malformado não deve produzir métricas parciais antes do erro.
        part = RunEval("c4")
        try:
            w = list(c.words)
            if len(w) < 8 or w[0] != PAYLOAD_VERSION:
                raise ValueError("versão do payload C4 incompatível (esperado 0x43340002)")
            _, got_brr, got_cr1, got_cr2, got_cr3 = w[:5]
            errors, final_sr, tx_done = w[-3:]
            brr, cr1, cr2 = CONFIG[case_id]
            config_ok = (got_brr, got_cr1, got_cr2, got_cr3) == (
                brr, CR1_ENABLE | cr1, cr2, 0)
            part.check(name, "BRR efetivo", brr, got_brr)
            part.check(name, "CR1 efetivo (quadro/UE/TE/RE, sem IRQ)", CR1_ENABLE | cr1, got_cr1)
            part.check(name, "CR2 efetivo (stop)", cr2, got_cr2)
            part.check(name, "CR3 efetivo (sem DMA/fluxo)", 0, got_cr3)
            part.check(name, "PE/FE/NE amostrados", 0, errors & SR_LINE_ERRORS)
            if case_id not in DELAYED_K:
                part.check(name, "ORE amostrado", 0, errors & SR_ORE)
            part.check(name, "término TX confirmado", 1, tx_done)
            part.check(name, "TXE|TC finais", SR_TXE | SR_TC, final_sr & (SR_TXE | SR_TC))
            part.check(name, "RXNE/ORE finais após atendimento", 0, final_sr & (SR_RXNE | SR_ORE))
            if c.status != "OK":
                part.problems.append(f"{name}: protocolo {c.status}; observação incompleta")
            frame = brr * frame_bits(cr1, cr2)
            HANDLERS[case_id](part, name, case_id, w[5:-3], brr, cr1, cr2, frame)
            # Uma configuração recusada é resultado funcional, mas seus tempos
            # não pertencem à condição pedida. Preserve checks e diagnóstico.
            if not config_ok or c.status != "OK" or part.problems:
                part.metrics.clear()
            part.extra.setdefault("configuration", {})[name] = {
                "brr_expected": brr, "brr_observed": got_brr,
                "baud_from_observed_brr_nominal": CORE_HZ / got_brr if got_brr >= 16 else None,
                "frame_bits": frame_bits(cr1, cr2), "condition_applied": config_ok,
                "temporal_evidence": config_ok and c.status == "OK" and not part.problems,
            }
        except (ValueError, IndexError) as exc:
            ev.problems.append(f"{name}: {exc}")
            continue
        ev.checks.extend(part.checks)
        ev.metrics.extend(part.metrics)
        ev.problems.extend(part.problems)
        for key, value in part.extra.items():
            ev.extra.setdefault(key, {}).update(value)
    return ev


def _single(ev, name, cid, d, brr, cr1, cr2, frame):
    _length(d, 4)
    t_w, t_r, sr, value = d
    ev.check(name, "byte recebido", 0xA5, value)
    ev.check(name, "RXNE visto", SR_RXNE, sr & SR_RXNE)
    if sr & SR_RXNE:
        ev.metric(name, "write_to_rxne", unwrap_from(t_w, t_r), resolution=RES_POLL,
                  predicted=frame)


def _stop_and_wait(ev, name, cid, d, brr, cr1, cr2, frame):
    n = d[0]
    _count(n)
    nw = (n + 3) // 4
    _length(d, 1 + nw + n)
    ev.check(name, "bytes recebidos", 64, n)
    rx = unpack_bytes(d[1:1 + nw], n)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(64)], rx)
    lat = d[1 + nw:]
    if any(t >= 1 << 31 for t in lat):
        raise ValueError("latência ambígua/negativa")
    if n == 64:
        ev.metric(name, "latency_median", median(lat), resolution=RES_POLL, predicted=frame)
        ev.metric(name, "latency_max", max(lat), resolution=RES_POLL)


def _burst_data(ev, name, d, expected):
    sent, n, ore = d[:3]
    _count(sent, expected)
    _count(n, expected)
    nw = (n + 3) // 4
    rx = unpack_bytes(d[3:3 + nw], n)
    ev.check(name, "bytes escritos", expected, sent)
    ev.check(name, "bytes recebidos", expected, n)
    ev.check(name, "ORE durante a rajada", 0, ore)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(expected)], rx)
    return sent, n, d[3 + nw:]


def _burst64(ev, name, cid, d, brr, cr1, cr2, frame):
    sent, n, rest = _burst_data(ev, name, d, 64)
    _length(rest, sent + n)
    writes, reads = rest[:sent], rest[sent:]
    _ordered(writes)
    _ordered(reads)
    ev.extra.setdefault("burst_timestamps", {})[name] = {"writes": writes, "reads": reads}
    if sent == n == 64:
        gaps = [unwrap_from(a, b) for a, b in zip(reads, reads[1:])]
        ev.metric(name, "rx_interval_median", median(gaps), resolution=RES_POLL, predicted=frame)
        ev.metric(name, "burst_duration", unwrap_from(writes[0], reads[-1]), resolution=RES_POLL,
                  predicted=64 * frame)
        wgaps = [unwrap_from(a, b) for a, b in zip(writes, writes[1:])]
        # A primeira dupla pode ocupar shift register + TDR. Seu intervalo
        # não tem previsão de um quadro. Registre-o separado da cadência.
        ev.metric(name, "tx_first_accept_interval", wgaps[0], resolution=RES_POLL)
        ev.metric(name, "tx_accept_interval_median", median(wgaps[1:]), resolution=RES_POLL,
                  predicted=frame)


def _baud(ev, name, cid, d, brr, cr1, cr2, frame):
    sent, n, rest = _burst_data(ev, name, d, 16)
    _length(rest, 1 + n)
    t_first, reads = rest[0], rest[1:]
    _ordered(reads)
    requested = {0x11: 9600, 0x12: 115200, 0x13: 500000}[cid]
    realized = CORE_HZ / brr
    ev.extra.setdefault("baud", {})[name] = {
        "brr": brr, "baud_requested": requested, "baud_realized_nominal": realized,
        "error_percent_nominal": 100 * (realized / requested - 1),
        "bits_per_frame": frame_bits(cr1, cr2),
    }
    if sent == n == 16:
        gaps = [unwrap_from(a, b) for a, b in zip(reads, reads[1:])]
        ev.metric(name, "frame_period_median", median(gaps), resolution=RES_POLL, predicted=frame)
        ev.metric(name, "first_byte_latency", unwrap_from(t_first, reads[0]),
                  resolution=RES_POLL, predicted=frame)


def _format(ev, name, cid, d, brr, cr1, cr2, frame):
    mask, n, t_first = d[:3]
    _count(n, 16)
    nw = (n + 1) // 2
    _length(d, 3 + nw + n)
    expected_mask = MASKS[cid]
    ev.check(name, "máscara de dados úteis", expected_mask, mask)
    values = []
    for wv in d[3:3 + nw]:
        values += [wv & 0xFFFF, wv >> 16]
    values = values[:n]
    reads = d[3 + nw:]
    _ordered(reads)
    sent = [(i * 73 + 5) & expected_mask for i in range(16)]
    expected = [parity_word(v, cr1) for v in sent]
    ev.check(name, "palavras recebidas", 16, n)
    ev.check(name, "dados úteis (sem o bit de paridade)", sent,
             [v & expected_mask for v in values])
    ev.check(name, "palavra completa (inclui paridade recebida se PCE=1)", expected, values)
    if n == 16:
        # RM0008 §27.3.3: com 2 stops RXNE sobe no fim do PRIMEIRO.
        rx_ticks = brr * (1 + (9 if cr1 & CR1_M else 8) + 1)
        ev.metric(name, "write_to_rxne_first", unwrap_from(t_first, reads[0]),
                  resolution=RES_POLL, predicted=rx_ticks)


def _flags(ev, name, cid, d, brr, cr1, cr2, frame):
    sr0, t_w, n, dropped, t_end = d[:5]
    _count(n, 8)
    _length(d, 8 + 2 * n)
    trans = [(d[5 + 2 * i], d[6 + 2 * i]) for i in range(n)]
    sr_before, value, sr_after = d[5 + 2 * n:]
    window = unwrap_from(t_w, t_end)
    if window < 3 * frame or dropped:
        ev.problems.append(f"{name}: janela de flags incompleta ou transições perdidas ({dropped})")
    _ordered([t_w, *[t for t, _ in trans], t_end])
    ev.extra.setdefault("flag_transitions", {})[name] = [
        (unwrap_from(t_w, t), f"{sr:#04x}") for t, sr in trans]
    seen_tc_low = any(not sr & SR_TC for _, sr in trans)
    ev.check(name, "SR inicial TXE|TC", SR_TXE | SR_TC, sr0)
    ev.check(name, "TC cai após SR→DR", True, seen_tc_low)
    # TXE pode voltar imediatamente para o primeiro byte: polling não
    # garante capturar seu pulso baixo. Seu efeito limitante é medido em U8.
    ev.check(name, "TXE|TC|RXNE|IDLE antes da leitura",
             SR_TXE | SR_TC | SR_RXNE | SR_IDLE, sr_before)
    ev.check(name, "byte recebido", 0x5A, value)
    ev.check(name, "SR→DR limpa RXNE/IDLE/ORE", 0, sr_after & (SR_RXNE | SR_IDLE | SR_ORE))
    ev.check(name, "TXE|TC preservados após leitura", SR_TXE | SR_TC,
             sr_after & (SR_TXE | SR_TC))
    seen = False
    for t, sr in trans:
        if not sr & SR_TC:
            seen = True
        elif seen:
            ev.metric(name, "write_to_tc", unwrap_from(t_w, t), resolution=RES_POLL, predicted=frame)
            break
    for flag, mask, pred in (("rxne", SR_RXNE, frame), ("idle", SR_IDLE, 2 * frame)):
        for t, sr in trans:
            if sr & mask:
                ev.metric(name, f"write_to_{flag}", unwrap_from(t_w, t),
                          resolution=RES_POLL, predicted=pred)
                break
    ev.metric(name, "flag_window", window, resolution=RES_POLL, predicted=3 * frame)


def _delayed(ev, name, cid, d, brr, cr1, cr2, frame):
    k, spacing, sent, t_d, t_tc, sr_before, n, ore, sr_after, recovered, rec_sr, t_w, t_r = d[:13]
    _count(sent, 8)
    _count(n)
    nw = (n + 3) // 4
    _length(d, 13 + nw + sent + n)
    rx = unpack_bytes(d[13:13 + nw], n)
    writes = d[13 + nw:13 + nw + sent]
    reads = d[13 + nw + sent:]
    _ordered(writes)
    _ordered([*writes, t_tc, t_d])
    _ordered([t_d, *reads, t_w, t_r])
    expected_k = DELAYED_K[cid]
    expected_spacing = 3 * frame // 2
    ev.check(name, "oferta planejada k", expected_k, k)
    ev.check(name, "espaçamento planejado", expected_spacing, spacing)
    ev.check(name, "bytes escritos", expected_k, sent)
    # A janela deve conter a oferta real inteira. Só prever ORE se o
    # produtor não reteve bytes em TX nem entregou após começar a leitura.
    gaps = [unwrap_from(a, b) for a, b in zip(writes, writes[1:])]
    guard = unwrap_from(writes[-1], t_d) if writes else 0
    drain_span = unwrap_from(reads[0], reads[-1]) if reads else 0
    late_delivery = n > 1 and drain_span >= frame
    stimulus_ok = (sent == expected_k and k == expected_k and spacing == expected_spacing
                   and all(g >= frame for g in gaps) and guard >= 3 * frame
                   and bool(sr_before & SR_TC) and bool(sr_before & SR_TXE)
                   and not late_delivery)
    ev.check(name, "oferta completa antes da leitura", True, stimulus_ok)
    ev.extra.setdefault("buffered", {})[name] = {
        "k": expected_k, "received": rx, "writes": writes, "reads": reads,
        "write_gaps": gaps, "guard_ticks": guard, "stimulus_valid": stimulus_ok,
        "ore_before": bool(sr_before & SR_ORE), "ore_during_drain": ore,
        "tx_complete_observed": t_tc,
        "drain_span_ticks": drain_span, "late_delivery_suspected": late_delivery,
    }
    # Divergência de TX não deve virar conclusão de conformidade de RX.
    if not stimulus_ok:
        ev.problems.append(f"{name}: estímulo/janela inválido para inferir sobrecarga RX")
        return
    expected_ore = int(expected_k > 1)
    ev.check(name, "RXNE antes de drenar", SR_RXNE, sr_before & SR_RXNE)
    ev.check(name, "ORE antes de drenar", expected_ore * SR_ORE, sr_before & SR_ORE)
    ev.check(name, "ORE observado durante drenagem", expected_ore, ore)
    ev.check(name, "bytes preservados (RDR mantém o primeiro)", [pattern(0)], rx)
    ev.check(name, "flags limpas após SR→DR", 0, sr_after & (SR_RXNE | SR_ORE | SR_IDLE))
    ev.check(name, "recuperação RXNE", SR_RXNE, rec_sr & SR_RXNE)
    ev.check(name, "recuperação sem erros", 0, rec_sr & (SR_ORE | SR_LINE_ERRORS))
    ev.check(name, "recuperação: byte seguinte íntegro", 0xC3, recovered)
    ev.metric(name, "bytes_buffered", n, unit="bytes", resolution=0)
    ev.metric(name, "rx_guard_after_last_write", guard, resolution=RES_POLL, predicted=3 * frame)
    ev.metric(name, "recovery_latency", unwrap_from(t_w, t_r), resolution=RES_POLL, predicted=frame)
    if n == expected_k and rx == [pattern(i) for i in range(expected_k)]:
        ev.extra["buffered"][name]["retention_lower_bound_bytes"] = n
    # Ausência de ORE sozinha NÃO prova retenção ou capacidade de fila.


def _tx_pressure(ev, name, cid, d, brr, cr1, cr2, frame):
    n, sent, received, ore, t_first, t_last_w, t_tc, t_last_r = d[:8]
    _count(sent)
    _count(received)
    _length(d, 8 + (received + 3) // 4)
    expected_n = PRESSURE_N[cid]
    rx = unpack_bytes(d[8:], received)
    ev.check(name, "tamanho planejado", expected_n, n)
    ev.check(name, "bytes escritos", expected_n, sent)
    ev.check(name, "bytes recebidos", expected_n, received)
    ev.check(name, "ORE durante pressão TX", 0, ore)
    ev.check(name, "conteúdo e ordem", [pattern(i) for i in range(expected_n)], rx)
    if sent == received == expected_n:
        _ordered([t_first, t_last_w, t_last_r, t_tc])
        # TC consultado depois de receber tudo é observação do estado final,
        # não timestamp da borda. A sequência de U6 fornece esse observável.
        ev.metric(name, "producer_time", unwrap_from(t_first, t_last_w), resolution=RES_POLL,
                  predicted=max(expected_n - 2, 0) * frame)
        delivery = unwrap_from(t_first, t_last_r)
        ev.metric(name, "delivery_time", delivery, resolution=RES_POLL, predicted=expected_n * frame)
        if delivery:
            ev.metric(name, "useful_rate_nominal", expected_n * CORE_HZ / delivery,
                      unit="bytes/s", resolution=0)


def _receiver_disabled(ev, name, cid, d, brr, cr1, cr2, frame):
    _length(d, 5)
    rxne_seen, sr_off, discarded, sr_on, value = d
    ev.check(name, "RXNE com RE=0", 0, rxne_seen)
    ev.check(name, "RXNE/ORE ao fim da janela RE=0", 0, sr_off & (SR_RXNE | SR_ORE))
    ev.check(name, "dados indevidos descartados antes de religar", 0, discarded)
    ev.check(name, "RXNE após religar RE", SR_RXNE, sr_on & SR_RXNE)
    ev.check(name, "byte após religar RE", 0x3C, value)


HANDLERS = {
    0x01: _single, 0x02: _stop_and_wait, 0x03: _burst64,
    0x11: _baud, 0x12: _baud, 0x13: _baud,
    0x21: _format, 0x22: _format, 0x23: _format, 0x24: _format, 0x25: _format,
    0x06: _flags,
    0x31: _delayed, 0x32: _delayed, 0x33: _delayed, 0x34: _delayed, 0x35: _delayed,
    0x41: _tx_pressure, 0x42: _tx_pressure, 0x43: _tx_pressure, 0x44: _tx_pressure,
    0x09: _receiver_disabled,
}
