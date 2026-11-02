"""CLI do C2 #oD (preset c2-od, só Renode, perfil R1).

  python -m c2 check                                  build do zero + gate
  python -m c2 run --case C2-09 --name piloto-01 [--reps 2] [--no-build]
  python -m c2 analyze --case C2-09 --name piloto-01  refaz a análise
  python -m c2 gen --out DIR                          (chamado pelo CMake)

Dados em data/c2/<caso>/<nome>/ (gitignored): plan.json, <variante>-<rep>/
com os arquivos brutos de cada execução, e analysis/{results.json,report.md}.
Saída: 0 = veredito emitido (IGUAL, DIVERGE ou NÃO DETERMINÍSTICO são
resultado, não erro); 3 = EVIDÊNCIA INVÁLIDA; 1 = erro de pré-condição/build.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="c2", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="gera c2_catalog.h")
    g.add_argument("--out", type=Path, required=True)
    sub.add_parser("check", help="build do zero do c2-od + gate estático do ELF")
    r = sub.add_parser("run", help="build + gate + coleta no Renode + análise")
    r.add_argument("--case", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--reps", type=int, default=2, help="repetições por variante (determinismo)")
    r.add_argument("--no-build", action="store_true")
    a = sub.add_parser("analyze", help="refaz a análise a partir dos dados brutos")
    a.add_argument("--case", required=True)
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
        return campaign.run(args.case, args.name, args.reps, build_first=not args.no_build)
    return campaign.analyze(args.case, args.name)


if __name__ == "__main__":
    sys.exit(main())
