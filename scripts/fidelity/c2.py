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

from statistics import median, pstdev

from .abi import unwrap_from
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
         "irq_delayed": "atendimento atrasado", "irq_coalesced": "eventos coalescidos"}


def label(case_id: int) -> str:
    kind, t, p = case_id >> 8, (case_id >> 4) & 0xF, case_id & 0xF
    return f"{TIMERS[t]}/apb{APB_DIV[p]}/{KINDS[kind]}"


def timclk(core_hz: int, apb_div: int) -> float:
    pclk = core_hz / apb_div
    return pclk if apb_div == 1 else 2 * pclk


def evaluate(snap) -> RunEval:
    ev = RunEval("c2")
    core_hz = snap.header["core_hz"]
    isr_events = {w: [e for e in snap.events[w] if e.event == EV_ISR_ENTRY] for w in (1, 2, 3)}
    if not snap.complete_trace:
        ev.problems.append(f"trace incompleto (perdas {snap.lost}): métricas de ISR inválidas")
    for case_id in PLANNED:
        c = snap.case(case_id)
        name = label(case_id)
        if c is None:
            ev.problems.append(f"{name}: caso ausente")
            continue
        ev.case_status[name] = c.status
        w = list(c.words)
        kind, t, profile, cfgr, psc, arr = w[:6]
        if (kind << 8 | t << 4 | profile) != case_id:
            ev.problems.append(f"{name}: cabeçalho {w[:3]} não confere com o id")
            continue
        div = APB_DIV[profile]
        ratio = timclk(core_hz, div) / core_hz              # contagens de TIMCLK por tick
        tick_per_count = (psc + 1) / ratio
        code = PPRE_CODE[div]
        ev.check(name, "RCC_CFGR.PPRE1/PPRE2 lido de volta", f"0x{(code << 8) | (code << 11):04x}",
                 f"0x{cfgr & 0x3F00:04x}")
        data = w[6:]
        # Uma volta do laço de polling inclui uma leitura no APB: com o
        # barramento dividido por N ela fica até ~N vezes mais lenta.
        res = RES_POLL * div
        HANDLERS[KINDS[kind]](ev, name, data, psc, arr, ratio, tick_per_count,
                              [e for e in isr_events[TIMER_WRITER[t]] if e.case_id == case_id], res)
    return ev


def _count_off(ev, name, d, psc, arr, ratio, tpc, isr, res):
    c0, c1, sr = d
    ev.check(name, "CNT parado (1ª leitura)", 0, c0)
    ev.check(name, "CNT parado (após 8000 ticks)", 0, c1)
    ev.check(name, "SR sem flags", 0, sr)


def _count_rate(ev, name, d, psc, arr, ratio, tpc, isr, res):
    t0, c0, t1, c1, sr = d
    window = unwrap_from(t0, t1)
    counts = c1 - c0
    predicted = window * ratio / (psc + 1)
    # Funcional: a regra do clock (razão TIMCLK/HCLK) — tolera 2 contagens
    # de leitura; é razão entre clocks da MESMA origem (HSI), não exatidão
    # absoluta de frequência.
    ev.check(name, "razão TIMCLK/HCLK (±2 contagens)", True, abs(counts - predicted) <= 2)
    ev.metric(name, "counts_per_tick", counts / window, unit="contagens/tick",
              resolution=2 / window, predicted=ratio / (psc + 1))


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


def _psc_preload(ev, name, d, psc, arr, ratio, tpc, isr, res):
    r = _two_updates(ev, name, d)
    if r is None:
        return
    cnt_w, d1, d2 = r
    old_rest = (arr + 1 - cnt_w) * (psc + 1) / ratio        # resto do período com PSC antigo
    new_rest = (arr + 1 - cnt_w) * 16 / ratio               # se o PSC novo valesse já
    new_period = (arr + 1) * 16 / ratio
    ev.check(name, "resto do período usa PSC antigo (bufferizado)", "antigo",
             "antigo" if abs(d1 - old_rest) < abs(d1 - new_rest) else "novo")
    ev.check(name, "período seguinte usa PSC novo", True, abs(d2 - new_period) <= 4 * res)
    ev.metric(name, "write_to_update", d1, resolution=res, predicted=old_rest)
    ev.metric(name, "next_period", d2, resolution=res, predicted=new_period)


def _arr(ev, name, d, psc, arr, ratio, preload, res):
    r = _two_updates(ev, name, d)
    if r is None:
        return
    cnt_w, d1, d2 = r
    tick = (psc + 1) / ratio
    immediate = (700 - cnt_w) * tick                        # ARR novo (699) já vale
    deferred = (arr + 1 - cnt_w) * tick                     # ARR antigo até o update
    expected = "no próximo update" if preload else "imediato"
    observed = "imediato" if abs(d1 - immediate) < abs(d1 - deferred) else "no próximo update"
    ev.check(name, "efeito da escrita em ARR", expected, observed)
    ev.check(name, "período seguinte = ARR novo", True, abs(d2 - 700 * tick) <= 4 * res)
    ev.metric(name, "write_to_update", d1, resolution=res,
              predicted=deferred if preload else immediate)
    ev.metric(name, "next_period", d2, resolution=res, predicted=700 * tick)


