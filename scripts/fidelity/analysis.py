"""Análise de uma campanha: contabilidade, estatística, classificação e relatório.

Entrada: data/fidelity/<campanha>/ (plano + tentativas). Saída em analysis/:
    accounting.csv   planejado / tentativas / válidos / inválidos por ambiente
    checks.csv       cada verificação funcional de cada run (valor esperado/observado)
    metrics.csv      cada métrica temporal de cada run
    stats.csv        estatística por (firmware, caso, métrica, ambiente)
    cases.csv        classificação por caso (condição)
    resources.csv    mapa de limites por recurso: funcional × instrução × ciclo
    c1_instructions.csv  contagem dinâmica (stepi) × ticks (C1-timing)
    report.md        relatório técnico gerado (não é a monografia)
    figures/*.png, perfetto/*.json

Critérios (declarados ANTES da campanha; ver README "Critérios"):
  - funcional: igualdade exata com o oráculo (especificação) e, para a
    fidelidade, igualdade do valor modal Renode × placa em cada item;
  - temporal no nível de CICLO: mediana do Renode dentro de
    [mín − res, máx + res] da placa, com res = resolução do ponto de
    observação; fora disso → divergência temporal, reportada com erro
    absoluto e relativo (sem tolerância de "aceitável": nenhum prazo de
    aplicação foi definido);
  - instrução (C1): sequência de PCs por stepi idêntica nos dois ambientes.
Classes por caso: 1 concordância funcional e temporal; 2 funcional com
divergência temporal; 3 divergência funcional; 4 evidência insuficiente.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev

from . import abi, c1, c2, c3, c4
from .firmwares import FIRMWARES
from .model import RunEval

ENV_LABEL = {"hw": "placa", "renode-nominal": "Renode 8 MIPS", "renode-calibrated": "Renode calibrado"}
CLASSES = {1: "concordância funcional e temporal", 2: "concordância funcional, divergência temporal",
           3: "divergência funcional", 4: "evidência insuficiente"}


@dataclass
class Run:
    env: str
    firmware: str
    name: str
    path: Path
    record: dict
    snapshot: abi.Snapshot | None = None
    eval: RunEval | None = None

    @property
    def valid(self) -> bool:
        return self.record.get("status") == "valid" and self.eval is not None


def load_runs(root: Path, plan: dict) -> list[Run]:
    runs = []
    for env in ("hw", "renode-nominal", "renode-calibrated"):
        for fw in plan["firmwares"]:
            for rec_path in sorted((root / env / fw).glob("run-*/run.json")):
                rec = json.loads(rec_path.read_text())
                run = Run(env, fw, rec_path.parent.name, rec_path.parent, rec)
                if rec.get("status") == "valid":
                    try:
                        run.snapshot = abi.decode((rec_path.parent / "snapshot.bin").read_bytes())
                        run.eval = FIRMWARES[fw].evaluate(run.snapshot)
                        if run.eval.problems:
                            run.record = {**rec, "status": "invalid",
                                          "problems": rec.get("problems", []) + run.eval.problems}
                    except abi.SnapshotError as exc:
                        run.record = {**rec, "status": "invalid", "problems": [str(exc)]}
                        run.eval = None
                    except (ValueError, IndexError, TypeError, KeyError) as exc:
                        run.record = {**rec, "status": "invalid",
                                      "problems": [f"avaliação falhou (layout inesperado): {exc!r}"]}
                        run.eval = None
                runs.append(run)
    return runs


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0])
    for r in rows[1:]:
        keys += [k for k in r if k not in keys]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


# ───────────────────────────── agregação ─────────────────────────────

def accounting(runs: list[Run], plan: dict) -> list[dict]:
    rows = []
    planned_envs = {"hw": "hw", "renode": "renode-nominal"}
    envs = sorted({r.env for r in runs} | {planned_envs[e] for e in plan["environments"]})
    for env in envs:
        for fw in plan["firmwares"]:
            mine = [r for r in runs if r.env == env and r.firmware == fw]
            if not mine and env == "renode-calibrated":
                continue
            status = Counter(r.record.get("status") if not (r.record.get("status") == "valid" and r.eval is None)
                             else "invalid" for r in mine)
            reasons = Counter(p for r in mine if not r.valid for p in r.record.get("problems", [])[:1])
            rows.append({"environment": env, "firmware": fw,
                         "planned": plan["repetitions"], "attempts": len(mine),
                         "valid": sum(r.valid for r in mine),
                         "invalid": status.get("invalid", 0), "infra_error": status.get("infra_error", 0),
                         "complete": sum(r.valid for r in mine) >= plan["repetitions"],
                         "reasons": "; ".join(f"{k} (×{v})" for k, v in reasons.most_common(3))})
    return rows


def check_rows(runs: list[Run]) -> list[dict]:
    rows = []
    for r in runs:
        if not r.valid:
            continue
        for case, status in r.eval.case_status.items():
            rows.append({"environment": r.env, "firmware": r.firmware, "run": r.name, "case": case,
                         "item": "status do protocolo do caso", "expected": "OK",
                         "observed": status, "ok": status == "OK"})
        for c in r.eval.checks:
            rows.append({"environment": r.env, "firmware": r.firmware, "run": r.name, "case": c.case,
                         "item": c.item,
                         "expected": "(sem oráculo)" if c.expected is None else _fmt(c.expected),
                         "observed": _fmt(c.observed), "ok": c.ok})
    return rows


def metric_rows(runs: list[Run]) -> list[dict]:
    rows = []
    for r in runs:
        if not r.valid:
            continue
        for m in r.eval.metrics:
            rows.append({"environment": r.env, "firmware": r.firmware, "run": r.name, "case": m.case,
                         "metric": m.name, "value": m.value, "unit": m.unit,
                         "resolution": m.resolution, "predicted": m.predicted})
    return rows


def _fmt(v) -> str:
    if isinstance(v, int) and not isinstance(v, bool) and v > 0xFFFF:
        return f"0x{v:x}"
    return str(v)


def stats_rows(metrics: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for m in metrics:
        groups[(m["firmware"], m["case"], m["metric"], m["environment"])].append(m)
    rows = []
    for (fw, case, metric, env), ms in sorted(groups.items()):
        vals = [m["value"] for m in ms]
        rows.append({"firmware": fw, "case": case, "metric": metric, "environment": env,
                     "n": len(vals), "mean": mean(vals), "std": pstdev(vals) if len(vals) > 1 else 0.0,
                     "median": median(vals), "min": min(vals), "max": max(vals),
                     "distinct_values": len(set(vals)), "predicted": ms[0]["predicted"],
                     "resolution": ms[0]["resolution"], "unit": ms[0]["unit"]})
    return rows


# ───────────────────────────── classificação ─────────────────────────────

def group_of(fw: str, case: str) -> str:
    """Recurso (linha do mapa de limites) de um caso."""
    if fw == "c1-functional":
        cid = next(k for k, v in c1.CASES.items() if v == case)
        return f"C1 · {c1.CASE_GROUP[cid]}"
    if fw == "c1-timing":
        load = case.split("/")[0]
        return f"C1 · tempo de carga: {load}"
    if fw == "c2":
        return f"C2 · {c2.GROUP[case.split('/')[-1]]}"
    if fw == "c3":
        return f"C3 · {c3.GROUP[int(case.split('/')[1], 16)]}"
    if fw == "c4":
        return f"C4 · {c4.GROUP[int(case.split('/')[1], 16)]}"
    return fw


def classify(checks: list[dict], stats: list[dict], ref_env: str, sim_env: str,
             firmwares: list[str]) -> list[dict]:
    by_case_item: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in checks:
        if c["environment"] in (ref_env, sim_env):
            by_case_item[(c["firmware"], c["case"], c["item"])][c["environment"]].append(c)
    st = {(s["firmware"], s["case"], s["metric"], s["environment"]): s for s in stats}
    cases = sorted({(fw, case) for fw, case, _ in by_case_item} |
                   {(s["firmware"], s["case"]) for s in stats if s["environment"] in (ref_env, sim_env)})
    rows = []
    for fw, case in cases:
        if fw not in firmwares:
            continue
        items = [(k[2], v) for k, v in by_case_item.items() if k[0] == fw and k[1] == case]
        reasons, func_div, unstable = [], [], []
        insufficient = False
        hw_spec_fail, rn_spec_fail = [], []
        for item, envs in items:
            if not envs.get(ref_env) or not envs.get(sim_env):
                insufficient = True
                reasons.append(f"'{item}' sem dados nos dois ambientes")
                continue
            ref_vals = Counter(c["observed"] for c in envs[ref_env])
            sim_vals = Counter(c["observed"] for c in envs[sim_env])
            if not all(c["ok"] for c in envs[ref_env]):
                hw_spec_fail.append(item)
            if not all(c["ok"] for c in envs[sim_env]):
                rn_spec_fail.append(item)
            if len(ref_vals) > 1 or len(sim_vals) > 1:
                unstable.append(item)
            if ref_vals.most_common(1)[0][0] != sim_vals.most_common(1)[0][0]:
                func_div.append(item)
        temporal, temporal_div = [], []
        for (sfw, scase, metric, env), s in st.items():
            if sfw != fw or scase != case or env != ref_env or s["unit"] == "bytes":
                continue
            sim = st.get((fw, case, metric, sim_env))
            if sim is None:
                continue
            res = s["resolution"]
            agree = s["min"] - res <= sim["median"] <= s["max"] + res
            err = sim["median"] - s["median"]
            rel = err / s["median"] if s["median"] else float("nan")
            temporal.append((metric, agree, err, rel))
            if not agree:
                temporal_div.append(f"{metric}: {err:+.1f} ({rel:+.1%})")
        if insufficient or (not items and not temporal):
            cls = 4
        elif func_div:
            cls = 3
        elif temporal_div:
            cls = 2
        else:
            cls = 1
        name = CLASSES[cls]
        if cls == 1 and not temporal:
            name = "concordância funcional (sem observável temporal)"
        elif cls in (1, 2) and not items:
            name = ("concordância temporal" if cls == 1 else "divergência temporal") + \
                " (sem observável funcional)"
        rows.append({
            "firmware": fw, "case": case, "group": group_of(fw, case), "class": cls,
            "class_name": name,
            "functional_divergences": "; ".join(func_div),
            "hw_vs_spec": "ok" if not hw_spec_fail else "diverge: " + "; ".join(hw_spec_fail),
            "sim_vs_spec": "ok" if not rn_spec_fail else "diverge: " + "; ".join(rn_spec_fail),
            "variable_across_runs": "; ".join(unstable),
            "temporal_metrics": len(temporal),
            "temporal_agree": sum(1 for t in temporal if t[1]),
            "temporal_divergences": "; ".join(temporal_div),
            "median_abs_rel_error": median([abs(t[3]) for t in temporal if t[3] == t[3]])
            if temporal else None,
            "max_abs_rel_error": max([abs(t[3]) for t in temporal if t[3] == t[3]], default=None),
            "reasons": "; ".join(reasons),
        })
    return rows


def resource_map(cases: list[dict], instr_rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        groups[c["group"]].append(c)
    instr_ok = {r["load"]: r["same_pc_sequence"] for r in instr_rows}
    rows = []
    for g, cs in groups.items():
        cls = Counter(c["class"] for c in cs)
        if cls.get(4):
            functional = "evidência insuficiente"
        elif cls.get(3):
            functional = f"diverge ({cls[3]}/{len(cs)} casos)"
        else:
            functional = "concorda"
        n_temp = sum(c["temporal_metrics"] for c in cs)
        if n_temp == 0:
            cycle = "—"
        elif all(c["temporal_metrics"] == c["temporal_agree"] for c in cs):
            cycle = "concorda"
        else:
            n_ok = sum(c["temporal_agree"] for c in cs)
            errs = [c["median_abs_rel_error"] for c in cs if c["median_abs_rel_error"] is not None]
            worst = max((c["max_abs_rel_error"] for c in cs if c["max_abs_rel_error"] is not None),
                        default=None)
            cycle = f"diverge ({n_temp - n_ok}/{n_temp} métricas"
            if errs:
                cycle += f"; erro rel. mediano {median(errs):.1%}, máx. {worst:.1%}"
            cycle += ")"
        instruction = "—"
        if g.startswith("C1 · tempo de carga: "):
            load = g.split(": ")[1]
            if load in instr_ok:
                instruction = "concorda (mesma sequência de PCs)" if instr_ok[load] else "diverge"
            else:
                instruction = "sem traço"
        hw_spec = "ok" if all(c["hw_vs_spec"] == "ok" for c in cs) else "diverge da especificação"
        sim_spec = "ok" if all(c["sim_vs_spec"] == "ok" for c in cs) else "diverge da especificação"
        rows.append({"resource": g, "cases": len(cs), "functional": functional,
                     "instruction": instruction, "cycle": cycle,
                     "hw_vs_spec": hw_spec, "sim_vs_spec": sim_spec,
                     "classes": ", ".join(f"{k}:{v}" for k, v in sorted(cls.items()))})
    return sorted(rows, key=lambda r: r["resource"])


# ───────────────────────────── C1: instruções e calibração ─────────────────────────────

def c1_instruction_rows(root: Path, stats: list[dict]) -> list[dict]:
    paths = {env: root / "instr" / env / "instructions.json" for env in ("hw", "renode")}
    if not all(p.exists() for p in paths.values()):
        return []
    hw, rn = (json.loads(paths[e].read_text()) for e in ("hw", "renode"))
    warm = {(s["case"], s["environment"]): s["median"] for s in stats
            if s["firmware"] == "c1-timing" and s["metric"] == "warm"}
    rows = []
    for key in sorted(hw, key=lambda k: (c1.LOADS.index(k.split("/")[0]), int(k.split("/")[1]))):
        h, r = hw[key], rn.get(key)
        t_hw, t_rn = warm.get((key, "hw")), warm.get((key, "renode-nominal"))
        rows.append({
            "case": key, "load": h["load"], "n": h["n"],
            "instructions_hw": h["count"], "instructions_renode": r["count"] if r else None,
            "same_pc_sequence": bool(r) and h["pcs_sha256"] == r["pcs_sha256"],
            "ticks_hw_warm": t_hw, "ticks_renode_warm": t_rn,
            "cpi_hw": t_hw / h["count"] if t_hw and h["count"] else None,
            "renode_ticks_minus_instructions": (t_rn - r["count"]) if (t_rn is not None and r) else None,
        })
    # Por carga: todas as sequências (3 tamanhos) iguais?
    per_load = defaultdict(list)
    for row in rows:
        per_load[row["load"]].append(row["same_pc_sequence"])
    for row in rows:
        row["same_pc_sequence_all_sizes"] = all(per_load[row["load"]])
    return rows


def calibration_summary(root: Path, stats: list[dict]) -> dict | None:
    cal_path = root / "calibration.json"
    if not cal_path.exists():
        return None
    cal = json.loads(cal_path.read_text())
    recs = sorted((root / "renode-calibrated" / "c1-timing").glob("run-*/run.json"))
    if recs:
        cal["effective_mips"] = json.loads(recs[0].read_text()).get("performance_in_mips_effective")
    warm = {(s["case"], s["environment"]): s["median"] for s in stats
            if s["firmware"] == "c1-timing" and s["metric"] == "warm"}
    rows = []
    for load in c1.LOADS[1:]:
        for n in c1.SIZES:
            key = f"{load}/{n}"
            hw = warm.get((key, "hw"))
            nom = warm.get((key, "renode-nominal"))
            cal_v = warm.get((key, "renode-calibrated"))
            role = ("treino" if load in cal["rule"]["training_loads"] else
                    "avaliação" if load in cal["rule"]["evaluation_loads"] else "—")
            rows.append({"case": key, "role": role, "hw": hw, "nominal": nom, "calibrated": cal_v,
                         "err_nominal": (nom - hw) / hw if hw and nom else None,
                         "err_calibrated": (cal_v - hw) / hw if hw and cal_v else None})
    cal["per_case"] = rows

    def mare(role, col):
        vals = [abs(r[col]) for r in rows if r["role"] == role and r[col] is not None]
        return sum(vals) / len(vals) if vals else None
    cal["aggregate"] = {f"{role}_{col}": mare(role, col) for role in ("treino", "avaliação")
                        for col in ("err_nominal", "err_calibrated")}
    return cal


def determinism(metrics: list[dict], checks: list[dict]) -> list[dict]:
    """Fração de observáveis com o MESMO valor em todos os runs, por ambiente."""
    rows = []
    for env in sorted({m["environment"] for m in metrics} | {c["environment"] for c in checks}):
        vals = defaultdict(set)
        for m in metrics:
            if m["environment"] == env:
                vals[("m", m["firmware"], m["case"], m["metric"])].add(m["value"])
        for c in checks:
            if c["environment"] == env:
                vals[("c", c["firmware"], c["case"], c["item"])].add(c["observed"])
        constant = sum(1 for v in vals.values() if len(v) == 1)
        rows.append({"environment": env, "observables": len(vals), "identical_in_all_runs": constant,
                     "fraction": constant / len(vals) if vals else None})
    return rows


# ───────────────────────────── orquestração ─────────────────────────────

def analyze(root: Path, log=print) -> dict:
    plan = json.loads((root / "plan.json").read_text())
    out = root / "analysis"
    out.mkdir(exist_ok=True)
    runs = load_runs(root, plan)
    acc = accounting(runs, plan)
    checks = check_rows(runs)
    metrics = metric_rows(runs)
    stats = stats_rows(metrics)
    fws = list(plan["firmwares"])
    cases = classify(checks, stats, "hw", "renode-nominal", fws)
    instr_rows = c1_instruction_rows(root, stats)
    resources = resource_map(cases, instr_rows)
    cal = calibration_summary(root, stats)
    det = determinism(metrics, checks)
    write_csv(out / "accounting.csv", acc)
    write_csv(out / "checks.csv", checks)
    write_csv(out / "metrics.csv", metrics)
    write_csv(out / "stats.csv", stats)
    write_csv(out / "cases.csv", cases)
    write_csv(out / "resources.csv", resources)
    write_csv(out / "c1_instructions.csv", instr_rows)
    write_csv(out / "determinism.csv", det)
    if cal:
        (out / "calibration.json").write_text(json.dumps(cal, indent=2, ensure_ascii=False))
    from . import figures, perfetto, report
    figs = figures.make_all(out / "figures", stats, metrics, instr_rows, cal)
    traces = perfetto.export_campaign(root, runs, out / "perfetto", log)
    summary = {
        "campaign": plan["campaign"], "mode": plan["mode"], "board": plan["board"],
        "complete": all(a["complete"] for a in acc if a["environment"] in ("hw", "renode-nominal")),
        "accounting": acc, "classes": Counter(c["class"] for c in cases),
        "figures": figs, "perfetto": traces,
    }
    report.write(out / "report.md", plan, summary, acc, cases, resources, stats, instr_rows,
                 cal, det, checks, root)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return summary
