"""Análise de uma campanha: HW × cada configuração do Renode, por firmware.

Entrada: data/fidelity/<campanha>/<fw>/<tag>/run-NNN/{manifest.json,snapshot.bin}
Saída:   data/fidelity/<campanha>/analysis/<fw>.{json,md,perfetto.json} + index.md

Princípios: (1) funcional antes de temporal; (2) referência externa sempre que
existe (oráculo do host, TRM, RM0008, PM0056) — a bancada não é "verdade"
automática (a placa pode divergir do manual, ver S3A); (3) nenhuma margem de
aceitação arbitrária: as divergências são reportadas com valor e unidade;
(4) determinismo entre runs verificado, não presumido.
"""
from __future__ import annotations

import json
import statistics as st
from dataclasses import dataclass
from pathlib import Path

from . import abi, firmware, oracles, perfetto
from .firmware import ROOT


@dataclass
class Run:
    path: Path
    manifest: dict
    snap: abi.Snapshot


# ───────────────────────────── carga ─────────────────────────────

def load(campaign: str, fw_name: str) -> dict[str, list[Run]]:
    base = ROOT / "data" / "fidelity" / campaign / fw_name
    out: dict[str, list[Run]] = {}
    if not base.is_dir():
        return out
    for tag_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        runs = []
        for run_dir in sorted(tag_dir.glob("run-*")):
            try:
                manifest = json.loads((run_dir / "manifest.json").read_text())
                if manifest.get("status") != "complete":
                    continue
                snap = abi.decode((run_dir / "snapshot.bin").read_bytes())
            except (OSError, ValueError, abi.SnapshotError):
                continue
            runs.append(Run(run_dir, manifest, snap))
        if runs:
            out[tag_dir.name] = runs
    return out


def order_tags(tags) -> list[str]:
    """hw primeiro; depois Renode nominal (m8-q1us), demais em ordem."""
    def key(t: str):
        return (t != "hw", not t.startswith("rn-m8-q1us"), t)
    return sorted(tags, key=key)


def determinism(runs: list[Run]) -> dict:
    sets = {tuple(r.snap.rows) for r in runs}
    return {"runs": len(runs), "distinct_row_sets": len(sets), "identical": len(sets) == 1}


def med(values):
    values = [v for v in values if v is not None]
    return st.median(values) if values else None


def span(values):
    values = [v for v in values if v is not None]
    return (min(values), max(values)) if values else (None, None)


def pooled(runs: list[Run], condition: int | None = None):
    for r in runs:
        for row in r.snap.rows:
            if condition is None or row[1] == condition:
                yield row


def fmt(v, nd=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:.3g}"
    return str(v)


# ───────────────────────────── S1A ─────────────────────────────

def _s1a_slopes(runs: list[Run]):
    """{kernel: {'slopes': [...], 'intercepts': [...], 'cold_excess': [...]}}"""
    out = {}
    for k in firmware.S1A_KERNELS:
        slopes, inters, cold = [], [], []
        for r in runs:
            rows = [x for x in r.snap.rows if x[1] == k]
            per_trial = {}
            for x in rows:
                per_trial.setdefault(x[0], {})[x[2]] = x[3]
            for trial, pts in per_trial.items():
                if trial == 0 or len(pts) != 2:
                    continue
                (n1, t1), (n2, t2) = sorted(pts.items())
                slope = (t2 - t1) / (n2 - n1)
                slopes.append(slope)
                inters.append(t1 - n1 * slope)
            warm = {n: t for x in rows if x[0] == 1 for n, t in [(x[2], x[3])]}
            cold_rows = [x for x in rows if x[0] == 0]
            if cold_rows and len(warm) == 2:
                n_lo = cold_rows[0][2]
                cold.append(cold_rows[0][3] - warm[n_lo])
        out[k] = {"slopes": slopes, "intercepts": inters, "cold_excess": cold}
    return out


