"""Orquestração do C2 #oD: check (build do zero + gate), run (coleta) e analyze.

Uma campanha = um caso, um ELF congelado (SHA-256 conferido a cada
execução), três variantes de observação × N repetições, cada execução num
processo novo do Renode. Dados em data/c2/<caso>/<nome>/.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import analysis, catalog as K, collect, gate, report
from obs.elf import ROOT, elf_path, load

DATA = ROOT / "data" / "c2"
NEED = gate.NEED
# Tempo virtual por execução: folga sobre ~40 µs por ponto do C2-09 medidos no piloto.
RUN_FOR_BASE_S, RUN_FOR_PER_POINT_S = 0.0005, 0.0001


def build(fresh: bool = False) -> None:
    if fresh:
        shutil.rmtree(ROOT / "build" / collect.PRESET, ignore_errors=True)
    out = subprocess.run(["cmake", "--workflow", "--preset", collect.PRESET], cwd=ROOT,
                         capture_output=True, text=True)
    log = out.stdout + out.stderr
    if out.returncode != 0:
        sys.stderr.write(log)
        raise SystemExit(1)
    if "warning" in log.lower():
        sys.stderr.write(log)
        print("ERRO: o build gerou avisos (política: zero warnings)", file=sys.stderr)
        raise SystemExit(1)


def gate_or_die() -> None:
    fw = load(elf_path(collect.PRESET), NEED)
    bad = gate.check(fw)
    for b in bad:
        print(f"[c2] gate: {b}", file=sys.stderr)
    if bad:
        raise SystemExit(1)
    print(f"[c2] gate aprovado: {fw.path.relative_to(ROOT)} SHA-256 {fw.sha256[:16]}…")


def check() -> int:
    build(fresh=True)
    gate_or_die()
    return 0


def layout_of(fw) -> dict:
    h = fw.function_range("c2_irq_handler")
    stores = sorted(a for a in fw.disasm if fw.is_store(a))
    return {"point": f"0x{fw.symbols['c2_point']:08x}", "handler": [f"0x{h.start:08x}", f"0x{h.stop:08x}"],
            "stores": [f"0x{a:08x}" for a in stores]}


def layout_from(plan: dict) -> analysis.Layout:
    lay = plan["layout"]
    return analysis.Layout(int(lay["point"], 16), range(int(lay["handler"][0], 16), int(lay["handler"][1], 16)),
                           frozenset(int(a, 16) for a in lay["stores"]))


def run_dirs(root: Path, plan: dict):
    for v in plan["variants"]:
        for rep in range(plan["repetitions"]):
            yield v, rep, root / f"{v}-{rep}"


def run(case: str, name: str, reps: int, build_first: bool = True) -> int:
    if case not in K.CASE_POINTS:
        print(f"ERRO: caso {case} não implementado (disponíveis: {', '.join(K.CASE_POINTS)})", file=sys.stderr)
        return 1
    root = DATA / case / name
    if root.exists():
        print(f"ERRO: {root} já existe (nome de campanha é único)", file=sys.stderr)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    lock = (DATA / ".build.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERRO: outra execução do C2 está usando o build", file=sys.stderr)
        return 1
    if build_first:
        build()
    gate_or_die()
    fw = load(elf_path(collect.PRESET), NEED)
    points = K.CASE_POINTS[case]()
    run_for = RUN_FOR_BASE_S + RUN_FOR_PER_POINT_S * len(points)
    root.mkdir(parents=True)
    plan = {"case": case, "campaign": name, "oracle": "oD", "environment": "renode", "profile": "R1",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "revision": collect.revision(), "renode": collect.renode_version(),
            "platform": collect.PLATFORM, "mips": collect.MIPS, "quantum_s": collect.QUANTUM,
            "run_for_s": run_for, "preset": collect.PRESET, "elf": str(fw.path.relative_to(ROOT)),
            "elf_sha256": fw.sha256, "catalog_hash": K.catalog_hash(), "repetitions": reps,
            "variants": {v: {"observer": h, "trace": t} for v, (h, t) in collect.VARIANTS.items()},
            "points": [{"index": p.index, "line": p.line, "line_name": K.FREE_LINES[p.line],
                        "mech": p.mech, "label": p.label} for p in points],
            "params": {"c2_09_prio": K.C2_09_PRIO, "c2_09_window": K.C2_09_WINDOW},
            "layout": layout_of(fw)}
    (root / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    errors = {}
    for v, rep, d in run_dirs(root, plan):
        print(f"[c2] {case} {v} #{rep} …", flush=True)
        try:
            collect.run(d, fw, case, points, v, run_for)
        except collect.CollectError as exc:
            errors[f"{v}-{rep}"] = str(exc)
            print(f"[c2]   EVIDÊNCIA INVÁLIDA: {exc}", flush=True)
        if load(elf_path(collect.PRESET)).sha256 != fw.sha256:
            errors[f"{v}-{rep}"] = "ELF mudou durante a campanha"
    (root / "errors.json").write_text(json.dumps(errors, indent=1, ensure_ascii=False))
    return analyze_dir(root)


def analyze(case: str, name: str) -> int:
    root = DATA / case / name
    if not (root / "plan.json").is_file():
        print(f"ERRO: {root}/plan.json ausente", file=sys.stderr)
        return 1
    return analyze_dir(root)


def analyze_dir(root: Path) -> int:
    plan = json.loads((root / "plan.json").read_text())
    errors = json.loads((root / "errors.json").read_text()) if (root / "errors.json").is_file() else {}
    case = plan["case"]
    points = K.CASE_POINTS[case]()
    if [p.label for p in points] != [p["label"] for p in plan["points"]]:
        print("ERRO: o catálogo atual não corresponde aos pontos da campanha", file=sys.stderr)
        return 1
    variants = {v: (c["observer"], c["trace"]) for v, c in plan["variants"].items()}
    runs = [analysis.read_run(d, v, rep, errors.get(f"{v}-{rep}")) for v, rep, d in run_dirs(root, plan)]
    res = analysis.evaluate(case, runs, points, layout_from(plan), variants)
    out = root / "analysis"
    out.mkdir(exist_ok=True)
    results = {"case": case, "verdict": res.verdict, "why": res.why, "checks": res.checks,
               "hooks": res.hooks, "points": [p.as_dict() for p in res.points], "plan": plan}
    (out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    (out / "report.md").write_text(report.render(results))
    print(f"[c2] {case}: {res.verdict}")
    for w in res.why[:20]:
        print(f"[c2]   {w}")
    print(f"[c2] relatório: {out / 'report.md'}")
    return 3 if res.verdict == analysis.INVALIDA else 0
