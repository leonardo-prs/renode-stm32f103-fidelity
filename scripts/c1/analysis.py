"""Análise de uma campanha do C1: vereditos, custos, repetições e traços.

Vereditos (material-base, @sec-vereditos), por caso e por métrica:

  IGUAL                   Renode = placa nos campos definidos (e a placa conforme)
  IGUAL COM CONFIGURAÇÃO  só o perfil renode-doc (correções documentadas) iguala
  DIVERGE                 Renode ≠ placa (inclui "simulação abortada")
  NÃO DETERMINÍSTICO      execuções repetidas deram resultados diferentes
  EVIDÊNCIA INVÁLIDA      faltam runs válidos, o teste de linearidade falhou...

e, em paralelo, a posição da PLACA diante da especificação: conforme,
PLACA ≠ ESPECIFICAÇÃO ou CONFLITO DOCUMENTAL (com a leitura que a placa
confirmou). Uma divergência nunca é contada quando o instrumento falhou.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from . import abi, disasm, evaluate, gen, timing
from .catalog import F_FAULT, F_TERMINAL, Alt
from .presets import PRESETS

IGUAL, CONFIG, DIVERGE = "IGUAL", "IGUAL COM CONFIGURAÇÃO", "DIVERGE"
NONDET, INVALID = "NÃO DETERMINÍSTICO", "EVIDÊNCIA INVÁLIDA"
CONFORME, PLACA_NE, CONFLITO = "conforme", "PLACA ≠ ESPECIFICAÇÃO", "CONFLITO DOCUMENTAL"
RENODES = ("renode", "renode-doc")


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def frac(x: Fraction | None) -> str | None:
    return None if x is None else str(x)


# ───────────────────────────── coleta dos runs ─────────────────────────────

def load_runs(root: Path, plan: dict, preset: str, batch: int, env: str) -> dict:
    """Runs do ELF congelado: {'valid': [Snapshot], 'aborts': [msg], 'attempts': n, 'invalid': [..]}."""
    base = root / env / preset / f"b{batch:02d}"
    elf_sha = plan["presets"][preset]["elf_sha256"]
    out = {"valid": [], "aborts": [], "attempts": 0, "invalid": []}
    for d in sorted(base.glob("run-*")):
        out["attempts"] += 1
        if not (d / "run.json").exists():
            continue
        rec = read_json(d / "run.json")
        if rec.get("elf_sha256") != elf_sha:
            continue
        if rec["status"] == "valid":
            out["valid"].append(abi.decode((d / "snapshot.bin").read_bytes()))
        elif rec["status"] == "simulator_abort":
            out["aborts"].append(rec["problems"][0])
        else:
            out["invalid"].append(f"{d.name}: {rec['status']}: {rec['problems'][:1]}")
    return out


def frozen_elf(root: Path, plan: dict, preset: str) -> Path:
    """O ELF que a campanha executou: a cópia congelada em <campanha>/build/
    ou, em campanhas antigas sem a cópia, build/<preset> se ainda for o
    mesmo (SHA-256 do plano). Símbolos e disassembly vêm sempre dele."""
    want = plan["presets"][preset]["elf_sha256"]
    for elf in (root / "build" / f"{preset}.elf", PRESETS[preset].elf):
        if elf.exists() and hashlib.sha256(elf.read_bytes()).hexdigest() == want:
            return elf
    raise ValueError(f"{preset}: nenhum ELF com o SHA-256 da campanha ({want[:12]}…); "
                     "a análise não pode resolver símbolos de outro build")


def envs_of(plan) -> list[str]:
    return [e for e in ("hw", "renode", "renode-doc") if e in plan["environments"]]


# ───────────────────────────── funcional (c1-func, c1-layout) ─────────────────────────────

def masked(value: int, exp) -> int:
    if isinstance(exp, tuple):
        return value & exp[1]
    if isinstance(exp, Alt):
        masks = {o[1] for o in exp.options if isinstance(o, tuple)}
        return value & (masks.pop() if len(masks) == 1 else 0xFFFF_FFFF)
    return value


def compare_set(vr: evaluate.VectorResult) -> list[int]:
    """Campos definidos e válidos; numa forma classe C (sem oráculo), todos."""
    ks = [k for k, e in enumerate(vr.expected) if e is not None]
    return ks or list(range(len(vr.observed)))


def functional(root: Path, plan: dict, preset: str, log) -> dict:
    g = gen.generate(preset)
    syms = disasm.symbols(frozen_elf(root, plan, preset))
    forms = g.forms
    envs = envs_of(plan)
    vectors: dict = {}          # (form, index) → {"vr": VectorResult (placa), env: [observed...]}
    status: dict = defaultdict(dict)     # form → env → problema (inválido/aborto)
    runs_summary = {}
    for b in plan["presets"][preset]["batches"]:
        batch = g.batches[b]
        for env in envs:
            r = load_runs(root, plan, preset, b, env)
            runs_summary[f"{env}/b{b:02d}"] = {"valid": len(r["valid"]), "aborts": len(r["aborts"]),
                                              "attempts": r["attempts"]}
            names = {forms[e.form].name for e in batch.entries}
            if r["aborts"] and not r["valid"]:
                for n in names:
                    status[n][env] = ("abort", r["aborts"][0])
                continue
            if not r["valid"]:
                for n in names:
                    status[n][env] = ("invalid", r["invalid"][:2] or ["nenhum run"])
                continue
            for snap in r["valid"]:
                results, probs = evaluate.functional(snap, forms, batch, syms)
                if probs:
                    for n in names:
                        status[n][env] = ("invalid", probs[:2])
                    break
                for vr in results:
                    slot = vectors.setdefault((vr.form, vr.index), {"vr": vr})
                    slot.setdefault(env, []).append(vr.observed)
                    if env == "hw":
                        slot["vr"] = vr
    by_form = {f.name: f for f in forms}
    planned = {forms[e.form].name for b in plan["presets"][preset]["batches"] for e in g.batches[b].entries}
    planned_cases = {by_form[n].case for n in planned}
    per_case: dict = defaultdict(list)
    for (name, idx), slot in sorted(vectors.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        per_case[by_form[name].case].append((name, idx, slot))
    cases = {}
    for case, items in per_case.items():
        cases[case] = judge_case(case, items, status, envs, by_form)
    from .func import DERIVED as FDER
    derived = FDER if preset == "c1-func" else {}
    for case, spec in derived.items():
        if not set(spec["cases"]) <= planned_cases:
            continue
        items = [it for c in spec["cases"] for it in per_case.get(c, [])]
        cases[case] = judge_case(case, items, status, envs, by_form, spec)
    # Formas planejadas sem dados (todos os lotes abortados ou inválidos).
    for n in sorted(planned):
        f = by_form[n]
        if f.case not in cases:
            cases[f.case] = judge_case(f.case, [], status, envs, by_form,
                                       forms_of_case=[x for x in planned if by_form[x].case == f.case])
    not_planned = sorted({f.case for f in forms} - planned_cases - set(derived), key=case_key)
    return {"cases": dict(sorted(cases.items(), key=lambda kv: case_key(kv[0]))),
            "runs": runs_summary, "vectors": sum(len(v) for v in per_case.values()),
            "not_planned": not_planned}


def case_key(case: str):
    head, _, num = case.rpartition("-")
    return (head, int(num) if num.isdigit() else 0, case)


def judge_case(case, items, status, envs, by_form, derived=None, forms_of_case=None) -> dict:
    names = sorted({n for n, _, _ in items} | set(forms_of_case or []))
    if derived and not names:
        names = sorted(n for n, f in by_form.items() if f.case in derived["cases"])
    meta = by_form[names[0]] if names else None
    out = {"case": case, "forms": len(names), "vectors": len(items),
           "klass": meta.klass if meta else "?", "level": meta.level if meta else "?",
           "source": (derived or {}).get("source") or (meta.source if meta else ""),
           "note": (derived or {}).get("note") or (meta.note if meta else ""),
           "derived_from": list(derived["cases"]) if derived else None}
    problems = {env: [status[n][env] for n in names if env in status[n]] for env in envs}
    hw_problem = problems.get("hw")
    if "hw" not in envs or hw_problem or not items:
        out.update(verdict=INVALID, board=None,
                   why=f"sem dados válidos da placa: {hw_problem[:1] if hw_problem else 'nenhum vetor'}")
        return out
    nondet = [env for env in envs if any(env in s and len(set(s[env])) > 1 for _, _, s in items)]
    out["nondeterministic"] = nondet
    # Placa × especificação.
    dmask = (derived or {}).get("mask")

    def board_ok(vr, k) -> bool | None:
        if dmask and vr.expected[k] is not None and not isinstance(vr.expected[k], Alt):
            e = vr.expected[k]
            value = e[0] if isinstance(e, tuple) else e
            return (vr.observed[k] & dmask) == (value & dmask)
        return vr.field_ok(k)

    def same(a: int, b: int, exp) -> bool:
        if dmask:
            return (a & dmask) == (b & dmask)
        return masked(a, exp) == masked(b, exp)

    board_bad, conflict_labels, examples = 0, set(), []
    for name, idx, s in items:
        vr = s["vr"]
        ks = sel_fields(vr, by_form[name], derived)
        for k in ks:
            if board_ok(vr, k) is False:
                board_bad += 1
                if len(examples) < 3:
                    examples.append({"vector": f"{name}[{idx}]", "field": by_form[name].fields[k],
                                     "board": hexs(vr.observed[k]), "expected": show(vr.expected[k])})
                break
            lab = vr.alt_label(k)
            if lab:
                conflict_labels.add(lab)
    if conflict_labels:
        out["board"] = f"{CONFLITO} (a placa confirma: {'; '.join(sorted(conflict_labels))})"
    elif board_bad:
        out["board"] = f"{PLACA_NE} ({board_bad} vetores)"
        out["board_examples"] = examples
    elif all(all(e is None for e in s["vr"].expected) for _, _, s in items):
        out["board"] = "classe C: a placa é o oráculo"
    else:
        out["board"] = CONFORME
    # Renode × placa (e × especificação), por perfil.
    out["renode"] = {}
    for env in RENODES:
        if env not in envs:
            continue
        if problems.get(env):
            kind, msg = problems[env][0]
            out["renode"][env] = {"result": DIVERGE if kind == "abort" else INVALID,
                                  "why": msg if kind == "abort" else f"sem dados válidos: {msg}"}
            continue
        bad, fields, ex, spec_bad = 0, set(), [], 0
        for name, idx, s in items:
            vr, obs = s["vr"], s[env][0]
            ks = sel_fields(vr, by_form[name], derived)
            diff = [k for k in ks if not same(obs[k], vr.observed[k], vr.expected[k])]
            alt = evaluate.VectorResult(name, idx, vr.inputs, obs, vr.expected)
            spec_bad += any(board_ok(alt, k) is False for k in ks)
            if diff:
                bad += 1
                fields |= {by_form[name].fields[k] for k in diff}
                if len(ex) < 4:
                    ex.append({"vector": f"{name}[{idx}]",
                               "inputs": [hexs(x) for x in vr.inputs],
                               "fields": {by_form[name].fields[k]: {"placa": hexs(vr.observed[k]),
                                                                    "renode": hexs(obs[k])} for k in diff}})
        out["renode"][env] = {"result": IGUAL if bad == 0 else DIVERGE, "vectors_diverging": bad,
                              "fields": sorted(fields), "examples": ex, "spec_mismatch": spec_bad}
    out["verdict"] = combine(out, nondet)
    return out


def sel_fields(vr, form, derived) -> list[int]:
    ks = compare_set(vr)
    if derived and derived.get("field"):
        ks = [k for k in ks if form.fields[k] == derived["field"]]
        if derived.get("where") and not derived["where"](vr.inputs):
            return []
    return ks


def combine(out: dict, nondet) -> str:
    if nondet:
        return NONDET
    r = out["renode"]
    base = r.get("renode", {}).get("result")
    doc = r.get("renode-doc", {}).get("result")
    if "renode" not in r:               # campanha sem o perfil base
        if doc in (None, INVALID):
            return INVALID
        return CONFIG if doc == IGUAL else doc
    if base == IGUAL:
        return IGUAL
    if base == DIVERGE and doc == IGUAL:
        return CONFIG
    if base == INVALID and doc in (None, INVALID):
        return INVALID
    return DIVERGE if base in (DIVERGE, None) or doc == DIVERGE else (base or INVALID)


def hexs(v) -> str:
    return f"0x{v:08x}" if isinstance(v, int) else str(v)


def show(e) -> str:
    if isinstance(e, Alt):
        return " | ".join(show(o) for o in e.options)
    if isinstance(e, tuple):
        return f"{hexs(e[0])} & {hexs(e[1])}"
    return hexs(e)


# ───────────────────────────── temporal (c1-cycle) ─────────────────────────────

def cycle(root: Path, plan: dict, log) -> dict:
    g = gen.generate("c1-cycle")
    variants = g.forms
    envs = envs_of(plan)
    iters = plan["cycle_iters"]
    runs: dict = defaultdict(dict)       # variante → env → [VariantRun]
    problems: dict = defaultdict(dict)
    for b in plan["presets"]["c1-cycle"]["batches"]:
        batch = g.batches[b]
        for env in envs:
            r = load_runs(root, plan, "c1-cycle", b, env)
            names = [variants[i].name for i in batch.variants]
            if not r["valid"]:
                for n in names:
                    problems[n][env] = r["aborts"][:1] or r["invalid"][:1] or ["nenhum run"]
                continue
            for snap in r["valid"]:
                vruns, probs = timing.parse(snap, variants, batch, iters)
                if probs:
                    for n in names:
                        problems[n][env] = probs[:1]
                    break
                for vrun in vruns:
                    runs[vrun.name].setdefault(env, []).append(vrun)
    planned = {variants[i].name for b in plan["presets"]["c1-cycle"]["batches"] for i in g.batches[b].variants}
    out = {}
    for v in variants:
        if v.name in planned:
            out[v.name] = judge_variant(v, runs.get(v.name, {}), problems.get(v.name, {}), envs)
    dwt_checks(out, runs, variants)
    profile_flags(out)
    return {"variants": out, "iters": iters,
            "not_planned": sorted({v.case for v in variants if v.name not in planned})}


def env_stats(v, vruns: list) -> dict:
    fits = [r.fits(v.sizes) for r in vruns]
    cold = [f[0] for f in fits]
    warm = [x for f in fits for x in f[1:]]
    linear = all(x.linear for f in fits for x in f)
    cs_cold = sorted({x.c for x in cold}, key=lambda c: (c is None, c or 0))
    cs_warm = sorted({x.c for x in warm}, key=lambda c: (c is None, c or 0))
    ds_cold = {x.deltas for x in cold}
    ds_warm = {x.deltas for x in warm}
    return {"runs": len(vruns), "linear": linear,
            "deterministic": len(ds_cold) <= 1 and len(ds_warm) <= 1,
            "c_cold": cs_cold[0] if len(cs_cold) == 1 else None,
            "c_warm": cs_warm[0] if len(cs_warm) == 1 else (None if not warm else None),
            "c_values": sorted({str(c) for c in cs_cold + cs_warm}),
            "o_warm": warm[0].o if warm else cold[0].o,
            "deltas_cold": sorted(ds_cold)[0] if ds_cold else None,
            "deltas_warm": sorted(ds_warm)[0] if ds_warm else None,
            "cold_eq_warm": (not warm) or (ds_cold == ds_warm),
            "profile": vruns[0].profile, "raw": vruns[0].raw}


def judge_variant(v, by_env: dict, probs: dict, envs) -> dict:
    out = {"variant": v.name, "case": v.case, "unit": v.unit, "obj": v.obj, "level": v.level,
           "trm": str(v.trm), "trm_text": v.trm.text, "renode_h_t1": str(v.renode), "source": v.source,
           "note": v.note, "sizes": v.sizes}
    stats = {}
    for env in envs:
        if env in probs or env not in by_env:
            stats[env] = {"problem": (probs.get(env) or ["sem dados"])[0]}
        else:
            stats[env] = env_stats(v, by_env[env])
    out["env"] = {e: {k: (frac(x) if isinstance(x, Fraction) else x) for k, x in s.items()}
                  for e, s in stats.items()}
    hw, rn = stats.get("hw", {}), stats.get("renode", {})
    if "problem" in hw or "problem" in rn or not hw or not rn:
        out["verdict"] = INVALID
        out["why"] = hw.get("problem") or rn.get("problem") or "sem dados"
        return out
    if not hw["deterministic"] or not rn["deterministic"]:
        out["verdict"] = NONDET
        return out
    if not hw["linear"] or not rn["linear"]:
        out["verdict"] = INVALID
        out["why"] = ("teste de linearidade falhou na " +
                      " e no ".join(n for n, s in (("placa", hw), ("Renode", rn)) if not s["linear"])
                      + ": c não é publicado; Δ brutos no registro")
        return out
    c_hw, c_rn = hw["c_warm"], rn["c_warm"]
    if v.sizes == (0, 0, 0):
        c_hw, c_rn = hw["o_warm"], rn["o_warm"]
    out["c_hw"], out["c_renode"] = frac(c_hw), frac(c_rn)
    out["delta"] = frac(c_hw - c_rn) if c_hw is not None and c_rn is not None else None
    out["ratio"] = (float(c_hw / c_rn) if c_rn else None) if c_hw is not None else None
    out["verdict"] = IGUAL if c_hw == c_rn else DIVERGE
    inside = v.trm.contains(c_hw) if v.sizes != (0, 0, 0) else v.trm.contains(c_hw)
    out["board_vs_trm"] = ("sem previsão (caracterização)" if inside is None else
                           ("a placa decidiu (TRM ambíguo)" if v.trm.ambiguous and inside else
                            ("dentro" if inside else "FORA")))
    out["renode_vs_h_t1"] = "confirma" if c_rn == v.renode else "REFUTA"
    out["cold_eq_warm"] = {"hw": hw["cold_eq_warm"], "renode": rn["cold_eq_warm"]}
    doc = stats.get("renode-doc")
    if doc and "problem" not in doc:
        out["renode_doc_same"] = doc["c_warm"] == rn["c_warm"] and doc["o_warm"] == rn["o_warm"]
    return out


PROFILE_COUNTERS = ("cpicnt", "exccnt", "sleepcnt", "lsucnt", "foldcnt")


def profile_flags(out: dict) -> None:
    """Contadores de perfil (8 bits): desconta a linha de base do bloco vazio
    (T-DWT-03) e sinaliza "possível volta" acima de 200 eventos."""
    base = out.get("T-DWT-03", {}).get("env", {}).get("hw", {}).get("profile")
    if not base:
        return
    for name, v in out.items():
        prof = v.get("env", {}).get("hw", {}).get("profile")
        if not prof:
            continue
        net = {k: (prof[k] - base[k]) % 256 for k in PROFILE_COUNTERS}
        v["profile_net"] = net
        over = [k for k, n in net.items() if n > 200]
        if over:
            v["profile_overflow"] = over


def dwt_checks(out: dict, runs: dict, variants) -> None:
    """Verificações próprias de T-DWT (validade da régua)."""
    for env in ("hw", "renode"):
        checks = {}
        off = runs.get("T-DWT-01.off", {}).get(env, [])
        checks["T-DWT-01 (CYCCNTENA = 0 → Δ = 0)"] = bool(off) and all(
            d == 0 for r in off for blk in r.deltas for d in blk)
        on = runs.get("T-DWT-01.on", {}).get(env, [])
        checks["T-DWT-01 (CYCCNTENA = 1 → Δ > 0)"] = bool(on) and all(
            d > 0 for r in on for blk in r.deltas for d in blk)
        wrap = runs.get("T-DWT-02", {}).get(env, [])
        ref = runs.get("T-DWT-04", {}).get(env, [])
        # CYCCNT ← 0xFFFFFFF0 antes de t0: o bloco 3K (24 ADDS) cruza 2^32.
        checks["T-DWT-02 (o bloco 3K deu a volta: t1 < t0)"] = bool(wrap) and all(
            t1 < t0 for r in wrap for (t0, t1) in r.raw[2])
        if wrap and ref:
            checks["T-DWT-02 (Δ com volta = Δ sem volta)"] = all(
                wrap[0].deltas[k][-1] == ref[0].deltas[k][-1] for k in range(3))
        lin = out.get("T-DWT-04", {})
        empty = out.get("T-DWT-03", {})
        e_lin, e_empty = lin.get("env", {}).get(env, {}), empty.get("env", {}).get(env, {})
        if "o_warm" in e_lin and "o_warm" in e_empty:
            # Se falhar, as bordas da janela dependem do conteúdo; c (diferencial) não
            # depende de O — o relatório explica a causa (sobreposição de cargas).
            checks["T-DWT-05 (Δ(0) = O extrapolado de T-DWT-04)"] = e_lin["o_warm"] == e_empty["o_warm"]
            checks["_O"] = {"delta0": e_empty["o_warm"], "O_T-DWT-04": e_lin["o_warm"]}
            checks["T-DWT-04 (c = 1 e linear)"] = e_lin.get("c_warm") == "1" and e_lin.get("linear")
        out.setdefault("_dwt", {})[env] = checks


# ───────────────────────────── repetições (Kalibera & Jones) ─────────────────────────────

def kalibera(root: Path, plan: dict, cyc: dict, log) -> dict:
    """S², T² por nível com Y_ji = (Δ_ji(3K) − Δ_ji(K)) / 2K nas iterações QUENTES."""
    g = gen.generate("c1-cycle")
    out, decisions = {}, []
    by_name = {v.name: v for v in g.forms}
    for b in plan["presets"]["c1-cycle"]["batches"]:
        batch = g.batches[b]
        for env in envs_of(plan):
            r = load_runs(root, plan, "c1-cycle", b, env)
            per_var = defaultdict(list)
            for snap in r["valid"]:
                vruns, probs = timing.parse(snap, g.forms, batch, plan["cycle_iters"])
                if probs:
                    continue
                for vr in vruns:
                    v = by_name[vr.name]
                    s1, s3 = v.sizes[0], v.sizes[2]
                    if s3 == s1:
                        ys = [float(vr.deltas[0][i]) for i in range(1, len(vr.deltas[0]))]
                    else:
                        ys = [(vr.deltas[2][i] - vr.deltas[0][i]) / (s3 - s1)
                              for i in range(1, len(vr.deltas[0]))]
                    per_var[vr.name].append(ys)
            for name, Y in per_var.items():
                st = variance_levels(Y)
                if st is None:
                    continue
                out.setdefault(name, {})[env] = st
                decisions.append(st["rule"])
    rule = max(decisions) if decisions else 1
    if rule == 1:
        decision = {"rule": 1, "iters": 1, "executions": 5,
                    "why": "todas as medidas do piloto idênticas (T1² = T2² = 0)"}
    elif rule == 2:
        decision = {"rule": 2, "iters": 30, "executions": 5,
                    "why": "variação só entre iterações (T2² ≤ 0 < T1²)"}
    else:
        r1 = max((st["r1_opt"] for e in out.values() for st in e.values() if st.get("r1_opt")),
                 default=30)
        decision = {"rule": 3, "iters": min(30, r1), "executions": 30,
                    "why": "variação entre execuções (T2² > 0): r1 ótimo e 30 execuções"}
    return {"per_variant": out, "campaign_decision": decision,
            "levels": "Y_ji = estimativa de c na iteração quente i da execução j"}


def variance_levels(Y: list[list[float]]) -> dict | None:
    r2 = len(Y)
    if r2 < 2 or any(len(y) < 2 for y in Y):
        return None
    r1 = min(len(y) for y in Y)
    Y = [y[:r1] for y in Y]
    means = [sum(y) / r1 for y in Y]
    grand = sum(means) / r2
    s1 = sum(sum((x - m) ** 2 for x in y) / (r1 - 1) for y, m in zip(Y, means)) / r2
    s2 = sum((m - grand) ** 2 for m in means) / (r2 - 1)
    t1, t2 = s1, s2 - s1 / r1
    if s1 == 0 and s2 == 0:
        rule = 1
    elif t2 <= 0:
        rule = 2
    else:
        rule = 3
    st = {"r1": r1, "r2": r2, "S1^2": s1, "S2^2": s2, "T1^2": t1, "T2^2": t2, "mean": grand,
          "rule": rule}
    if rule == 3 and t1 > 0:
        # c2/c1: custo de uma execução / custo de uma iteração (host): ~3 s / ~1 ms.
        st["r1_opt"] = math.ceil(math.sqrt(3000 * t1 / t2))
    return st


# ───────────────────────────── nível de instrução ─────────────────────────────

def traces(root: Path, plan: dict, cyc: dict | None) -> dict:
    out = {}
    if not plan["trace"]["enabled"]:
        return out
    for preset in ("c1-func", "c1-cycle"):
        g = gen.generate(preset)
        elf = frozen_elf(root, plan, preset)
        dis = disasm.disassemble(elf)
        addrs = sorted(dis)
        syms = disasm.symbols(elf)
        rows = []
        for b in plan["presets"][preset]["batches"]:
            batch = g.batches[b]
            names = ([g.forms[e.form].name for e in batch.entries] if preset == "c1-func"
                     else [g.forms[i].name for i in batch.variants])
            data = {}
            for env in envs_of(plan):
                p = root / "trace" / env / preset / f"b{b:02d}" / "trace.json"
                data[env] = read_json(p)["calls"] if p.exists() else None
            for k, name in enumerate(names):
                row = {"name": name}
                for env, calls in data.items():
                    row[env] = None if calls is None or k >= len(calls) else calls[k]["count"]
                hw, rn = data.get("hw"), data.get("renode")
                if hw and rn and k < len(hw) and k < len(rn):
                    row["same_path"] = hw[k]["sha256"] == rn[k]["sha256"]
                if preset == "c1-cycle":
                    # Cada ambiente com o seu traço: o caminho dinâmico pode diferir.
                    for env, calls in data.items():
                        if calls and k < len(calls):
                            row[f"window_{env}"] = window_count(g.forms[batch.variants[k]],
                                                                calls[k]["pcs"], syms, dis, addrs)
                if preset == "c1-func":
                    st = static_count(g.forms[batch.entries[k].form], syms, dis, addrs)
                    if st is not None:
                        row["static"] = st
                        for env in data:
                            if row.get(env) is not None:
                                row[f"static_ok_{env}"] = row[env] == st
                rows.append(row)
        out[preset] = rows
    if cyc and "c1-cycle" in out:
        h_t1(out["c1-cycle"], cyc)
    return out


BRANCHY = ("b", "bl", "blx", "bx", "cbz", "cbnz", "tbb", "tbh", "svc", "udf", "it", "itt", "ite",
           "ittt", "itte", "itet", "itee", "itttt", "iteee")


def after(addrs: list[int], start: int) -> list[int]:
    return addrs[bisect.bisect_left(addrs, start):]


def static_count(form, syms, dis, addrs) -> int | None:
    """Contagem estática de uma rotina em linha reta: o BLX de c1_call mais as
    instruções da rotina até o retorno. None se houver desvio, IT, SVC,
    instrução crua ou se a forma provocar falta (o caminho não é estático)."""
    if form.flags & (F_FAULT | F_TERMINAL):
        return None
    start = syms.get(form.routine)
    if start is None:
        return None
    n = 0
    for addr in after(addrs, start & ~1):
        d = dis[addr]
        mnem = d.mnemonic.split(".")[0]
        n += 1
        if (mnem == "pop" and "pc" in d.operands) or (mnem == "ldmia" and "pc" in d.operands) \
                or (mnem == "bx" and d.operands == "lr"):
            return 1 + n
        base = mnem[:-2] if len(mnem) > 3 and mnem[-2:] in {
            "eq", "ne", "cs", "cc", "mi", "pl", "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le"} else mnem
        if base in BRANCHY or mnem in BRANCHY or mnem.startswith(("b", ".")) and mnem not in (
                "bic", "bics", "bfi", "bfc"):
            return None
        if n > 200:
            return None
    return None


def window_count(v, pcs: list[str], syms, dis, addrs) -> int | None:
    """Instruções executadas entre a 1ª unidade (t0 já lido) e a leitura de t1."""
    block = v.blocks[0]
    x0 = syms.get(f"{block}_x0")
    if x0 is None:
        return None
    t1 = None
    for addr in after(addrs, x0 & ~1):
        d = dis[addr]
        if d.mnemonic == "ldr" and d.operands.startswith("r5, [r6"):
            t1 = addr
            break
    seq = [int(p, 16) for p in pcs]
    try:
        i0 = seq.index(x0 & ~1)
        i1 = seq.index(t1, i0)
    except (ValueError, TypeError):
        return None
    return i1 - i0


def h_t1(rows: list[dict], cyc: dict) -> None:
    """H-T1 exata: no Renode, Δ(K) − Δ(0) = instruções executadas na janela (stepi)."""
    variants = cyc["variants"]
    d0 = {env: variants.get("T-DWT-03", {}).get("env", {}).get(env, {}).get("deltas_cold")
          for env in ("hw", "renode")}
    from .cycle import V_CYCOFF, VARIANTS
    off = {x.name for x in VARIANTS if x.flags & V_CYCOFF}
    for row in rows:
        v = variants.get(row["name"], {})
        if row["name"] in off:                 # contador desligado de propósito
            continue
        for env, key in (("renode", "h_t1_exact"), ("hw", "hw_cpi")):
            e = v.get("env", {}).get(env, {})
            w = row.get(f"window_{env}")
            if w is not None and e.get("deltas_cold") and d0.get(env) and (w or env == "renode"):
                dk = e["deltas_cold"][0] - d0[env][0]
                row[key] = (dk == w) if env == "renode" else str(Fraction(dk, w))


# ───────────────────────────── entrada ─────────────────────────────

def check_catalogs(plan: dict) -> None:
    """A análise reconstrói vetores e variantes a partir do catálogo ATUAL; ele
    tem de ser o mesmo com que os ELFs da campanha foram gerados."""
    bad = []
    for preset, info in plan["presets"].items():
        h = f"0x{gen.generate(preset).catalog_hash:08x}"
        if h != info["catalog_hash"]:
            bad.append(f"{preset}: campanha {info['catalog_hash']}, fontes atuais {h}")
    if bad:
        raise ValueError("o catálogo das fontes não é o da campanha (analise na revisão "
                         f"{plan.get('revision')}): " + "; ".join(bad))


def analyze(root: Path, log=print) -> dict:
    from . import report
    plan = read_json(root / "plan.json")
    check_catalogs(plan)
    out_dir = root / "analysis"
    out_dir.mkdir(exist_ok=True)
    func = functional(root, plan, "c1-func", log)
    lay = functional(root, plan, "c1-layout", log)
    cyc = cycle(root, plan, log)
    kal = kalibera(root, plan, cyc, log)
    trc = traces(root, plan, cyc)
    results = {"plan": {k: plan[k] for k in ("campaign", "mode", "board", "identity", "environments",
                                             "repetitions", "cycle_iters", "kalibera", "renode",
                                             "revision", "tools", "created_utc")},
               "presets": {p: {k: plan["presets"][p][k] for k in ("elf_sha256", "catalog_hash", "batches")}
                           for p in plan["presets"]},
               "functional": func, "layout": lay, "cycle": cyc, "trace": trc}
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))
    (out_dir / "kalibera.json").write_text(json.dumps(kal, indent=1, ensure_ascii=False))
    complete = all(c["verdict"] != INVALID or c.get("why", "").startswith("teste de linearidade")
                   for part in (func["cases"], lay["cases"]) for c in part.values()) and \
        all(v.get("verdict") != INVALID or "linearidade" in v.get("why", "")
            for k, v in cyc["variants"].items() if not k.startswith("_"))
    report.write(out_dir, results, kal, plan)
    log(f"análise gravada em {out_dir}")
    return {"complete": complete}
