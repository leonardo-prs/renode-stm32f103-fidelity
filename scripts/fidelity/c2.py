"""C2 — oráculos e métricas (timers TIM2/TIM3/TIM1 e IRQ de update).

Expectativas derivadas do RM0008 (Rev. 21):
  - §7.2 (árvore de clock): TIMxCLK = PCLKx se prescaler APBx = 1, senão
    2 × PCLKx. Com HCLK 8 MHz: /1 → 8 MHz, /2 → 8 MHz, /4 → 4 MHz.
  - §7.3.2 (RCC_CFGR): PPRE1 bits 10:8, PPRE2 bits 13:11; /1 = 0xx,
    /2 = 100, /4 = 101.
  - §15.3.1/§15.3.2: PSC sempre bufferizado (vale a partir do próximo
    update); ARR bufferizado só com ARPE = 1. Período =
    (PSC + 1)(ARR + 1) / TIMCLK.
  - §15.4.1 (URS) e §15.4.5 (UG): UG reinicia CNT e o contador do
    prescaler; com URS = 0 o UG gera evento de update e seta UIF
    (independe de UIE); com URS = 1, não.
  - PM0056 §4.3 (NVIC): pending registrado enquanto a linha está ativa e
    mantido até a entrada no handler ou escrita em ICPR.
A conversão de ticks usa core_hz do header (HCLK nominal) e o perfil
gravado em cada caso, nunca uma constante escondida.
"""
from __future__ import annotations

from math import ceil, floor
from statistics import median, pstdev

from .abi import SnapshotError, timeline, unwrap_from
from .model import RES_LOG, RES_POLL, RunEval

KINDS = {1: "count_off", 2: "count_rate", 3: "update_poll", 4: "psc_preload",
         5: "arr_preload_off", 6: "arr_preload_on", 7: "ug_urs0", 8: "ug_urs1",
         9: "uif_pending", 10: "irq_idle", 11: "irq_load", 12: "irq_delayed",
         13: "irq_coalesced"}
TIMERS = ["tim2", "tim3", "tim1"]
TIMER_WRITER = {0: 1, 1: 2, 2: 3}
APB_DIV = [1, 2, 4]
PPRE_CODE = {1: 0b000, 2: 0b100, 4: 0b101}
EV_ISR_ENTRY = 0x200
N_PERIODS, N_IRQS = 8, 16

PLANNED = (
    [(1 << 8) | (t << 4) for t in range(3)]
    + [(2 << 8) | (t << 4) | p for t in range(3) for p in range(3)]
    + [(3 << 8) | (t << 4) for t in range(3)] + [(3 << 8) | (0 << 4) | 2, (3 << 8) | (2 << 4) | 2]
    + [(k << 8) | (t << 4) for t in range(3) for k in (4, 5, 6, 7, 8, 9)]
    + [(10 << 8) | (t << 4) for t in range(3)] + [(10 << 8) | 1, (10 << 8) | 2]
    + [(k << 8) | (t << 4) for t in range(3) for k in (11, 12, 13)]
)

# Recurso de cada tipo de caso (tabela de limites).
GROUP = {"count_off": "contagem habilitada/parada",
         "count_rate": "árvore de clock (APB → TIMCLK)",
         "update_poll": "período de update (polling)",
         "psc_preload": "PSC bufferizado", "arr_preload_off": "ARR sem preload",
         "arr_preload_on": "ARR com preload", "ug_urs0": "UG/URS", "ug_urs1": "UG/URS",
         "uif_pending": "UIF × UIE × pending NVIC",
         "irq_idle": "IRQ periódica (MAIN ocioso)", "irq_load": "IRQ periódica (MAIN com carga)",
         "irq_delayed": "atendimento atrasado", "irq_coalesced": "eventos coalescidos",
         "rcc": "RCC (registradores de clock lidos de volta)"}
RCC_CASE = "c2/rcc"
WRITE_AT = 500          # CNT a partir do qual o firmware escreve o novo PSC/ARR


def label(case_id: int) -> str:
    kind, t, p = case_id >> 8, (case_id >> 4) & 0xF, case_id & 0xF
    return f"{TIMERS[t]}/apb{APB_DIV[p]}/{KINDS[kind]}"


