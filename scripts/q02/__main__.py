"""CLI do Q-02 (preset q02, só Renode, perfil R1).

  python -m q02 check                          build do zero + gate do ELF
  python -m q02 run --name piloto-01 [--reps 2] [--no-build]
  python -m q02 analyze --name piloto-01       refaz a análise
  python -m q02 gen --out DIR                  (chamado pelo CMake)

Dados em data/q02/<nome>/ (gitignored): plan.json, <variante>-<rep>/ com os
arquivos brutos e analysis/{results.json,report.md}.
Saída: 0 = veredito emitido (IGUAL, REPROVADO ou NÃO DETERMINÍSTICO são
resultado); 3 = EVIDÊNCIA INVÁLIDA; 1 = erro de pré-condição/build.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="q02", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="gera q02_spec.h")
    g.add_argument("--out", type=Path, required=True)
    sub.add_parser("check", help="build do zero do q02 + gate estático do ELF")
    r = sub.add_parser("run", help="build + gate + coleta no Renode + análise")
    r.add_argument("--name", required=True)
    r.add_argument("--reps", type=int, default=2, help="repetições por variante (determinismo)")
    r.add_argument("--no-build", action="store_true")
    a = sub.add_parser("analyze", help="refaz a análise a partir dos dados brutos")
    a.add_argument("--name", required=True)
    args = p.parse_args(argv)

    if args.cmd == "gen":
        from . import gen
        gen.write(args.out)
        return 0
    from . import campaign
    if args.cmd == "check":
        return campaign.check()
    if args.cmd == "run":
        if args.reps < 2:
            p.error("--reps >= 2 (o determinismo é conferido entre repetições)")
        return campaign.run(args.name, args.reps, build_first=not args.no_build)
    return campaign.analyze(args.name)


if __name__ == "__main__":
    sys.exit(main())