def analyze_s1a(data: dict[str, list[Run]]) -> dict:
    tags = order_tags(data)
    fw = firmware.get("s1a")
    res = {"functional": [], "tables": [], "notes": [], "derived": {}}
    # Funcional: assinatura × oráculo, e HW × Renode linha a linha.
    for tag in tags:
        total = bad = 0
        for r in data[tag]:
            ctx_rows = [x for x in r.snap.rows if x[1] == 0]
            ctx = list(ctx_rows[0][2:8]) + [ctx_rows[1][2], ctx_rows[1][3]]
            for x in r.snap.rows:
                if x[1] == 0:
                    continue
                total += 1
                bad += oracles.s1a_signature(x[1], x[2], ctx, ctx_rows[1][4]) != x[4]
        res["functional"].append({"check": "assinatura dos kernels = oráculo do host",
                                  "env": tag, "pass": total - bad, "total": total})
    slopes = {tag: _s1a_slopes(data[tag]) for tag in tags}
    rows = []
    for k, name in firmware.S1A_KERNELS.items():
        trm, note = oracles.S1A_TRM_CYCLES[k]
        row = {"kernel": name, "instr/iter": oracles.S1A_INSTR_PER_ITER[k], "TRM ciclos/iter": trm}
        for tag in tags:
            s = slopes[tag][k]["slopes"]
            row[f"{tag} /iter"] = med(s)
            row[f"{tag} faixa"] = "{}..{}".format(*map(fmt, span(s)))
        if "hw" in slopes and med(slopes["hw"][k]["slopes"]) is not None:
            row["CPI HW"] = med(slopes["hw"][k]["slopes"]) / oracles.S1A_INSTR_PER_ITER[k]
        row["nota TRM"] = note
        rows.append(row)
    res["tables"].append({"title": "Custo por iteração (inclinação, trials quentes 1..4 × runs)",
                          "unit": "HW: ciclos HCLK; Renode: ticks do DWT virtual (8 MHz)",
                          "rows": rows})
    cold_rows = []
    for k, name in firmware.S1A_KERNELS.items():
        row = {"kernel": name}
        for tag in tags:
            c = slopes[tag][k]["cold_excess"]
            row[f"{tag} excesso 1ª exec."] = "{}..{}".format(*map(fmt, span(c)))
        cold_rows.append(row)
    res["tables"].append({"title": "Primeira execução após reset (COLD − WARM, mesma N)",
                          "unit": "ciclos/ticks", "rows": cold_rows})
    if "hw" in slopes:
        mix = med(slopes["hw"][12]["slopes"])
        if mix:
            cpi = mix / 18
            res["derived"]["calibration"] = {
                "kernel": "mix (s1k_mix, congelado)", "hw_cycles_per_iter": mix,
                "instr_per_iter": 18, "cpi": cpi, "mips_exact": 8 / cpi,
                "mips_integer": round(8 / cpi),
                "rule": "MIPS_cal = 8 MHz / CPI_mix; Renode só aceita inteiro"}
    res["notes"].append("Renode 1.17: tempo = instruções ÷ PerformanceInMips (BaseCPU); "
                        "com 8 MIPS e DWT a 8 MHz, 1 instrução = 1 tick em qualquer classe.")
    return res


# ───────────────────────────── S1B ─────────────────────────────

def analyze_s1b(data):
    tags = order_tags(data)
    fw = firmware.get("s1b")
    expected = oracles.s1b_signatures()
    res = {"functional": [], "tables": [], "notes": [], "derived": {}}
    for tag in tags:
        rows = list(pooled(data[tag]))
        ok = sum(expected[(x[0], x[1])] == x[3] for x in rows)
        res["functional"].append({"check": "assinatura das cargas = oráculo do host",
                                  "env": tag, "pass": ok, "total": len(rows)})
    table = []
    for cond, name in fw.conditions.items():
        row = {"carga": name}
        per = {}
        for tag in tags:
            by_trial = {}
            for x in pooled(data[tag], cond):
                if x[0] >= 1:
                    by_trial.setdefault(x[0], []).append(x[2])
            per[tag] = {t: med(v) for t, v in by_trial.items()}
            row[f"{tag} mediana"] = med(per[tag].values())
        if "hw" in per:
            for tag in tags:
                if tag == "hw":
                    continue
                errs = [(per[tag][t] - per["hw"][t]) / per["hw"][t] * 100
                        for t in per["hw"] if t in per[tag] and per["hw"][t]]
                row[f"erro {tag} %"] = med(errs)
            rn8 = next((t for t in tags if t.startswith("rn-m8-q1us")), None)
            if rn8:
                ratios = [per["hw"][t] / per[rn8][t] for t in per["hw"]
                          if per[rn8].get(t)]
                row["CPI efetivo (HW/RN8)"] = med(ratios)
        table.append(row)
    res["tables"].append({"title": "Tempo por carga (trials quentes 1..8; mesmo dado de entrada por trial)",
                          "unit": "HW: ciclos; Renode: ticks DWT; erro = (RN − HW)/HW",
                          "rows": table})
    return res