def timclk(core_hz: int, apb_div: int) -> float:
    pclk = core_hz / apb_div
    return pclk if apb_div == 1 else 2 * pclk


# Quantidade exata de palavras de dados; inclui os brackets medidos de
# CNT e UG. Mais 6 palavras comuns e 4 leituras de estado no fim do caso.
DATA_WORDS = {1: 3, 2: 7, 3: 9, 4: 4, 5: 4, 6: 4, 7: 6, 8: 6,
              9: 6, 10: 2, 11: 2, 12: 6, 13: 6}


def evaluate(snap) -> RunEval:
    ev = RunEval("c2")
    ev.extra["observer"] = {
        "log_ticks_min": snap.header["log_ticks"],
        "observer_ticks_min": snap.header["observer_ticks"],
        "limits": ["RES_POLL é estimativa, não limite calibrado do laço",
                   "CNT periódico fornece fase módulo período; latência exige ausência de perdas",
                   "CNT atrasado é congelado antes da liberação da IRQ",
                   "timestamp do logger inclui prólogo e custo de registro",
                   "preload: previsões temporais, sem tolerância funcional universal"],
    }
    if snap.state != "DONE" or snap.header["error"]:
        ev.problems.append(f"snapshot {snap.state}, erro {snap.header['error']}: instrumento inválido")
        return ev
    if [c.case_id for c in snap.cases] != PLANNED:
        ev.problems.append("conjunto/ordem de casos diferente do plano C2")
    core_hz = snap.header["core_hz"]
    if core_hz != 8_000_000 or (snap.header["rcc_cr"] & 3) != 3:
        ev.problems.append("clock nominal HSI8/HSIRDY inválido")
        return ev
    trace_ok = True
    try:
        timeline(snap)
    except SnapshotError as exc:
        ev.problems.append(f"trace inválido ({exc}): métricas de ISR inválidas")
        trace_ok = False
    allowed = set(PLANNED)
    for e in snap.all_events():
        if e.event >= 0x100 and (e.event != EV_ISR_ENTRY or e.case_id not in allowed
                               or e.writer != TIMER_WRITER[(e.case_id >> 4) & 0xF]):
            ev.problems.append(f"evento C2 inesperado: ticket {e.ticket}")
            trace_ok = False
    rcc_items: dict[str, tuple[int, set]] = {}      # item → (esperado, valores lidos)
    for case_id in PLANNED:
        c = snap.case(case_id)
        name = label(case_id)
        if c is None:
            ev.problems.append(f"{name}: caso ausente")
            continue
        ev.case_status[name] = c.status
        kind, t, profile = case_id >> 8, (case_id >> 4) & 0xF, case_id & 0xF
        w = list(c.words)
        if len(w) != 10 + DATA_WORDS[kind]:
            ev.problems.append(f"{name}: payload tem {len(w)} palavras, esperado {10 + DATA_WORDS[kind]}")
            continue
        if w[:3] != [kind, t, profile]:
            ev.problems.append(f"{name}: cabeçalho {w[:3]} não confere com o id")
            continue
        if c.status != "OK":
            ev.problems.append(f"{name}: status {c.status}; medições excluídas")
            continue
        cfgr, psc, arr = w[3:6]
        expected_psc = 7 if 3 <= kind <= 9 else 0
        expected_arr = 65535 if kind <= 2 else (999 if kind <= 9 else 7999)
        ev.check(name, "PSC lido de volta", expected_psc, psc)
        ev.check(name, "ARR lido de volta", expected_arr, arr)
        div = APB_DIV[profile]
        code = PPRE_CODE[div]
        cr1, dier, ccer, enr = w[-4:]
        # Registradores do RCC vão para UM caso de contexto ("c2/rcc"), uma
        # vez por perfil e por timer: o Renode 1.17 não modela o RCC do F1
        # (lê 0), e repetir isso em cada caso marcaria todo recurso de timer
        # como divergente por uma única lacuna. Os efeitos dessa lacuna no
        # timer aparecem nos próprios casos (ex.: razão TIMCLK/HCLK em /4).
        rcc_items.setdefault(f"RCC_CFGR com APB /{div} (SW/HPRE/PPRE1/PPRE2)",
                             ((code << 8) | (code << 11), set()))[1].add(cfgr & 0x3FFF)
        bit = 11 if t == 2 else t
        rcc_items.setdefault(f"clock enable do {TIMERS[t].upper()} (RCC_APB{2 if t == 2 else 1}ENR)",
                             (1, set()))[1].add((enr >> bit) & 1)
        expected_cr1 = 0 if kind in (1, 9, 10, 11, 12, 13) else (0x81 if kind == 6 else (5 if kind == 8 else 1))
        ev.check(name, "CR1 efetivo antes da limpeza", expected_cr1, cr1)
        ev.check(name, "DIER efetivo antes da limpeza", 1 if kind == 9 else 0, dier)
        ev.check(name, "saídas de canal desabilitadas", 0, ccer)
        # As previsões usam entradas fixadas pelo plano; valores observados
        # errados não podem mudar o próprio oráculo.
        ratio = timclk(core_hz, div) / core_hz
        tick_per_count = (expected_psc + 1) / ratio
        isr = [e for e in snap.events[TIMER_WRITER[t]]
               if e.event == EV_ISR_ENTRY and e.case_id == case_id] if trace_ok else []
        if kind < 10 and isr:
            ev.check(name, "nenhuma ISR com NVIC/UIE bloqueados", 0, len(isr))
        if kind >= 10 and not trace_ok:
            continue
        HANDLERS[KINDS[kind]](ev, name, w[6:-4], expected_psc, expected_arr,
                              ratio, tick_per_count, isr, RES_POLL * div)
    for item, (expected, seen) in rcc_items.items():
        observed = " | ".join(f"0x{v:04x}" for v in sorted(seen))   # >1 valor = leitura variável
        ev.check(RCC_CASE, item, f"0x{expected:04x}", observed)
    if rcc_items:
        ev.case_status[RCC_CASE] = "OK"
    return ev


