"""Construtores de formas funcionais (os moldes de src/c1/func/moldes.inc)."""
from __future__ import annotations

from typing import Callable

from .. import arm
from ..catalog import Form, Insn
from ..vectors import FLAGS2, V32, rows

APSR_MASK = arm.NZCVQ_MASK


def apsr_out(value: int) -> int:
    """Valor que MRS APSR devolve: só [31:27], zeros no resto (§B5.2.2)."""
    return value & APSR_MASK


def arith(apsr_in: int, result: int, c: int, v: int) -> int:
    """APSR depois de uma operação aritmética com S: N, Z pelo resultado."""
    n, z = arm.nz(result)
    return apsr_out(arm.with_nzcv(apsr_in, n, z, c, v))


def logical(apsr_in: int, result: int, c: int | None) -> int:
    """APSR depois de uma lógica com S: N, Z; C = carry do deslocador; V intacto."""
    n, z = arm.nz(result)
    return apsr_out(arm.with_nzcv(apsr_in, n, z, c, None))


def carry(apsr_in: int) -> int:
    return arm.bit(apsr_in, arm.C_BIT)


def vbin(name: str, case: str, routine: str, op: Callable[[int, int, int], tuple[int, int]],
         insn: Insn, *, a=V32, b=V32, flags=FLAGS2, **kw) -> Form:
    """Molde VBIN: in = {Rn, Rm, APSR}, out = {Rd, APSR}; op(x, y, apsr) → (rd, apsr')."""
    def oracle(vec):
        x, y, ap = vec
        rd, ap2 = op(x, y, ap)
        return {"rd": rd, "apsr": ap2}
    return Form(name, case, routine, (rows(a), rows(b), rows(flags)), ("rd", "apsr"),
                oracle, (insn,), **kw)


def vun(name: str, case: str, routine: str, op: Callable[[int, int], tuple[int, int]],
        insn: Insn, *, a=V32, flags=FLAGS2, **kw) -> Form:
    """Molde VUN: in = {x, APSR}, out = {Rd, APSR}; op(x, apsr) → (rd, apsr')."""
    def oracle(vec):
        x, ap = vec
        rd, ap2 = op(x, ap)
        return {"rd": rd, "apsr": ap2}
    return Form(name, case, routine, (rows(a), rows(flags)), ("rd", "apsr"), oracle,
                (insn,), **kw)


def vflg2(name: str, case: str, routine: str, op: Callable[[int, int, int], int],
          insn: Insn, *, a=V32, b=V32, flags=FLAGS2, **kw) -> Form:
    def oracle(vec):
        x, y, ap = vec
        return {"apsr": op(x, y, ap)}
    return Form(name, case, routine, (rows(a), rows(b), rows(flags)), ("apsr",), oracle,
                (insn,), **kw)


def vflg1(name: str, case: str, routine: str, op: Callable[[int, int], int],
          insn: Insn, *, a=V32, flags=FLAGS2, **kw) -> Form:
    def oracle(vec):
        x, ap = vec
        return {"apsr": op(x, ap)}
    return Form(name, case, routine, (rows(a), rows(flags)), ("apsr",), oracle,
                (insn,), **kw)


def hx(value: int) -> str:
    """Sufixo de rotina para uma constante (como o .irp do assembly)."""
    return f"{value:#x}"


def imm_re(value: int) -> str:
    """Regex do imediato como o objdump imprime (#N; ; 0x... opcional)."""
    return rf"#{value}\b"