# ───────────────────────────── S2A ─────────────────────────────

def analyze_s2a(data):
    tags = order_tags(data)
    fw = firmware.get("s2a")
    res = {"functional": [], "tables": [], "notes": [], "derived": {}}
    lat_rows, work_rows = [], []
    for cond, name in fw.conditions.items():
        lrow = {"condição": name}
        wrow = {"condição": name}
        if cond in oracles.S2A_SPIN_CYCLES:
            wrow["TRM ciclos/iter"] = oracles.S2A_SPIN_CYCLES[cond]
            wrow["instr/iter"] = oracles.S2A_SPIN_INSTR
        for tag in tags:
            lat, first, periods, work = [], [], [], []
            for r in data[tag]:
                rows = sorted((x for x in r.snap.rows if x[1] == cond), key=lambda x: x[0])
                if not rows:
                    continue
                first.append(rows[0][2])
                lat += [x[2] for x in rows[1:]]
                periods += [abi.ticks_delta(a[3], b[3]) for a, b in zip(rows[1:], rows[2:])]
                work += [b[4] - a[4] for a, b in zip(rows[1:], rows[2:])]
            lrow[f"{tag} lat. mín/med/máx"] = "/".join(fmt(v) for v in (min(lat), med(lat), max(lat))) if lat else "—"
            lrow[f"{tag} 1ª IRQ"] = "/".join(map(str, sorted(set(first))))
            lrow[f"{tag} período med (faixa)"] = (f"{fmt(med(periods))} ({min(periods)}..{max(periods)})"
                                                 if periods else "—")
            if cond in oracles.S2A_SPIN_CYCLES:
                wrow[f"{tag} iter/período"] = med(work)
        if cond in oracles.S2A_SPIN_CYCLES and "hw" in data:
            hw = wrow.get("hw iter/período")
            for tag in tags:
                if tag != "hw" and hw:
                    wrow[f"{tag}/HW"] = wrow[f"{tag} iter/período"] / hw
        lat_rows.append(lrow)
        work_rows.append(wrow)
    res["tables"].append({"title": "Latência TIM2 update → 1ª leitura de CNT na ISR (amostras 1..63)",
                          "unit": "ticks do TIM2 (= ciclos HCLK no HW; tempo virtual no Renode)",
                          "rows": lat_rows})
    res["tables"].append({"title": "Trabalho do laço de fundo por período de 8000 ciclos",
                          "unit": "iterações (TRM: ciclos/iteração esperados no HW)",
                          "rows": work_rows})
    return res


# ───────────────────────────── S2B ─────────────────────────────

S2B_EXPECT = {
    # cond: {campo: (valor esperado, referência)}
    1: {"uif": (1, "RM0008 §15.4.5 UIF setado por overflow independente de UIE"),
        "nvic_pending": (0, "sem UIE não há pedido de IRQ")},
    2: {"isr_entries": (1, "NVIC: pendência única (coalescência de 5 eventos)"),
        "pending_after_run": (1, "PM0056 §4.3 ISPR")},
    3: {"isr_entries": (0, "UIF e ICPR limpos antes de habilitar")},
    4: {"isr_entries": (1, "pendência do NVIC é latched (PM0056 §2.3.9)"),
        "spurious": (1, "entra com UIF já limpo")},
    7: {"spurious": (0, "DSB após a escrita (ARM AN321)")},
    8: {"write_to_update": (500, "RM0008 §15.3.1: PSC bufferizado, vale no próximo update"),
        "next_period": (2000, "PSC=1 → 2× período")},
    9: {"uif_after_ug": (1, "RM0008 §15.4.6 EGR.UG gera evento de update (URS=0)")},
    10: {"write_to_update": (500, "RM0008 §15.3.1: ARR com ARPE=1 vale no próximo update"),
         "next_period": (2000, "ARR=1999")},
    11: {"spurious": (0, "leitura de volta força a escrita pela ponte APB")},
}
S2B_TOL = {"write_to_update": 12, "next_period": 12}   # resolução do polling


