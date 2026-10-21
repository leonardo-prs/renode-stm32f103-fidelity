"""CLI do C1 (ver README).

    python -m c1 campaign --name N --mode pilot|final --board B [...]
    python -m c1 analyze  --name N                   (refaz a análise)
    python -m c1 run      --env hw|renode|renode-doc --preset P [--batch B]
    python -m c1 trace    --env E --preset P [--batch B]     (diagnóstico)
    python -m c1 check                               (build do zero + gate)
    python -m c1 gen      --preset P --out DIR       (chamado pelo CMake)
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
                             flags=abi.HOST_TRACE if args.trace else 0,
                             reboot=preset.name == "c1-layout" and args.batch == 1)
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
    if args.preset in ('c1-func', 'c1-cycle'):
        from . import disasm
        for p in disasm.gate(preset.name, preset.elf):
            print(f'  GATE: {p}')
    problems = abi.run_checks(snap, preset.preset_id, g.catalog_hash, host.nonce, host.batch)
    if args.env == "hw":
        problems += abi.clock_checks(snap)
    print(f"estado {snap.state} {snap.errors}; {len(snap.records)} registros, "
          f"{snap.header['word_count']} palavras; observer {snap.header['observer_ticks']}; "
          f"extra {col.extra}")
    for p in problems:
        print(f"  PROBLEMA: {p}")
    if preset.name in ("c1-func", "c1-layout") and args.batch < len(g.batches):
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
        if args.dump:
            for r in results:
                f = forms[r.form]
                print(f"  {r.form}: " + ", ".join(
                    f"{n}=0x{r.observed[k]:x}{'' if r.field_ok(k) is not False else '≠'}"
                    f"{('[' + r.alt_label(k) + ']') if r.alt_label(k) else ''}"
                    for k, n in enumerate(f.fields)))
    if preset.name == "c1-cycle" and args.batch < len(g.batches):
        from . import timing
        runs, probs = timing.parse(snap, g.forms, g.batches[args.batch], args.iters, args.trace)
        for p in probs:
            print(f"  PROBLEMA: {p}")
        byname = {v.name: v for v in g.forms}
        print(f"{'variante':28} {'TRM':>14} {'H-T1':>5} {'c fria':>8} {'c quente':>8} {'O':>6} lin  Δ(K,2K,3K) quente")
        for r in runs:
            v = byname[r.name]
            fits = r.fits(v.sizes)
            cold, warm = fits[0], fits[-1]
            fmt = lambda c: "—" if c is None else str(c)   # noqa: E731
            print(f"{r.name:28} {str(v.trm):>14} {str(v.renode):>5} {fmt(cold.c):>8} {fmt(warm.c):>8} "
                  f"{str(warm.o):>6} {'ok ' if all(f.linear for f in fits) else 'NÃO'} {warm.deltas}"
                  + (f"  perfil {r.profile}" if args.profile and r.profile else ""))
    print(f"dados: {out}")
    return 0 if not problems else 3


def cmd_trace(args) -> int:
    import json as _json
    from . import abi, gen, targets, trace
    from .presets import PRESETS, ROOT
    preset = PRESETS[args.preset]
    out = ROOT / "data" / "c1" / "diagnostic" / f"trace-{args.env}-{preset.name}-b{args.batch}-{utc()}"
    out.mkdir(parents=True)
    build(preset.name, out / "build.log")
    host = targets.HostBlock(batch=args.batch, iters=0, flags=abi.HOST_TRACE)
    if args.env == "hw":
        with targets.Bench(out) as bench:
            bench.flash(preset.elf, out / "flash.log")
            calls = trace.trace_hw(bench, preset.elf, out, host, args.timeout)
    else:
        calls = trace.trace_renode(preset.elf, out, host, args.env, args.timeout)
    (out / "trace.json").write_text(_json.dumps(calls))
    g = gen.generate(preset.name)
    b = g.batches[args.batch]
    names = ([g.forms[e.form].name for e in b.entries] if preset.name == "c1-func"
             else [g.forms[i].name for i in b.variants])
    for name, c in zip(names, calls):
        print(f"{name:32} {c['count']:4} {c['sha256']}")
    print(f"{len(calls)} chamadas; dados: {out}")
    return 0


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
    r.add_argument("--profile", action="store_true", help="mostra os contadores de perfil do DWT")
    r.add_argument("--dump", action="store_true", help="mostra todos os campos de cada vetor")
    r.add_argument("--out", type=Path, default=None)
    t = sub.add_parser("trace", help="traço por stepi de um lote (diagnóstico)")
    t.add_argument("--env", choices=ENVS, required=True)
    t.add_argument("--preset", choices=("c1-func", "c1-cycle"), required=True)
    t.add_argument("--batch", type=int, default=0)
    t.add_argument("--timeout", type=float, default=1800)
    c = sub.add_parser("campaign", help="campanha completa (placa + Renode + traço + análise)")
    c.add_argument("--name", required=True)
    c.add_argument("--mode", choices=("pilot", "final"), required=True)
    c.add_argument("--board", required=True, help="identidade física do exemplar (etiqueta)")
    c.add_argument("--board-note", default="")
    c.add_argument("--env", dest="envs", nargs="+", default=list(ENVS), choices=ENVS)
    c.add_argument("--pilot-from", default=None, help="campanha piloto cuja decisão de repetições vale")
    c.add_argument("--reps", type=int, default=None, help="força o número de execuções (diagnóstico)")
    c.add_argument("--iters", type=int, default=None, help="força as iterações quentes do c1-cycle")
    c.add_argument("--no-trace", dest="trace", action="store_false")
    c.add_argument("--jobs", type=int, default=4)
    c.add_argument("--resume", action="store_true")
    a = sub.add_parser("analyze", help="(re)gera analysis/ de uma campanha")
    a.add_argument("--name", required=True)
    sub.add_parser("check", help="pré-verificação, build do zero e gate dos três presets")
    args = p.parse_args(argv)

    if args.cmd == "check":
        from . import campaign
        log = campaign.Log(campaign.DATA / "diagnostic" / "check.log")
        try:
            with campaign.Lock(campaign.DATA / ".build.lock", "a árvore build/"):
                campaign.preflight(list(ENVS), log)
                log(f"vendor: {campaign.vendor_integrity()}")
                for preset in campaign.PRESET_ORDER:
                    campaign.build(preset, campaign.DATA / "diagnostic" / "build")
                    log(f"{preset}: {campaign.gate(preset)}")
        except campaign.CampaignError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.cmd in ("campaign", "analyze"):
        import re as _re
        from . import campaign
        if not _re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.name):
            p.error("--name: só letras, dígitos, '.', '_' e '-'")
        try:
            if args.cmd == "campaign":
                if args.mode == "pilot" and args.pilot_from:
                    p.error("--pilot-from só faz sentido no modo final")
                return campaign.run_campaign(args)
            from .analysis import analyze
            root = campaign.DATA / args.name
            if not (root / "plan.json").exists():
                raise campaign.CampaignError(f"campanha inexistente: {args.name}")
            with campaign.Lock(root / ".lock", f"campanha '{args.name}'"):
                summary = analyze(root, print)
            return 0 if summary["complete"] else 3
        except (campaign.CampaignError, OSError, ValueError) as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("interrompido: tentativas já gravadas ficam; use --resume", file=sys.stderr)
            return 130
    if args.cmd == "trace":
        return cmd_trace(args)
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