def _count_off(ev, name, d, psc, arr, ratio, tpc, isr, res):
    c0, c1, sr = d
    ev.check(name, "CNT parado (1ª leitura)", 0, c0)
    ev.check(name, "CNT parado (após 8000 ticks)", 0, c1)
    ev.check(name, "SR sem flags", 0, sr)


def _count_rate(ev, name, d, psc, arr, ratio, tpc, isr, res):
    t0, c0, t0_after, t1, c1, t1_after, sr = d
    window = unwrap_from(t0, t1)
    lo = unwrap_from(t0_after, t1)
    hi = unwrap_from(t0, t1_after)
    if not (0 < lo <= window <= hi < 400000):
        ev.problems.append(f"{name}: bracket CNT inválido")
        return
    counts = (c1 - c0) & 0xFFFF
    # Instante de cada leitura pertence ao seu bracket CYCCNT. Um count
    # de incerteza cobre a fase fracionária, sem supor custo fixo do APB.
    lower, upper = floor(lo / tpc), ceil(hi / tpc)
    ev.check(name, "ΔCNT na faixa prevista pelo bracket", True,
             lower <= counts <= upper)
    ev.check(name, "UIF ausente (janela sem overflow previsto)", 0, sr & 1)
    ev.extra.setdefault("count_bounds", {})[name] = [lower, counts, upper]
    ev.metric(name, "counts_per_tick", counts / window, unit="contagens/tick",
              resolution=(upper - lower + 1) / window, predicted=1 / tpc)


def _update_poll(ev, name, d, psc, arr, ratio, tpc, isr, res):
    t_cen, *ups = d
    if 0 in ups:
        ev.check(name, "8 updates observados", N_PERIODS, ups.index(0))
        return
    ev.check(name, "8 updates observados", N_PERIODS, len(ups))
    period = (psc + 1) * (arr + 1) / ratio
    periods = [unwrap_from(a, b) for a, b in zip(ups, ups[1:])]
    ev.metric(name, "first_update", unwrap_from(t_cen, ups[0]), resolution=res,
              predicted=period)
    ev.metric(name, "period_median", median(periods), resolution=res, predicted=period)
    ev.metric(name, "period_jitter_std", pstdev(periods), resolution=res)


def _two_updates(ev, name, d):
    cnt_w, t_w, u1, u2 = d
    if 0 in (u1, u2):
        ev.check(name, "2 updates após a escrita", True, False)
        return None
    return cnt_w, unwrap_from(t_w, u1), unwrap_from(u1, u2)


