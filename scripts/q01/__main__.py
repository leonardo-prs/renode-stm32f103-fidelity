"""CLI do Q-01.

  python -m q01 run --name piloto-01 [--reps 2] [--no-build]
  python -m q01 analyze --name piloto-01

Dados em data/q01/<nome>/ (gitignored): plan.json, <variante>-<rep>/ com os
arquivos brutos de cada execução, e analysis/{results.json,report.md}.
Saída: 0 = veredito emitido (IGUAL, DIVERGE ou NÃO DETERMINÍSTICO são
resultado, não erro); 3 = EVIDÊNCIA INVÁLIDA; 1 = erro de pré-condição/build.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import subprocess
import sys
from pathlib import Path

from . import analysis, collect, report

DATA = collect.ROOT / "data" / "q01"
PASSES = 3                                   # Q01_PASSES em src/q01/main.c


def build() -> None:
    subprocess.run(["cmake", "--workflow", "--preset", collect.PRESET], cwd=collect.ROOT, check=True,
                   stdout=subprocess.DEVNULL)


def run_dirs(root: Path, plan: dict):
    for v in plan["variants"]:
        for rep in range(plan["repetitions"]):
            yield v, rep, root / f"{v}-{rep}"


def cmd_run(args) -> int:
    root = DATA / args.name
    if root.exists():
        print(f"ERRO: {root} já existe (nome de campanha é único)", file=sys.stderr)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    lock = (DATA / ".build.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ERRO: outra execução do Q-01 está usando o build", file=sys.stderr)
        return 1
    if not args.no_build:
        build()
    fw = collect.load_firmware()
    root.mkdir(parents=True)
    plan = {"case": "Q-01", "campaign": args.name, "oracle": "oD", "environment": "renode",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "revision": collect.revision(), "renode": collect.renode_version(),
            "platform": collect.PLATFORM, "mips": collect.MIPS, "quantum_s": collect.QUANTUM,
            "run_for_s": collect.RUN_FOR, "elf": str(fw.elf.relative_to(collect.ROOT)),
            "elf_sha256": fw.sha256, "passes": PASSES, "repetitions": args.reps,
            "variants": {v: {"point_hooks": h, "trace": t} for v, (h, t) in collect.VARIANTS.items()},
            "points": {f"p{n}": f"0x{a:08x}" for n, a in fw.points}}
    (root / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    errors = {}
    for v, rep, d in run_dirs(root, plan):
        print(f"[q01] {v} #{rep} …", flush=True)
        try:
            collect.run(d, fw, v)
        except collect.CollectError as exc:
            errors[f"{v}-{rep}"] = str(exc)
            print(f"[q01]   EVIDÊNCIA INVÁLIDA: {exc}", flush=True)
        if collect.load_firmware().sha256 != fw.sha256:
            errors[f"{v}-{rep}"] = "ELF mudou durante a campanha"
    (root / "errors.json").write_text(json.dumps(errors, indent=1, ensure_ascii=False))
    return analyze(root)


def analyze(root: Path) -> int:
    plan = json.loads((root / "plan.json").read_text())
    errors = json.loads((root / "errors.json").read_text()) if (root / "errors.json").is_file() else {}
    points = sorted((int(k[1:]), int(a, 16)) for k, a in plan["points"].items())
    variants = {v: (c["point_hooks"], c["trace"]) for v, c in plan["variants"].items()}
    runs = [analysis.read_run(d, v, rep, errors.get(f"{v}-{rep}")) for v, rep, d in run_dirs(root, plan)]
    res = analysis.evaluate(runs, points, plan["passes"], variants)
    out = root / "analysis"
    out.mkdir(exist_ok=True)
    results = {"case": "Q-01", "verdict": res.verdict, "why": res.why, "checks": res.checks,
               "segments": [s.as_dict() for s in res.segments], "plan": plan}
    (out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    (out / "report.md").write_text(report.render(results))
    print(f"[q01] veredito: {res.verdict}")
    for w in res.why:
        print(f"[q01]   {w}")
    print(f"[q01] relatório: {out / 'report.md'}")
    return 3 if res.verdict == analysis.INVALIDA else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="q01", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="build + coleta no Renode + análise")
    r.add_argument("--name", required=True)
    r.add_argument("--reps", type=int, default=2, help="repetições por variante (determinismo)")
    r.add_argument("--no-build", action="store_true")
    a = sub.add_parser("analyze", help="refaz a análise a partir dos dados brutos")
    a.add_argument("--name", required=True)
    args = p.parse_args(argv)
    if args.cmd == "run":
        if args.reps < 2:
            p.error("--reps >= 2 (o determinismo é conferido entre repetições)")
        return cmd_run(args)
    return analyze(DATA / args.name)


if __name__ == "__main__":
    sys.exit(main())
