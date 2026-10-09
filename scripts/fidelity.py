#!/usr/bin/env python3
"""CLI do experimento de fidelidade Renode × STM32F103 (ver README).

    campaign  campanha completa: build, gate, bancada, Renode, análise
    analyze   (re)gera a análise de uma campanha existente
    run       um único run (diagnóstico): decodifica e avalia
    check     pré-verificação + build + gate, sem executar nada
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fidelity import abi, campaign, targets  # noqa: E402
from fidelity.firmwares import FIRMWARES  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="fidelity.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("campaign", help="campanha completa (um comando no laboratório)")
    c.add_argument("--name", required=True, help="identidade da campanha (diretório em data/fidelity/)")
    c.add_argument("--board", required=True,
                   help="identidade física do exemplar (ex.: 'stm32f103c8-genuino-lab-01')")
    c.add_argument("--board-note", default="", help="observação livre sobre o exemplar (marcação do chip...)")
    c.add_argument("--reps", type=int, default=None, help="runs por firmware e ambiente (final 50, piloto 10)")
    c.add_argument("--pilot", action="store_true", help="modo piloto (10 runs por padrão)")
    c.add_argument("--firmwares", nargs="+", default=list(FIRMWARES), choices=list(FIRMWARES))
    c.add_argument("--env", dest="envs", nargs="+", default=["hw", "renode"], choices=["hw", "renode"])
    c.add_argument("--resume", action="store_true", help="retoma uma campanha (exige plano idêntico)")
    c.add_argument("--calibration", action="store_true",
                   help="complemento do C1: escolhe MIPS calibrado e roda o Renode calibrado (só C1)")
    c.add_argument("--no-instr", dest="instr", action="store_false",
                   help="pula o traço por stepi do C1-timing (nível 'instrução' fica sem evidência)")
    c.add_argument("--jobs", type=int, default=4, help="processos Renode em paralelo (padrão 4)")

    a = sub.add_parser("analyze", help="(re)gera analysis/ de uma campanha")
    a.add_argument("--name", required=True)

    r = sub.add_parser("run", help="um run de diagnóstico (não entra em campanha)")
    r.add_argument("--env", choices=["hw", "renode"], required=True)
    r.add_argument("--firmware", choices=list(FIRMWARES), required=True)
    r.add_argument("--mips", type=int, default=targets.NOMINAL_MIPS)
    r.add_argument("--out", type=Path, default=None)

    k = sub.add_parser("check", help="pré-verificação, build e gate de todos os firmwares")
    k.add_argument("--env", dest="envs", nargs="+", default=["hw", "renode"], choices=["hw", "renode"])
    args = p.parse_args(argv)
    if args.cmd == "campaign" and args.reps is None:
        args.reps = 10 if args.pilot else 50
    return args


def cmd_run(args) -> int:
    fw = FIRMWARES[args.firmware]
    out = args.out or campaign.DATA / "diagnostic" / f"{args.env}-{fw.name}-{campaign.utc()}"
    out.mkdir(parents=True, exist_ok=True)
    if args.env == "hw":
        with targets.Bench(out) as bench:
            print(json.dumps(bench.identify()))
            bench.flash(fw.elf, out / "flash.log")
            collected = bench.run(fw.elf, out, fw.timeout_s)
    else:
        mips = args.mips
        q = targets.QUANTUM_S if mips == targets.NOMINAL_MIPS else campaign.quantum_for(mips)
        collected = targets.run_renode(fw.elf, out, fw.timeout_s, mips=mips, quantum_s=q)
    rec = campaign.record_run(out, fw, args.env, {"diagnostic": True}, collected, None)
    print(json.dumps({k: rec[k] for k in ("status", "problems")}, ensure_ascii=False))
    if rec["status"] == "valid":
        ev = fw.evaluate(abi.decode(collected.snapshot))
        bad = [c for c in ev.checks if not c.ok]
        print(f"{len(ev.checks)} verificações, {len(bad)} diferentes do oráculo; {len(ev.metrics)} métricas")
        for c in bad:
            print(f"  ≠ {c.case} | {c.item} | esperado {c.expected} | observado {c.observed}")
    print(f"dados: {out}")
    return 0 if rec["status"] == "valid" else 3


def cmd_check(args) -> int:
    log = campaign.Log(campaign.DATA / "diagnostic" / "check.log")
    campaign.preflight(args.envs, log)
    log(f"vendor: {campaign.vendor_integrity()}")
    for fw in FIRMWARES.values():
        campaign.build(fw, campaign.DATA / "diagnostic" / "build")
        log(f"{fw.name}: {campaign.gate(fw)}")
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.cmd == "campaign":
            return campaign.run_campaign(args)
        if args.cmd == "analyze":
            from fidelity.analysis import analyze
            summary = analyze(campaign.DATA / args.name)
            print(json.dumps({"complete": summary["complete"], "classes": summary["classes"]},
                             default=str, ensure_ascii=False))
            return 0 if summary["complete"] else 3
        if args.cmd == "run":
            return cmd_run(args)
        if args.cmd == "check":
            return cmd_check(args)
    except campaign.CampaignError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return campaign.EXIT_ERROR
    except KeyboardInterrupt:
        print("interrompido: tentativas já gravadas ficam; use --resume", file=sys.stderr)
        return 130
    return 1


if __name__ == "__main__":
    sys.exit(main())