def _nearest(d1: float, hypotheses: dict[str, float]) -> str:
    """Hipótese temporal mais próxima de d1, ou "ambíguo" se d1 não estiver
    claramente mais perto de uma delas (menos de 1/4 da distância entre as
    previsões). As previsões diferem em milhares de ticks e o polling tem
    resolução de dezenas: a decisão só fica ambígua se algo inesperado ocorrer."""
    (a, ta), (b, tb) = hypotheses.items()
    if abs(abs(d1 - ta) - abs(d1 - tb)) < abs(ta - tb) / 4:
        return "ambíguo"
    return a if abs(d1 - ta) < abs(d1 - tb) else b


def _psc_preload(ev, name, d, psc, arr, ratio, tpc, isr, res):
    r = _two_updates(ev, name, d)
    if r is None:
        return
    cnt_w, d1, d2 = r
    old_rest = (arr + 1 - cnt_w) * (psc + 1) / ratio        # resto do período com PSC antigo
    new_rest = (arr + 1 - cnt_w) * 16 / ratio               # se o PSC novo valesse já
    new_period = (arr + 1) * 16 / ratio
    # RM0008 §15.3.1: PSC é bufferizado; o novo valor só vale após o update.
    ev.check(name, "resto do período usa o PSC antigo (bufferizado)", "antigo",
             _nearest(d1, {"antigo": old_rest, "novo": new_rest}))
    # Previsão da métrica no ponto PLANEJADO da escrita (CNT = 500), igual nos
    # dois ambientes; o CNT observado só entra na decisão acima.
    ev.metric(name, "write_to_update", d1, resolution=res,
              predicted=(arr + 1 - WRITE_AT) * (psc + 1) / ratio)
    ev.metric(name, "next_period", d2, resolution=res, predicted=new_period)


def _arr(ev, name, d, psc, arr, ratio, preload, res):
    r = _two_updates(ev, name, d)
    if r is None:
        return
    cnt_w, d1, d2 = r
    tick = (psc + 1) / ratio
    immediate = (700 - cnt_w) * tick                        # ARR novo (699) já vale
    deferred = (arr + 1 - cnt_w) * tick                     # ARR antigo até o update
    # RM0008 §15.3.1: com ARPE = 1 o ARR é bufferizado; com ARPE = 0 vale na hora.
    ev.check(name, "momento em que o novo ARR passa a valer",
             "no próximo update" if preload else "imediato",
             _nearest(d1, {"imediato": immediate, "no próximo update": deferred}))
    planned = (arr + 1 - WRITE_AT) * tick if preload else (700 - WRITE_AT) * tick
    ev.metric(name, "write_to_update", d1, resolution=res, predicted=planned)
    ev.metric(name, "next_period", d2, resolution=res, predicted=700 * tick)