def _expect_table(data, fw, expect, tol=None, trial=2):
    tags = order_tags(data)
    rows = []
    checks = []
    for cond, name in fw.conditions.items():
        fields = fw.field_names(cond)
        obs = {}
        for tag in tags:
            vals = [x for x in pooled(data[tag], cond) if x[0] == trial] or list(pooled(data[tag], cond))
            obs[tag] = {f: sorted({x[2 + i] for x in vals}) for i, f in enumerate(fields)
                        if not f.startswith("v")}
        for f in (fields if cond in expect or True else ()):
            if f.startswith("v"):
                continue
            exp = expect.get(cond, {}).get(f)
            row = {"condição": name, "campo": f,
                   "esperado (manual)": exp[0] if exp else "—",
                   "referência": exp[1] if exp else "observação"}
            for tag in tags:
                vals = obs[tag].get(f, [])
                row[tag] = "/".join(map(str, vals)) if len(vals) <= 3 else f"{vals[0]}..{vals[-1]}"
                if exp:
                    t = (tol or {}).get(f, 0)
                    ok = all(abs(v - exp[0]) <= t for v in vals) if vals else False
                    row[f"{tag} ✓"] = "sim" if ok else "NÃO"
                    checks.append({"check": f"{name}.{f} = {exp[0]}", "env": tag,
                                   "pass": int(ok), "total": 1})
            rows.append(row)
    return rows, checks


def analyze_s2b(data):
    fw = firmware.get("s2b")
    rows, checks = _expect_table(data, fw, S2B_EXPECT, S2B_TOL, trial=2)
    return {"functional": checks, "tables": [
        {"title": "Semântica TIM2/NVIC (trial 2 — quente)", "unit": "valores de registrador/contagens; tempos em ciclos/ticks",
         "rows": rows}], "notes": [
        "late_clear*: corrida física entre a escrita no SR pela ponte APB e o retorno de exceção; "
        "o resultado no HW depende da razão de clock do APB1 e do layout exato do código."], "derived": {}}


# ───────────────────────────── S3A / S3B ─────────────────────────────

S3A_EXPECT = {
    1: {"received": (32, "loopback"), "mismatches": (0, "")},
    2: {"received": (64, ""), "mismatches": (0, ""),
        "tx_ahead_max": (2, "RM0008 §27.3.2: TDR + registrador de deslocamento (≤2 + 1 em trânsito)")},
    3: {"sr_after_burst": (0xF8, "RM0008 §27.3.3: ORE (bit 3) setado no 2º byte"),
        "drained_more": (0, "RM0008 §27.3.3: só o RDR antigo sobrevive; bytes seguintes perdidos")},
    4: {"received": (32, ""), "stranded_after": (0, "IRQ de nível re-pende enquanto RXNE=1")},
    5: {"received": (32, "")},
    6: {"idle_seen": (1, "RM0008 §27.6.1 IDLE")},
    7: {"tc_right_after_write": (0, "RM0008 §27.3.2: TC só ao fim do quadro"),
        "tc_after_2_frames": (1, "")},
    8: {"data_transmitted": (0, "RM0008 §27.3.2: sem TE o dado não é transmitido")},
}
S3A_TOL = {"tx_ahead_max": 1}


def analyze_s3a(data):
    fw = firmware.get("s3a")
    rows, checks = _expect_table(data, fw, S3A_EXPECT, S3A_TOL, trial=2)
    return {"functional": checks, "tables": [
        {"title": "USART1 em loopback: integridade e semântica de flags (trial 2)",
         "unit": "contagens / valores de SR (hex em decimal)", "rows": rows}],
        "notes": ["A coluna 'esperado' é o STM32F103 do RM0008. A placa da bancada diverge em "
                  "overrun (bufferiza ≥4 bytes sem ORE): evidência de clone — ver relatório S3."],
        "derived": {}}


