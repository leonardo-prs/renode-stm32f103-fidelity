"""Gate do ELF: a instrução executada é a instrução testada.

O oráculo é definido POR INSTRUÇÃO; se o montador escolher outra
codificação (16 × 32 bits) ou trocar a instrução (ex.: `ldm r0, {r1}` vira
`ldr`), o caso deixaria de testar o que diz testar. Este módulo confere, no
disassembly do ELF final, cada rótulo <rotina>_x<k> declarado no catálogo:
mnemônico, largura e operandos. Qualquer diferença recusa o ELF (veredito
EVIDÊNCIA INVÁLIDA para tudo o que dele dependeria).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .targets import run_command

LINE = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{4}(?: [0-9a-f]{4})?)\s+(\S+)(?:\s+(.*))?$")


@dataclass(frozen=True)
class Decoded:
    addr: int
    width: int
    mnemonic: str
    operands: str


def symbols(elf: Path) -> dict[str, int]:
    out = run_command(["arm-none-eabi-nm", str(elf)]).stdout
    syms = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms[parts[2]] = int(parts[0], 16)
    return syms


def disassemble(elf: Path) -> dict[int, Decoded]:
    out = run_command(["arm-none-eabi-objdump", "-d", str(elf)], timeout_s=60).stdout
    insns = {}
    for line in out.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        addr, raw, mnem, ops = int(m[1], 16), m[2], m[3], (m[4] or "")
        ops = re.split(r"\s+[@;]", ops)[0].strip()       # comentários do objdump
        width = 16 if len(raw) == 4 else 32
        insns[addr] = Decoded(addr, width, mnem, ops)
    return insns


def check_points(elf: Path, points: list[tuple[str, str, str, int, str | None]]) -> list[str]:
    """points: (dono, rótulo, mnemônico-regex, largura, operandos-regex).

    Devolve a lista de problemas (vazia = ELF aceito)."""
    syms = symbols(elf)
    insns = disassemble(elf)
    problems = []
    declared = set()
    for owner, label, mnem, width, ops in points:
        declared.add(label)
        if label not in syms:
            problems.append(f"{owner}: rótulo {label} ausente no ELF")
            continue
        d = insns.get(syms[label] & ~1)
        if d is None:
            problems.append(f"{owner}: {label} não aponta para uma instrução")
            continue
        if not re.fullmatch(mnem, d.mnemonic):
            problems.append(f"{owner}: {label} é '{d.mnemonic} {d.operands}', esperado '{mnem}'")
        if d.width != width:
            problems.append(f"{owner}: {label} tem {d.width} bits, esperado {width}")
        if ops is not None and not re.match(ops + r"$", d.operands):
            problems.append(f"{owner}: {label} operandos '{d.operands}', esperado /{ops}/")
    orphans = sorted(s for s in syms if re.search(r"_x\d+$", s) and s not in declared
                     and (s.startswith("v_") or s.startswith("t_")))
    if orphans:
        problems.append(f"rótulos de teste sem declaração no catálogo: {orphans[:6]}")
    return problems


def func_points(forms) -> list[tuple[str, str, str, int, str | None]]:
    points = []
    seen = set()
    for f in forms:
        for insn in f.insns:
            label = f"{f.routine}_x{insn.k}"
            key = (label, insn.mnemonic, insn.width, insn.operands)
            if key in seen:
                continue
            seen.add(key)
            points.append((f.name, label, insn.mnemonic, insn.width, insn.operands))
    return points


def gate(preset_name: str, elf: Path) -> list[str]:
    from .gen import generate
    g = generate(preset_name)
    if preset_name == "c1-func":
        return check_points(elf, func_points(g.forms))
    if preset_name == "c1-cycle":
        from .cycle import points as cycle_points
        return check_points(elf, cycle_points(g.forms))
    return []