def _arr_preload_off(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _arr(ev, name, d, psc, arr, ratio, False, res)


def _arr_preload_on(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _arr(ev, name, d, psc, arr, ratio, True, res)


def _ug(ev, name, d, urs, tpc):
    cnt_before, cnt_after, cnt_later, sr, t_ug, t_later = d
    elapsed = unwrap_from(t_ug, t_later)
    if not (24 <= elapsed < 4000):
        ev.problems.append(f"{name}: bracket UG inválido ({elapsed} ticks)")
        return
    upper = ceil(elapsed / tpc)
    ev.check(name, "CNT andando antes do UG (500..998)", True, 500 <= cnt_before < 999)
    if upper >= 1000 - cnt_before:
        ev.problems.append(f"{name}: janela não distingue UG de overflow natural")
        return
    # RM0008 não fixa a latência de visibilidade na primeira leitura de CNT.
    # Verificar a leitura posterior, cujo tempo foi medido, sem impor que a
    # leitura imediata já esteja atualizada. O raw mantém ambas as leituras.
    ev.check(name, "UG reinicia CNT após janela medida", True, cnt_later <= upper)
    ev.check(name, f"UIF após UG com URS={urs}", 0 if urs else 1, sr & 1)
    ev.extra.setdefault("ug_bounds", {})[name] = {"elapsed": elapsed, "upper_cnt": upper,
                                                           "cnt_immediate": cnt_after,
                                                           "cnt_later": cnt_later}


def _ug_urs0(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _ug(ev, name, d, 0, tpc)


def _ug_urs1(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _ug(ev, name, d, 1, tpc)


def _uif_pending(ev, name, d, psc, arr, ratio, tpc, isr, res):
    labels = ["UIF após update", "pending com UIE=0", "pending com UIE=1",
              "UIF após limpeza", "pending após UIF limpo (latch)", "pending após ICPR"]
    for item, exp, obs in zip(labels, [1, 0, 1, 0, 1, 0], d):
        ev.check(name, item, exp, obs)


def _irq_periodic(ev, name, d, psc, arr, ratio, tpc, isr, res):
    t_start, entries = d
    ev.check(name, "entradas da ISR", N_IRQS, entries)
    ev.check(name, "eventos de ISR no trace", N_IRQS, len(isr))
    ev.check(name, "CNT da ISR dentro do período", True, all(e.arg <= arr for e in isr))
    if entries != N_IRQS or len(isr) != N_IRQS or any(e.arg > arr for e in isr):
        return
    period = (psc + 1) * (arr + 1) / ratio
    phase = [e.arg * tpc for e in isr]     # fase módulo período, não latência sem prova de ausência de perdas
    periods = [unwrap_from(a.ticks, b.ticks) for a, b in zip(isr, isr[1:])]
    ev.metric(name, "phase_cnt_median", median(phase), resolution=tpc)
    ev.metric(name, "phase_cnt_max", max(phase), resolution=tpc)
    ev.metric(name, "phase_cnt_min", min(phase), resolution=tpc)
    ev.metric(name, "isr_period_median", median(periods), resolution=RES_LOG, predicted=period)
    ev.metric(name, "isr_period_jitter_std", pstdev(periods), resolution=RES_LOG)
    ev.metric(name, "first_isr_after_start", unwrap_from(t_start, isr[0].ticks),
              resolution=RES_LOG, predicted=period)




def _irq_delay(ev, name, d, psc, arr, ratio, tpc, isr, res):
    delay, t_seen, cnt_seen, cnt_stopped, t_enable, entries = d
    ev.check(name, "UIF observado antes de habilitar", True, t_seen != 0)
    ev.check(name, "atraso solicitado", 20000 if name.endswith("irq_coalesced") else 2000, delay)
    ev.check(name, "ISR atendida uma única vez", 1, entries)
    ev.check(name, "um evento de ISR no trace", 1, len(isr))
    ev.check(name, "CNT observado dentro do período", True,
             cnt_seen <= arr and cnt_stopped <= arr and all(e.arg <= arr for e in isr))
    ev.check(name, "ISR preserva CNT congelado", True, [e.arg for e in isr] == [cnt_stopped])
    if entries != 1 or len(isr) != 1 or t_seen == 0 or cnt_seen > arr or cnt_stopped > arr or isr[0].arg != cnt_stopped:
        return
    period = (psc + 1) * (arr + 1) / ratio
    e = isr[0]
    ev.metric(name, "release_marker_to_isr", unwrap_from(t_enable, e.ticks), resolution=RES_LOG)
    # CNT congelado foi lido por MAIN e pela ISR; compara-se o valor real,
    # sem simular a parada num timestamp anterior à escrita em CR1.
    elapsed = unwrap_from(t_seen, t_enable)
    ev.check(name, "atraso mínimo até liberação", True, elapsed >= delay)
    ev.metric(name, "frozen_cnt_ticks", e.arg * tpc, resolution=tpc)
    # Fonte parada antes da liberação: CNT não é a latência da ISR.
    ev.extra.setdefault("inferred_updates", {})[name] = int((cnt_seen * tpc + elapsed) // period) + 1


HANDLERS = {
    "count_off": _count_off, "count_rate": _count_rate, "update_poll": _update_poll,
    "psc_preload": _psc_preload, "arr_preload_off": _arr_preload_off,
    "arr_preload_on": _arr_preload_on, "ug_urs0": _ug_urs0, "ug_urs1": _ug_urs1,
    "uif_pending": _uif_pending, "irq_idle": _irq_periodic, "irq_load": _irq_periodic,
    "irq_delayed": _irq_delay, "irq_coalesced": _irq_delay,
}