def _arr_preload_off(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _arr(ev, name, d, psc, arr, ratio, False, res)


def _arr_preload_on(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _arr(ev, name, d, psc, arr, ratio, True, res)


def _ug(ev, name, d, urs):
    cnt_before, cnt_after, cnt_later, sr = d
    ev.check(name, "CNT andando antes do UG (>= 500)", True, cnt_before >= 500)
    # 24 ticks depois do UG, com PSC = 7, o contador reiniciado vale <= 4.
    ev.check(name, "UG reinicia CNT (CNT <= 4 após 24 ticks)", True, cnt_later <= 4)
    # Quando o reinício fica visível para a leitura SEGUINTE não é especificado
    # pelo RM0008: observação sem oráculo (expected = None).
    ev.check(name, "leitura imediata após UG já vê o CNT reiniciado", None,
             "sim" if cnt_after <= 1 else "não")
    ev.check(name, f"UIF após UG com URS={urs}", 0 if urs else 1, sr & 1)


def _ug_urs0(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _ug(ev, name, d, 0)


def _ug_urs1(ev, name, d, psc, arr, ratio, tpc, isr, res):
    _ug(ev, name, d, 1)


def _uif_pending(ev, name, d, psc, arr, ratio, tpc, isr, res):
    labels = ["UIF após update", "pending com UIE=0", "pending com UIE=1",
              "UIF após limpeza", "pending após UIF limpo (latch)", "pending após ICPR"]
    for item, exp, obs in zip(labels, [1, 0, 1, 0, 1, 0], d):
        ev.check(name, item, exp, obs)


def _irq_periodic(ev, name, d, psc, arr, ratio, tpc, isr, res):
    t_start, entries = d
    ev.check(name, "entradas da ISR", N_IRQS, entries)
    ev.check(name, "eventos de ISR no trace", N_IRQS, len(isr))
    if len(isr) < 2:
        return
    period = (psc + 1) * (arr + 1) / ratio
    lat = [e.arg * tpc for e in isr]                     # CNT na ISR → ticks desde o update
    periods = [unwrap_from(a.ticks, b.ticks) for a, b in zip(isr, isr[1:])]
    ev.metric(name, "latency_cnt_median", median(lat), resolution=tpc)
    ev.metric(name, "latency_cnt_max", max(lat), resolution=tpc)
    ev.metric(name, "latency_cnt_min", min(lat), resolution=tpc)
    ev.metric(name, "isr_period_median", median(periods), resolution=RES_LOG, predicted=period)
    ev.metric(name, "isr_period_jitter_std", pstdev(periods), resolution=RES_LOG)
    ev.metric(name, "first_isr_after_start", unwrap_from(t_start, isr[0].ticks),
              resolution=RES_LOG, predicted=period)




def _irq_delay(ev, name, d, psc, arr, ratio, tpc, isr, res):
    delay, t_seen, cnt_seen, t_enable, entries = d
    ev.check(name, "UIF observado antes de habilitar", True, t_seen != 0)
    ev.check(name, "ISR atendida uma única vez", 1, entries)
    if not isr:
        return
    period = (psc + 1) * (arr + 1) / ratio
    e = isr[0]
    ev.metric(name, "enable_to_isr", unwrap_from(t_enable, e.ticks), resolution=RES_LOG)
    # Posição no período quando a ISR leu CNT: prevista a partir do instante
    # em que MAIN viu UIF (cnt_seen) + o atraso. CNT dá só a posição dentro
    # do período, não quantos períodos passaram (isso é inferido).
    ev.metric(name, "isr_cnt_ticks", e.arg * tpc, resolution=tpc,
              predicted=(cnt_seen * tpc + delay) % period)
    ev.extra.setdefault("inferred_updates", {})[name] = int((cnt_seen * tpc + delay) // period) + 1


HANDLERS = {
    "count_off": _count_off, "count_rate": _count_rate, "update_poll": _update_poll,
    "psc_preload": _psc_preload, "arr_preload_off": _arr_preload_off,
    "arr_preload_on": _arr_preload_on, "ug_urs0": _ug_urs0, "ug_urs1": _ug_urs1,
    "uif_pending": _uif_pending, "irq_idle": _irq_periodic, "irq_load": _irq_periodic,
    "irq_delayed": _irq_delay, "irq_coalesced": _irq_delay,
}
