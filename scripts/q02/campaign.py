"""Orquestração do Q-02: check (build do zero + gate), run (coleta) e analyze.

Uma campanha = um ELF congelado (SHA-256 conferido a cada execução), três
variantes de observação × N repetições, cada execução num processo novo do
Renode. Dados em data/q02/<nome>/.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import shutil
import subprocess
import sys
from pathlib import Path

from obs.elf import ROOT, Elf, elf_path, load
from obs.renode import CollectError, renode_version, revision

from . import analysis, collect, gate, report, spec

DATA = ROOT / "data" / "q02"


def build(fresh: bool = False) -> None:
    if fresh:
        shutil.rmtree(ROOT / "build" / collect.PRESET, ignore_errors=True)
    out = subprocess.run(["cmake", "--workflow", "--preset", collect.PRESET], cwd=ROOT,
                         capture_output=True, text=True)
    log = out.stdout + out.stderr
    if out.returncode != 0 or "warning" in log.lower():
        sys.stderr.write(log)
        if out.returncode == 0:
            print("ERRO: o build gerou avisos (política: zero warnings)", file=sys.stderr)
        raise SystemExit(1)


def gate_or_die() -> Elf:
    fw = load(elf_path(collect.PRESET), gate.NEED)
    bad = gate.check(fw)
    for b in bad:
        print(f"[q02] gate: {b}", file=sys.stderr)
    if bad:
        raise SystemExit(1)
    print(f"[q02] gate aprovado: {fw.path.relative_to(ROOT)} SHA-256 {fw.sha256[:16]}…")
    return fw


def check() -> int:
    build(fresh=True)
    gate_or_die()
    return 0


def layout_of(fw: Elf) -> dict:
    s = fw.symbols
    rng = lambda n: [f"0x{fw.function_range(n).start:08x}", f"0x{fw.function_range(n).stop:08x}"]  # noqa: E731
    store = next(i.addr for i in fw.function_insns("q02_store") if i.mnemonic == "str")
    returns = sorted(i.addr for i in fw.disasm.values()
                     if (i.mnemonic == "bx" and i.operands == "lr")
                     or (i.mnemonic.startswith("pop") and "pc" in i.operands))
    return {"point": f"0x{s['q02_point']:08x}", "store": f"0x{store:08x}", "trigger": f"0x{s['q02_trigger']:08x}",
            "handlers": {str(spec.EXC_PENDSV): rng("PendSV_Handler"), str(spec.EXC_SYSTICK): rng("SysTick_Handler")},
            "reset": rng("Reset_Handler"),
            "wait_loads": [f"0x{a:08x}" for a in fw.function_range("q02_wait") if fw.is_load(a)],
            "returns": [f"0x{a:08x}" for a in returns], "sink": f"0x{s['q02_sink']:08x}",
            "stores": [f"0x{a:08x}" for a in sorted(a for a in fw.disasm if fw.is_store(a))]}


def layout_from(plan: dict) -> analysis.Layout:
    L = plan["layout"]
    h = lambda x: int(x, 16)        # noqa: E731
    return analysis.Layout(h(L["point"]), h(L["store"]), h(L["trigger"]),
                           {int(k): range(h(a), h(b)) for k, (a, b) in L["handlers"].items()},
                           range(h(L["reset"][0]), h(L["reset"][1])),
                           frozenset(map(h, L["wait_loads"])), frozenset(map(h, L["returns"])),
                           h(L["sink"]), frozenset(map(h, L["stores"])))


def run_dirs(root: Path, plan: dict):
    for v in plan["variants"]:
        for rep in range(plan["repetitions"]):
            yield v, rep, root / f"{v}-{rep}"


def run(name: str, reps: int, build_first: bool = True) -> int:
    root = DATA / name
    if root.exists():
        print(f"ERRO: {root} já existe (nome de campanha é único)", file=sys.stderr)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    lock = (DATA / ".build.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERRO: outra execução do Q-02 está usando o build", file=sys.stderr)
        return 1
    if build_first:
        build()
    fw = gate_or_die()
    root.mkdir(parents=True)
    plan = {"case": "Q-02", "campaign": name, "environment": "renode", "profile": "R1",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "revision": revision(), "renode": renode_version(), "platform": collect.PLATFORM,
            "mips": collect.MIPS, "quantum_s": collect.QUANTUM, "preset": collect.PRESET,
            "elf": str(fw.path.relative_to(ROOT)), "elf_sha256": fw.sha256, "spec_hash": spec.spec_hash(),
            "repetitions": reps, "pauses_ns": list(spec.PAUSES_NS), "run_ns": spec.RUN_NS,
            "variants": {v: {"observer": h, "trace": t} for v, (h, t) in collect.VARIANTS.items()},
            "watched": [f"0x{a:08x}" for a in collect.watched(fw)], "layout": layout_of(fw)}
    (root / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    errors = {}
    for v, rep, d in run_dirs(root, plan):
        print(f"[q02] {v} #{rep} …", flush=True)
        try:
            collect.run(d, fw, v)
        except CollectError as exc:
            errors[f"{v}-{rep}"] = str(exc)
            print(f"[q02]   EVIDÊNCIA INVÁLIDA: {exc}", flush=True)
        if load(elf_path(collect.PRESET)).sha256 != fw.sha256:
            errors[f"{v}-{rep}"] = "ELF mudou durante a campanha"
    (root / "errors.json").write_text(json.dumps(errors, indent=1, ensure_ascii=False))
    return analyze_dir(root)


def analyze(name: str) -> int:
    root = DATA / name
    if not (root / "plan.json").is_file():
        print(f"ERRO: {root}/plan.json ausente", file=sys.stderr)
        return 1
    return analyze_dir(root)


def analyze_dir(root: Path) -> int:
    plan = json.loads((root / "plan.json").read_text())
    if plan["spec_hash"] != spec.spec_hash():
        print("ERRO: a especificação atual não corresponde à da campanha", file=sys.stderr)
        return 1
    errors = json.loads((root / "errors.json").read_text()) if (root / "errors.json").is_file() else {}
    variants = {v: (c["observer"], c["trace"]) for v, c in plan["variants"].items()}
    runs = [analysis.read_run(d, v, rep, errors.get(f"{v}-{rep}")) for v, rep, d in run_dirs(root, plan)]
    res = analysis.evaluate(runs, layout_from(plan), variants)
    out = root / "analysis"
    out.mkdir(exist_ok=True)
    results = {"case": "Q-02", "verdict": res.verdict, "why": res.why, "checks": res.checks,
               "criteria": [c.as_dict() for c in res.criteria], "hooks": res.hooks, "plan": plan}
    (out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    (out / "report.md").write_text(report.render(results))
    print(f"[q02] Q-02: {res.verdict}")
    for w in res.why[:20]:
        print(f"[q02]   {w}")
    print(f"[q02] relatório: {out / 'report.md'}")
    return 3 if res.verdict == analysis.INVALIDA else 0
