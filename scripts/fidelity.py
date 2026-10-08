#!/usr/bin/env python3
"""Ponto de entrada único do experimento de fidelidade HW × Renode.

    scripts/fidelity.py build s1a [s2a ...]          # cmake --preset + build
    scripts/fidelity.py run s1a --env hw --runs 10 --campaign v1
    scripts/fidelity.py run s1a --env renode --mips 8 --runs 2 --campaign v1
    scripts/fidelity.py show data/fidelity/v1/s1a/hw/run-001
    scripts/fidelity.py analyze --campaign v1 [s1a ...]

Dados: data/fidelity/<campanha>/<firmware>/<tag>/run-NNN/{manifest.json,
snapshot.bin, gdb.log, ...}. Um run = um reset → execução completa → dump.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fidelity import abi, firmware, runner  # noqa: E402


def cmd_build(args) -> int:
    for name in args.firmware:
        firmware.get(name)
        for step in (["cmake", "--preset", name], ["cmake", "--build", "--preset", name]):
            done = subprocess.run(step, cwd=firmware.ROOT, capture_output=True, text=True)
            if done.returncode:
                print(done.stdout[-3000:], done.stderr[-3000:], sep="\n")
                return done.returncode
        size = subprocess.run(["arm-none-eabi-size", str(firmware.get(name).elf)],
                              capture_output=True, text=True).stdout.strip().splitlines()[-1]
        print(f"[build] {name}: {size}")
    return 0


def cmd_run(args) -> int:
    fws = [firmware.get(n) for n in args.firmware]
    if args.elf:
        if len(fws) != 1 or not args.label:
            raise runner.RunError("--elf exige um único firmware e --label")
        fws = [dataclasses.replace(fws[0], elf_override=Path(args.elf).resolve())]
    failures = 0
    label = f"-{args.label}" if args.label else ""
    if args.env == "hw":
        with runner.HWBench(firmware.ROOT / "data" / "fidelity" / args.campaign / "_bench") as bench:
            for fw in fws:
                batch = runner.batch_identity(fw)
                base = runner.campaign_dir(args.campaign, fw, ("hw-free" if args.free_run else "hw") + label)
                bench.flash(fw)
                runner.record_batch(base, {"utc": runner.utc(), "runs": args.runs,
                                           "tools": runner.tool_versions(), **batch})
                for _ in range(args.runs):
                    res = bench.run(fw, runner.next_run_dir(base), batch, free_run=args.free_run)
                    failures += not res.ok
                    print(f"[hw] {fw.name} {res.path.name}: {'ok' if res.ok else 'ERRO ' + res.error}")
    else:
        cfg = runner.RenodeConfig(mips=args.mips, quantum=args.quantum,
                                  uart_delay=not args.no_uart_delay)
        for fw in fws:
            batch = runner.batch_identity(fw)
            base = runner.campaign_dir(args.campaign, fw, cfg.tag + label)
            runner.record_batch(base, {"utc": runner.utc(), "runs": args.runs,
                                       "tools": runner.tool_versions(), **batch})
            for _ in range(args.runs):
                t0 = time.monotonic()
                res = runner.run_renode(fw, cfg, runner.next_run_dir(base), batch)
                failures += not res.ok
                print(f"[{cfg.tag}] {fw.name} {res.path.name}: "
                      f"{'ok' if res.ok else 'ERRO ' + res.error} ({time.monotonic() - t0:.1f} s)")
    return 1 if failures else 0


def cmd_show(args) -> int:
    run = Path(args.run)
    manifest = json.loads((run / "manifest.json").read_text())
    snap = abi.decode((run / "snapshot.bin").read_bytes())
    fw = firmware.get(manifest["firmware"])
    h = snap.header
    print(f"{fw.title} — {manifest['tag']} — {run}")
    print(f"state={abi.STATES[h['state']]} error={h['error']:#x} {h['error_names']} "
          f"rows={h['row_count']}/{h['row_capacity']} trace={h['trace_count']} drop={h['trace_drop']}")
    print(f"cpuid={h['cpuid']:#x} rcc_cr={h['rcc_cr']:#x} cfgr={h['rcc_cfgr']:#x} "
          f"acr={h['flash_acr']:#x} aircr={h['aircr']:#x} dbgmcu={h['dbgmcu_cr']:#x} "
          f"observer={h['observer_ticks']} end={h['end_ticks']}")
    for r in snap.rows:
        names = fw.field_names(r[1])
        cond = fw.conditions.get(r[1], str(r[1]))
        vals = " ".join(f"{n}={v}" for n, v in zip(names, r[2:]))
        print(f"  t{r[0]:<3} {cond:<12} {vals}")
    if args.trace:
        for e in snap.trace:
            print(f"  [{abi.WRITERS[e.writer]}#{e.index}] t={e.ticks} ev={e.event:#x} "
                  f"trial={e.trial} arg={e.arg:#x}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("firmware", nargs="+")
    r = sub.add_parser("run")
    r.add_argument("firmware", nargs="+")
    r.add_argument("--env", choices=("hw", "renode"), required=True)
    r.add_argument("--runs", type=int, default=1)
    r.add_argument("--campaign", required=True)
    r.add_argument("--mips", type=float, default=8.0)
    r.add_argument("--quantum", default="0.000001")
    r.add_argument("--no-uart-delay", action="store_true")
    r.add_argument("--elf", help="ELF de diagnóstico (build com FINAL_DEFS)")
    r.add_argument("--label", help="sufixo do diretório de dados p/ diagnósticos")
    r.add_argument("--free-run", action="store_true",
                   help="HW: roda sem debugger conectado; conecta e faz dump depois")
    s = sub.add_parser("show")
    s.add_argument("run")
    s.add_argument("--trace", action="store_true")
    a = sub.add_parser("analyze")
    a.add_argument("firmware", nargs="*")
    a.add_argument("--campaign", required=True)
    args = p.parse_args(argv)
    if args.cmd == "analyze":
        from fidelity import analysis
        return analysis.main(args)
    try:
        return {"build": cmd_build, "run": cmd_run, "show": cmd_show}[args.cmd](args)
    except runner.RunError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