def analyze_s3b(data):
    tags = order_tags(data)
    rows, bursts = [], []
    for metric, idx in (("t_txe", 2), ("t_tc", 3), ("t_rxne", 4), ("t_idle", 5)):
        row = {"métrica": metric, "teórico": {"t_txe": "≤ 69 (1 bit)", "t_tc": "690",
                                              "t_rxne": "≈ 690 − ½ bit", "t_idle": "≈ 1380"}[metric]}
        for tag in tags:
            vals = [x[idx] for x in pooled(data[tag], 1) if x[0] >= 1]
            row[tag] = f"{fmt(med(vals))} ({min(vals)}..{max(vals)})" if vals else "—"
        rows.append(row)
    for tag in tags:
        ints, writes_ahead = [], []
        for r in data[tag]:
            b = [x for x in r.snap.rows if x[1] == 2]
            for k in range(len(b) // 16):
                chunk = b[16 * k:16 * k + 16]
                rx = [x[3] for x in chunk]
                ints += [y - x for x, y in zip(rx[1:], rx[2:])]
        tc = [x[2] for x in pooled(data[tag], 3)]
        ok = [x[4] for x in pooled(data[tag], 2)]
        bursts.append({"ambiente": tag, "intervalo RXNE med (faixa)": f"{fmt(med(ints))} ({min(ints)}..{max(ints)})" if ints else "—",
                       "TC final 8 bytes (med)": med(tc), "teórico TC 8 bytes": 8 * 690,
                       "bytes corretos": f"{sum(ok)}/{len(ok)}"})
    return {"functional": [], "tables": [
        {"title": "Byte isolado: instante de cada flag após escrever DR (amostras 1..31)",
         "unit": "ciclos/ticks; 1 quadro 8N1 @ BRR 69 = 690", "rows": rows},
        {"title": "Rajada de 16 bytes e vazão", "unit": "ciclos/ticks", "rows": bursts}],
        "notes": [], "derived": {}}


# ───────────────────────────── S4A / S4B ─────────────────────────────

def analyze_s4a(data):
    tags = order_tags(data)
    fw = firmware.get("s4a")
    names = oracles.S4A_EVENTS
    rows, checks = [], []
    for cond, name in fw.conditions.items():
        exp = oracles.s4a_expected(cond)
        row = {"condição": name, "esperado (PM0056)": " ".join(names[e] for e in exp)}
        for tag in tags:
            got = {tuple(oracles.decode_order(x[2])) for x in pooled(data[tag], cond)}
            ok = got == {tuple(exp)}
            row[f"{tag} ✓"] = "sim" if ok else "NÃO: " + " | ".join(" ".join(names.get(e, "?") for e in g) for g in got)
            deltas = [x[7] for x in pooled(data[tag], cond) if x[0] == 2]
            row[f"{tag} Δticks"] = "/".join(map(str, sorted(set(deltas))))
            checks.append({"check": f"ordem {name}", "env": tag, "pass": int(ok), "total": 1})
        rows.append(row)
    return {"functional": checks, "tables": [
        {"title": "Ordem de eventos (contador de sequência atômico) e Δticks",
         "unit": "Δticks: 1–5 pedido→H_ENTER; 6–9 saída do 1º → entrada do 2º; 10 TIM2 pendente sob BASEPRI; 11 nº de entradas TIM2",
         "rows": rows}], "notes": [], "derived": {}}


def s4b_class(order_word: int) -> str:
    seq = oracles.decode_order(order_word & 0xFFFF)
    l_active = (order_word >> 24) & 1
    if 3 not in seq:
        return "H não entrou"
    if l_active:
        return "preempção"
    if 1 in seq and seq.index(3) < seq.index(1):
        return "late-arrival/arbitragem"
    return "sequencial"


def analyze_s4b(data):
    tags = order_tags(data)
    rows, bounds = [], []
    deltas = sorted({x[2] for x in pooled(next(iter(data.values())), 1) if x[0] >= 1})
    for d in deltas:
        row = {"Δ": d}
        for tag in tags:
            cls = {s4b_class(x[5]) for x in pooled(data[tag], 1) if x[0] >= 1 and x[2] == d}
            row[tag] = "/".join(sorted(cls))
        rows.append(row)
    for tag in tags:
        segs, prev = [], None
        for d in deltas:
            cls = "/".join(sorted({s4b_class(x[5]) for x in pooled(data[tag], 1) if x[0] >= 1 and x[2] == d}))
            if cls != prev:
                segs.append(f"Δ≥{d}: {cls}")
                prev = cls
        late = [oracles.s32(x[7]) for x in pooled(data[tag], 1)
                if x[0] >= 1 and s4b_class(x[5]) == "late-arrival/arbitragem" and x[2] > 0]
        hl = [x[4] - x[2] for x in pooled(data[tag], 1) if x[0] >= 1 and s4b_class(x[5]) == "preempção"]
        bounds.append({"ambiente": tag, "regiões": " → ".join(segs),
                       "encadeamento H→L (late)": "/".join(map(str, sorted(set(late)))) or "—",
                       "latência H (CNT−Δ) na preempção": "{}..{}".format(*map(fmt, span(hl)))})
    return {"functional": [], "tables": [
        {"title": "Regiões da corrida UP(L) × CC1(H) com defasagem Δ", "unit": "ciclos/ticks",
         "rows": bounds},
        {"title": "Classificação por Δ", "unit": "", "rows": rows}],
        "notes": ["Discriminante: L ativo (IABR) na entrada de H. DDI0337G §5.7: late-arrival só "
                  "enquanto a 1ª instrução de L não entrou em Execute."], "derived": {}}


ANALYZERS = {"s1a": analyze_s1a, "s1b": analyze_s1b, "s2a": analyze_s2a, "s2b": analyze_s2b,
             "s3a": analyze_s3a, "s3b": analyze_s3b, "s4a": analyze_s4a, "s4b": analyze_s4b}


# ───────────────────────────── saída ─────────────────────────────

def to_markdown(fw: firmware.Firmware, data, res) -> str:
    lines = [f"# {fw.title}", ""]
    lines.append("| ambiente | runs | determinístico entre runs | ELF sha256 | revisão |")
    lines.append("|---|---|---|---|---|")
    for tag in order_tags(data):
        det = determinism(data[tag])
        m = data[tag][0].manifest
        lines.append(f"| {tag} | {det['runs']} | {'sim' if det['identical'] else 'NÃO (' + str(det['distinct_row_sets']) + ' conjuntos)'} "
                     f"| `{m.get('elf_sha256', '')[:12]}` | {m.get('revision', '')} |")
    if res["functional"]:
        lines += ["", "## Verificações funcionais", "", "| verificação | ambiente | resultado |", "|---|---|---|"]
        for c in res["functional"]:
            lines.append(f"| {c['check']} | {c['env']} | {c['pass']}/{c['total']} |")
    for t in res["tables"]:
        lines += ["", f"## {t['title']}", "", f"*Unidade: {t['unit']}*" if t["unit"] else "", ""]
        cols = list(dict.fromkeys(k for r in t["rows"] for k in r))
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "---|" * len(cols))
        for r in t["rows"]:
            lines.append("| " + " | ".join(fmt(r.get(c)) for c in cols) + " |")
    if res.get("derived"):
        lines += ["", "## Derivados", "", "```json", json.dumps(res["derived"], indent=2, ensure_ascii=False), "```"]
    if res.get("notes"):
        lines += ["", "## Notas", ""] + [f"- {n}" for n in res["notes"]]
    return "\n".join(lines) + "\n"


