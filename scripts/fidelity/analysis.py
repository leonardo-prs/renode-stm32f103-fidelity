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

Comparações descritivas: funcional exige todas as observações conformes ao
oráculo e constantes/iguais entre ambientes; falhas ocasionais ficam visíveis.
Tempo: diferenças entre medianas de runs, sem margem de aceitação universal.
A resolução declarada pelo oráculo não é um limite instrumental validado.
Nenhum resultado desta análise demonstra precisão universal de ciclo/ISA.
"""
from __future__ import annotations

import csv
import json
import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, stdev

from . import abi, c1, c2, c3, c4
from .firmwares import FIRMWARES
from .model import RunEval

ENV_LABEL = {"hw": "placa", "renode-nominal": "Renode 8 MIPS", "renode-calibrated": "Renode calibrado"}
CLASSES = {1: "concordância funcional; mesmas medianas temporais observadas", 2: "concordância funcional, diferença temporal observada",
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
    """Lê todas as tentativas e REVALIDA as válidas com o código atual.

    Um run só entra na análise se: o snapshot tem o SHA-256 registrado, foi
    produzido pelo ELF congelado no plano, decodifica (ABI atual) e passa
    nas verificações de instrumento do firmware (nonce, casos, estado).
    """
    if plan.get("abi_version") != abi.ABI_VERSION:
        raise ValueError(f"plano de outra ABI ({plan.get('abi_version')}); use a versão do código "
                         "com que a campanha foi coletada")
    runs = []
    for env in ("hw", "renode-nominal", "renode-calibrated"):
        for name, spec in plan["firmwares"].items():
            fw = FIRMWARES[name]
            seen_nonces = set()
            for rec_path in sorted((root / env / name).glob("run-*/run.json")):
                rec = json.loads(rec_path.read_text())
                run = Run(env, name, rec_path.parent.name, rec_path.parent, rec)
                runs.append(run)
                if rec.get("status") != "valid":
                    continue
                problems = []
                raw = (rec_path.parent / "snapshot.bin").read_bytes()
                if hashlib.sha256(raw).hexdigest() != rec.get("snapshot_sha256"):
                    problems.append("snapshot diferente do registrado (hash)")
                if rec.get("elf_sha256") != spec["elf_sha256"]:
                    problems.append("run de outro ELF (diferente do plano)")
                if rec.get("nonce") in seen_nonces:
                    problems.append("nonce repetido: não é um reset independente")
                try:
                    run.snapshot = abi.decode(raw)
                    problems += fw.validate(run.snapshot, rec.get("nonce"))
                    run.eval = fw.evaluate(run.snapshot)
                except (abi.SnapshotError, ValueError, IndexError, KeyError) as exc:
                    problems.append(f"revalidação falhou: {exc}")
                if problems:
                    run.record = {**rec, "status": "invalid", "problems": problems}
                    run.eval = None
                else:
                    seen_nonces.add(rec.get("nonce"))
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
    envs = sorted({r.env for r in runs} | {planned_envs[e] for e in plan["environments"]}
                  | ({"renode-calibrated"} if plan.get("calibration", {}).get("enabled") and "c1-timing" in plan["firmwares"] else set()))
    for env in envs:
        for fw in plan["firmwares"]:
            mine = [r for r in runs if r.env == env and r.firmware == fw]
            if env == "renode-calibrated" and (fw != "c1-timing" or not plan.get("calibration", {}).get("enabled")):
                if not mine:
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
                         "has_oracle": c.expected is not None,
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
                         "resolution": m.resolution, "predicted": m.predicted,
                         "resolution_basis": getattr(m, "resolution_basis", "não validada"),
                         "core_hz": r.snapshot.header["core_hz"] if r.snapshot else None,
                         "session": r.record.get("config", {}).get("session"),
                         "finished_utc": r.record.get("finished_utc")})
    return rows


def _fmt(v) -> str:
    if isinstance(v, int) and not isinstance(v, bool) and v > 0xFFFF:
        return f"0x{v:x}"
    return str(v)


def stats_rows(metrics: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for m in metrics:
        if not math.isfinite(m["value"]) or not math.isfinite(m["resolution"]) or m["resolution"] < 0:
            raise ValueError("métrica não finita ou resolução inválida")
        groups[(m["firmware"], m["case"], m["metric"], m["environment"])].append(m)
    rows = []
    for (fw, case, metric, env), ms in sorted(groups.items()):
        if len({m["unit"] for m in ms}) != 1:
            raise ValueError(f"unidades incompatíveis em {fw}/{case}/{metric}/{env}")
        by_run = defaultdict(list)
        for m in ms:
            by_run[m["run"]].append(m["value"])
        # Uma mediana por reset; eventos internos nunca aumentam n independente.
        vals = [median(v) for v in by_run.values()]
        predictions = {m["predicted"] for m in ms}
        rows.append({"firmware": fw, "case": case, "metric": metric, "environment": env,
                     "n": len(vals), "samples": len(ms), "aggregation": "mediana por run",
                     "mean": mean(vals), "std": stdev(vals) if len(vals) > 1 else None,
                     "median": median(vals), "min": min(vals), "max": max(vals),
                     "distinct_values": len(set(vals)),
                     "predicted": next(iter(predictions)) if len(predictions) == 1 else None,
                     "prediction_consistent": len(predictions) == 1,
                     "resolution": max(m["resolution"] for m in ms),
                     "resolution_validated": False, "unit": ms[0]["unit"]})
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
        if case == "c3/config":
            return "C3 · configuração do núcleo e clock"
        return f"C3 · {c3.GROUP[int(case.split('/')[1], 16)]}"
    if fw == "c4":
        return f"C4 · {c4.GROUP[int(case.split('/')[1], 16)]}"
    return fw


def classify(checks: list[dict], stats: list[dict], ref_env: str, sim_env: str,
             firmwares: list[str], expected_cases: list[tuple[str, str]] | None = None) -> list[dict]:
    by_case_item: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for c in checks:
        if c["environment"] in (ref_env, sim_env):
            by_case_item[(c["firmware"], c["case"], c["item"])][c["environment"]].append(c)
    st = {(s["firmware"], s["case"], s["metric"], s["environment"]): s for s in stats}
    case_runs = defaultdict(set)
    for c in checks:
        case_runs[(c["firmware"], c["case"], c["environment"])].add(c["run"])
    cases = sorted(set(expected_cases or []) | {(fw, case) for fw, case, _ in by_case_item} |
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
            if any(not c["ok"] for c in envs.get(ref_env, []) if c.get("has_oracle", True)):
                hw_spec_fail.append(item)
            if any(not c["ok"] for c in envs.get(sim_env, []) if c.get("has_oracle", True)):
                rn_spec_fail.append(item)
            if not envs.get(ref_env) or not envs.get(sim_env):
                insufficient = True
                reasons.append(f"'{item}' sem dados nos dois ambientes")
                continue
            for env in (ref_env, sim_env):
                if {c["run"] for c in envs[env]} != case_runs[(fw, case, env)]:
                    insufficient = True
                    reasons.append(f"'{item}' omitido em parte dos runs de {env}")
            if len({c["expected"] for env in (ref_env, sim_env) for c in envs[env]}) > 1:
                insufficient = True
                reasons.append(f"'{item}' expectativas incompatíveis entre runs/ambientes")
            ref_vals = Counter(c["observed"] for c in envs[ref_env])
            sim_vals = Counter(c["observed"] for c in envs[sim_env])
            if len(ref_vals) > 1 or len(sim_vals) > 1:
                unstable.append(item)
            if set(ref_vals) != set(sim_vals):
                func_div.append(item)
            elif len(ref_vals) > 1 or len(sim_vals) > 1:
                insufficient = True
                reasons.append(f"'{item}' variável: equivalência da distribuição não estabelecida")
        temporal, temporal_div = [], []
        metrics = {k[2] for k in st if k[:2] == (fw, case) and k[3] in (ref_env, sim_env)}
        for metric in sorted(metrics):
            s, sim = st.get((fw, case, metric, ref_env)), st.get((fw, case, metric, sim_env))
            if s is None or sim is None:
                insufficient = True
                reasons.append(f"'{metric}' sem métrica nos dois ambientes")
                continue
            if s["unit"] != sim["unit"] or s["predicted"] != sim["predicted"] or not s.get("prediction_consistent", True) or not sim.get("prediction_consistent", True):
                insufficient = True
                reasons.append(f"'{metric}' unidade/previsão incompatível")
                continue
            if s["unit"] == "bytes":
                continue
            for env, value in ((ref_env, s), (sim_env, sim)):
                if value["n"] < len(case_runs[(fw, case, env)]):
                    insufficient = True
                    reasons.append(f"'{metric}' omitido em parte dos runs de {env}")
            # Igualdade descritiva, sem utilizar bounds instrumentais não provados.
            agree = sim["median"] == s["median"]
            err = sim["median"] - s["median"]
            rel = err / s["median"] if s["median"] else None
            temporal.append((metric, agree, err, rel))
            if not agree:
                temporal_div.append(f"{metric}: {err:+.6g} {s['unit']}" +
                                    (f" ({rel:+.1%})" if rel is not None else " (referência zero)"))
        if func_div or hw_spec_fail or rn_spec_fail:
            cls = 3
        elif insufficient or (not items and not temporal):
            cls = 4
        elif temporal_div:
            cls = 2
        else:
            cls = 1
        name = CLASSES[cls]
        if cls == 3 and not func_div:
            name = "não conformidade com especificação (sem diferença HW×Renode demonstrada)"
        comparison = ("valores diferentes observados" if func_div else
                      "sem evidência suficiente" if insufficient or not items else
                      "mesmos valores constantes observados")
        if cls == 1 and not temporal:
            name = "concordância funcional (sem observável temporal)"
        elif cls in (1, 2) and not items:
            name = ("concordância temporal" if cls == 1 else "divergência temporal") + \
                " (sem observável funcional)"
        rows.append({
            "firmware": fw, "case": case, "group": group_of(fw, case), "class": cls,
            "class_name": name,
            "functional_divergences": "; ".join(func_div),
            "functional_comparison": comparison,
            "specification_failures": "; ".join([f"{ref_env}: {x}" for x in hw_spec_fail] +
                                                   [f"{sim_env}: {x}" for x in rn_spec_fail]),
            "hw_vs_spec": ("diverge: " + "; ".join(hw_spec_fail)) if hw_spec_fail else
                ("ok" if items and all(v.get(ref_env) for _, v in items) else "sem evidência"),
            "sim_vs_spec": ("diverge: " + "; ".join(rn_spec_fail)) if rn_spec_fail else
                ("ok" if items and all(v.get(sim_env) for _, v in items) else "sem evidência"),
            "variable_across_runs": "; ".join(unstable),
            "functional_items": len(items),
            "temporal_interpretation": "comparação observada; adequação temporal não estabelecida",
            "temporal_metrics": len(temporal),
            "temporal_agree": sum(1 for t in temporal if t[1]),
            "temporal_divergences": "; ".join(temporal_div),
            "median_abs_rel_error": median([abs(t[3]) for t in temporal if t[3] is not None])
            if any(t[3] is not None for t in temporal) else None,
            "max_abs_rel_error": max([abs(t[3]) for t in temporal if t[3] is not None], default=None),
            "reasons": "; ".join(reasons),
        })
    return rows


def resource_map(cases: list[dict], instr_rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        groups[c["group"]].append(c)
    instr_ok = {}
    for r in instr_rows:
        instr_ok[r["load"]] = instr_ok.get(r["load"], True) and r["same_pc_sequence_all_sizes"]
    rows = []
    for g, cs in groups.items():
        cls = Counter(c["class"] for c in cs)
        functional_cases = [c for c in cs if c["functional_items"]]
        differences = sum(bool(c["functional_divergences"]) for c in functional_cases)
        if not functional_cases:
            functional = "sem observável funcional"
        elif differences:
            functional = f"valores diferentes observados ({differences}/{len(functional_cases)} casos funcionais)"
        elif any(c["functional_comparison"] == "sem evidência suficiente" for c in functional_cases):
            functional = "evidência insuficiente"
        else:
            functional = "mesmos valores constantes observados"
        n_temp = sum(c["temporal_metrics"] for c in cs)
        if n_temp == 0:
            cycle = "—"
        elif cls.get(4):
            cycle = "evidência insuficiente"
        elif all(c["temporal_metrics"] == c["temporal_agree"] for c in cs):
            cycle = "mesmas medianas observadas; adequação não estabelecida"
        else:
            n_ok = sum(c["temporal_agree"] for c in cs)
            errs = [c["median_abs_rel_error"] for c in cs if c["median_abs_rel_error"] is not None]
            worst = max((c["max_abs_rel_error"] for c in cs if c["max_abs_rel_error"] is not None),
                        default=None)
            cycle = f"diferença observada ({n_temp - n_ok}/{n_temp} métricas"
            if errs:
                cycle += f"; erro rel. mediano {median(errs):.1%}, máx. {worst:.1%}"
            cycle += ")"
        instruction = "—"
        if g.startswith("C1 · tempo de carga: "):
            load = g.split(": ")[1]
            if load in instr_ok:
                instruction = "mesmo caminho observado (PCs; não valida estado por instrução)" if instr_ok[load] else "diverge"
            else:
                instruction = "sem traço"
        def spec_status(key):
            if any(c[key].startswith("diverge") for c in functional_cases):
                return "diverge da especificação"
            return "ok" if functional_cases and all(c[key] == "ok" for c in functional_cases) else "sem evidência"
        hw_spec, sim_spec = spec_status("hw_vs_spec"), spec_status("sim_vs_spec")
        rows.append({"resource": g, "cases": len(cs), "functional": functional,
                     "instruction": instruction, "cycle": cycle,
                     "hw_vs_spec": hw_spec, "sim_vs_spec": sim_spec,
                     "classes": ", ".join(f"{k}:{v}" for k, v in sorted(cls.items()))})
    return sorted(rows, key=lambda r: r["resource"])


# ───────────────────────────── C1: instruções e calibração ─────────────────────────────

def _instruction_data(root: Path, env: str) -> dict:
    """Resultado do stepi de um ambiente, conferido contra o ELF congelado."""
    plan = json.loads((root / "plan.json").read_text())
    out = root / "instr" / env
    meta = json.loads((out / "trace.json").read_text())
    if meta.get("elf_sha256") != plan["firmwares"]["c1-timing"]["elf_sha256"]:
        raise ValueError(f"traço stepi de {env} é de outro ELF")
    doc = json.loads((out / "instructions.json").read_text())
    expected = {"empty/0"} | {f"{load}/{n}" for load in c1.LOADS[1:] for n in c1.SIZES}
    if set(doc) != expected:
        raise ValueError(f"traço stepi de {env}: conjunto de cargas/tamanhos incompleto")
    return doc


def c1_instruction_rows(root: Path, stats: list[dict]) -> list[dict]:
    paths = {env: root / "instr" / env / "instructions.json" for env in ("hw", "renode")}
    if not all(p.exists() for p in paths.values()):
        return []
    hw, rn = (_instruction_data(root, e) for e in ("hw", "renode"))
    warm = {(s["case"], s["environment"]): s["median"] for s in stats
            if s["firmware"] == "c1-timing" and s["metric"] == "warm"}
    rows = []
    for key in sorted(hw, key=lambda k: (c1.LOADS.index(k.split("/")[0]), int(k.split("/")[1]))):
        h, r = hw[key], rn.get(key)
        t_hw, t_rn = warm.get((key, "hw")), warm.get((key, "renode-nominal"))
        rows.append({
            "case": key, "load": h["load"], "n": h["n"],
            "instructions_hw": h["count"], "instructions_renode": r["count"] if r else None,
            "same_pc_sequence": bool(r) and h["count"] == r["count"] and h["pcs_sha256"] == r["pcs_sha256"],
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
    if type(cal.get("chosen_mips")) is not int or not 1 <= cal["chosen_mips"] <= 16:
        raise ValueError("MIPS calibrado fora da faixa planejada 1..16")
    # Valor efetivo só é apresentado quando há estatísticas de runs revalidados.
    cal["effective_mips"] = cal["chosen_mips"] if any(s["environment"] == "renode-calibrated" for s in stats) else None
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
                         "err_nominal": (nom - hw) / hw if hw is not None and hw != 0 and nom is not None else None,
                         "err_calibrated": (cal_v - hw) / hw if hw is not None and hw != 0 and cal_v is not None else None})
    cal["per_case"] = rows
    cal["aggregate_size"] = cal["rule"]["size"]

    def mare(role, col):
        vals = [abs(r[col]) for r in rows if r["role"] == role and r["case"].endswith(f"/{cal['rule']['size']}") and r[col] is not None]
        wanted = cal["rule"]["training_loads" if role == "treino" else "evaluation_loads"]
        return sum(vals) / len(vals) if vals and len(vals) == len(wanted) else None
    cal["aggregate"] = {f"{role}_{col}": mare(role, col) for role in ("treino", "avaliação")
                        for col in ("err_nominal", "err_calibrated")}
    return cal


def determinism(metrics: list[dict], checks: list[dict]) -> list[dict]:
    """Só considera repetibilidade com >=2 runs e cobertura de todos os runs
    válidos do firmware. A fração usa apenas observáveis elegíveis.
    """
    rows = []
    envs = {m["environment"] for m in metrics} | {c["environment"] for c in checks}
    for env in sorted(envs):
        vals, runs = defaultdict(dict), defaultdict(set)
        for kind, data, key, value in (("m", metrics, "metric", "value"),
                                       ("c", checks, "item", "observed")):
            for row in data:
                if row["environment"] != env:
                    continue
                runs[row["firmware"]].add(row["run"])
                ident = (kind, row["firmware"], row["case"], row[key])
                vals[ident].setdefault(row["run"], []).append(row[value])
        eligible = [v for k, v in vals.items() if len(v) >= 2 and set(v) == runs[k[1]]]
        constant = sum(len({tuple(vv) for vv in v.values()}) == 1 for v in eligible)
        rows.append({"environment": env, "observables": len(vals), "eligible": len(eligible),
                     "insufficient": len(vals) - len(eligible), "identical_in_all_runs": constant,
                     "fraction": constant / len(eligible) if eligible else None})
    return rows


def expected_case_labels(plan: dict) -> list[tuple[str, str]]:
    labels = []
    for fw, spec in plan["firmwares"].items():
        for cid in spec["planned_cases"]:
            if fw == "c1-functional":
                label = c1.CASES[cid]
            elif fw == "c1-timing":
                label = f"{c1.LOADS[cid >> 4]}/{0 if cid == 0 else c1.SIZES[cid & 15]}"
            else:
                label = {"c2": c2, "c3": c3, "c4": c4}[fw].label(cid)
            labels.append((fw, label))
    return labels


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
    cases = classify(checks, stats, "hw", "renode-nominal", fws, expected_case_labels(plan))
    analysis_problems = []
    try:
        instr_rows = c1_instruction_rows(root, stats)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        instr_rows = []
        analysis_problems.append(f"traço de instruções inválido: {exc}")
    if plan.get("instructions", {}).get("enabled"):
        for env in plan["environments"]:
            if not (root / "instr" / env / "instructions.json").exists():
                analysis_problems.append(f"traço de instruções solicitado ausente: {env}")
    resources = resource_map(cases, instr_rows)
    try:
        cal = calibration_summary(root, stats) if plan.get("calibration", {}).get("enabled") else None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        cal = None
        analysis_problems.append(f"calibração inválida: {exc}")
    det = determinism(metrics, checks)
    write_csv(out / "exclusions.csv", [{"environment": r.env, "firmware": r.firmware,
                                        "run": r.name, "status": r.record.get("status"),
                                        "problems": "; ".join(r.record.get("problems", []))}
                                       for r in runs if not r.valid])
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
        "acquisition_complete": bool(acc) and all(a["complete"] for a in acc),
        "complete": (bool(acc) and all(a["complete"] for a in acc) and not analysis_problems
                     and not traces["errors"] and bool(traces["validation"])
                     and all(v["ok"] for v in traces["validation"])),
        "analysis_problems": analysis_problems,
        "comparison_available": set(plan["environments"]) == {"hw", "renode"},
        "accounting": acc, "classes": Counter(c["class"] for c in cases),
        "figures": figs, "perfetto": traces,
    }
    report.write(out / "report.md", plan, summary, acc, cases, resources, stats, instr_rows,
                 cal, det, checks, root)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return summary
