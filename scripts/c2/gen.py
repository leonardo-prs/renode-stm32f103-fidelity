"""Gera build/<preset>/gen/c2_catalog.h a partir do catálogo (chamado pelo CMake).

    python -m c2 gen --out build/c2-od/gen
"""
from __future__ import annotations

from pathlib import Path

from . import catalog as K


def header() -> str:
    lines = [
        "/* GERADO por scripts/c2/gen.py a partir de scripts/c2/catalog.py — não editar. */",
        "#ifndef C2_CATALOG_H",
        "#define C2_CATALOG_H",
        "",
        f'#define C2_CATALOG_HASH "{K.catalog_hash()}"',
        f"#define C2_MAGIC        0x{K.MAGIC:08X}UL",
        f"#define C2_MAX_POINTS   {K.MAX_POINTS}U",
        f"#define C2_N_ARGS       {K.N_ARGS}U",
        f"#define C2_N_REC        {K.N_REC}U",
        f"#define C2_N_IRQ        {K.N_IRQ}U",
        f"#define C2_POINT_SHIFT  {K.POINT_SHIFT}U",
        "",
        f"#define C2_ST_RUNNING   {K.ST_RUNNING}U",
        f"#define C2_ST_DONE      {K.ST_DONE}U",
        f"#define C2_ST_BAD_PARAM {K.ST_BAD_PARAM}U",
        "",
    ]
    lines += [f"#define C2_CASE_{num:02d}     {num}U   /* {cid} */" for cid, num in K.CASES.items()]
    lines += [""] + [f"#define C2_MECH_{m:<6} {v}U" for m, v in K.MECH.items()]
    lines += ["", "/* Linhas livres usadas como estímulo por software (vetor → c2_irq_handler). */",
              "#define C2_FREE_LINES_MASK0 0x%08XUL" % sum(1 << n for n in K.FREE_LINES if n < 32),
              "#define C2_FREE_LINES_MASK1 0x%08XUL" % sum(1 << (n - 32) for n in K.FREE_LINES if n >= 32),
              "/* Vetores IRQ0..IRQ%d (posição 16 + n da tabela): linha livre → c2_irq_handler,"
              % (K.N_IRQ - 1), " * demais → c2_fault (nenhuma outra fonte é esperada). */",
              "#define C2_IRQ_VECTORS \\"]
    lines += [f"    {'c2_irq_handler' if n in K.FREE_LINES else 'c2_fault'}, /* IRQ{n} */ \\"
              for n in range(K.N_IRQ)]
    lines += ["", "", "/* C2-09 */"]
    lines += [f"#define C2_09_{p:<10} {v}U" for p, v in K.C2_09_PHASES.items()]
    lines += [f"#define C2_09_PRIO       {K.C2_09_PRIO}U",
              f"#define C2_09_WINDOW     {K.C2_09_WINDOW}U"]
    lines += [f"#define C2_09_REC_{r.upper():<15} {i}U" for i, r in enumerate(K.C2_09_REC)]
    lines += ["", "#endif", ""]
    return "\n".join(lines)


def write(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "c2_catalog.h"
    text = header()
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)
    return path