def main(args) -> int:
    names = args.firmware or list(firmware.FIRMWARES)
    out_dir = ROOT / "data" / "fidelity" / args.campaign / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    index = [f"# Campanha `{args.campaign}`", ""]
    for name in names:
        fw = firmware.get(name)
        data = load(args.campaign, name)
        if not data:
            print(f"[analyze] {name}: sem runs completos")
            continue
        res = ANALYZERS[name](data)
        res["determinism"] = {tag: determinism(runs) for tag, runs in data.items()}
        res["runs"] = {tag: [str(r.path.relative_to(ROOT)) for r in runs] for tag, runs in data.items()}
        (out_dir / f"{name}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
        (out_dir / f"{name}.md").write_text(to_markdown(fw, data, res))
        perfetto.write(out_dir / f"{name}.perfetto.json", fw, {t: data[t][0] for t in order_tags(data)})
        fails = [c for c in res["functional"] if c["pass"] != c["total"]]
        index.append(f"- [{fw.title}]({name}.md) — ambientes: {', '.join(order_tags(data))}; "
                     f"verificações com divergência: {len(fails)}")
        print(f"[analyze] {name}: {len(data)} ambientes, {len(fails)} verificações divergentes")
    (out_dir / "index.md").write_text("\n".join(index) + "\n")
    return 0
