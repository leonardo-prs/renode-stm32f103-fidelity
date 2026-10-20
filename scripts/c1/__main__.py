"""CLI do C1 (ver README).

    python -m c1 gen   --preset P --out DIR          (chamado pelo CMake)
    python -m c1 run   --env hw|renode|renode-doc --preset P [--batch B]
                                                     (um run de diagnóstico)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ENVS = ("hw", "renode", "renode-doc")


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build(preset: str, log: Path) -> None:
    from . import targets
    with log.open("w") as out:
        for argv in (["cmake", "--preset", preset], ["cmake", "--build", "--preset", preset]):
            r = targets.run_command(argv, stdout=out, stderr=out, timeout_s=300, check=False)
            if r.returncode:
                raise targets.TargetError(f"build de {preset} falhou (ver {log})")


def cmd_run(args) -> int:
    from . import abi, evaluate, gen, targets
    from .presets import PRESETS, ROOT
    preset = PRESETS[args.preset]
    out = args.out or ROOT / "data" / "c1" / "diagnostic" / f"{args.env}-{preset.name}-b{args.batch}-{utc()}"
    out.mkdir(parents=True, exist_ok=False)
    build(preset.name, out / "build.log")
    g = gen.generate(preset.name)
    host = targets.HostBlock(batch=args.batch, iters=args.iters,
                             flags=abi.HOST_TRACE if args.trace else 0)
    if args.env == "hw":
        with targets.Bench(out) as bench:
            print(json.dumps(bench.identify(preset.elf)))
            bench.flash(preset.elf, out / "flash.log")
            col = bench.run(preset.elf, out, host, args.timeout)
    else:
        try:
            col = targets.run_renode(preset.elf, out, host, args.timeout, profile=args.env)
        except targets.SimulatorAbort as exc:
            print(f"SIMULADOR ABORTOU: {exc}")
            print(f"dados: {out}")
            return 0
    snap = abi.decode(col.snapshot)
    if args.preset == 'c1-func':
        from . import disasm
        for p in disasm.gate(preset.name, preset.elf):
            print(f'  GATE: {p}')
    problems = abi.run_checks(snap, preset.preset_id, g.catalog_hash, host.nonce, host.batch)
    print(f"estado {snap.state} {snap.errors}; {len(snap.records)} registros, "
          f"{snap.header['word_count']} palavras; observer {snap.header['observer_ticks']}; "
          f"extra {col.extra}")
    for p in problems:
        print(f"  PROBLEMA: {p}")
    if preset.name == "c1-func" and args.batch < len(g.batches):
        from . import disasm
        syms = disasm.symbols(preset.elf)
        results, probs = evaluate.functional(snap, g.forms, g.batches[args.batch], syms, args.trace)
        for p in probs:
            print(f"  PROBLEMA: {p}")
        bad = [r for r in results if not r.ok]
        print(f"{len(results)} vetores, {len(bad)} diferentes do oráculo")
        forms = {f.name: f for f in g.forms}
        for r in bad[:args.show]:
            f = forms[r.form]
            diffs = [f"{name}: obs 0x{r.observed[k]:08x} esp {r.expected[k]}"
                     for k, name in enumerate(f.fields) if r.field_ok(k) is False]
            print(f"  ≠ {r.form}[{r.index}] in={[hex(x) for x in r.inputs]} " + "; ".join(diffs))
    print(f"dados: {out}")
    return 0 if not problems else 3


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="c1", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="gera os headers do catálogo para um preset")
    g.add_argument("--preset", required=True)
    g.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("run", help="um run de diagnóstico (fora de campanha)")
    r.add_argument("--env", choices=ENVS, required=True)
    r.add_argument("--preset", choices=("c1-func", "c1-layout", "c1-cycle"), required=True)
    r.add_argument("--batch", type=int, default=0)
    r.add_argument("--iters", type=int, default=1)
    r.add_argument("--trace", action="store_true", help="só o 1º vetor de cada forma")
    r.add_argument("--timeout", type=float, default=120)
    r.add_argument("--show", type=int, default=20)
    r.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    if args.cmd == "gen":
        from . import gen
        g = gen.write(args.preset, args.out)
        print(f"{args.preset}: catálogo 0x{g.catalog_hash:08x}, {len(g.forms)} formas, "
              f"{len(g.batches)} lotes")
        return 0
    if args.cmd == "run":
        return cmd_run(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
