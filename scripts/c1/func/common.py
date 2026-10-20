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


def ins(text: str, width: int, k: int = 0) -> Insn:
    """Insn a partir do texto exato que o objdump imprime ("ands.w r2, r2, r3, lsl #1")."""
    import re
    mnem, _, ops = text.partition(" ")
    return Insn(re.escape(mnem), width, re.escape(ops.strip()) if ops else "", k)


# ───────────────────────────── faltas ─────────────────────────────
# Campos do registro de faltas (fault.S): cfsr hfsr mmfar bfar pc xpsr
# exc_return landing ipsr count. Valores esperados podem ser um nome de
# símbolo do ELF (str, opcionalmente "sym+N"), resolvido na avaliação.

T_BIT = 1 << 24
XPSR_MASK = 0xFF00_FFFF      # NZCVQ, IT[1:0], T, IT[7:2], bit 9 e exceção
EXC_THREAD_MSP, EXC_THREAD_PSP, EXC_HANDLER = 0xFFFF_FFF9, 0xFFFF_FFFD, 0xFFFF_FFF1
IPSR_HARD, IPSR_MEM, IPSR_BUS, IPSR_USAGE, IPSR_SVC = 3, 4, 5, 6, 11

# CFSR (PM0056 §4.4.10): MMFSR [7:0], BFSR [15:8], UFSR [31:16].
IACCVIOL, MMARVALID = 1 << 0, 1 << 7
PRECISERR, BFARVALID = 1 << 9, 1 << 15
UNDEFINSTR, INVSTATE, INVPC, NOCP = 1 << 16, 1 << 17, 1 << 18, 1 << 19
UNALIGNED, DIVBYZERO = 1 << 24, 1 << 25
HFSR_FORCED = 1 << 30


def fault(cfsr: int, pc, *, apsr: int = 0, hfsr: int = 0, ipsr: int = IPSR_USAGE,
          xpsr_extra: int = T_BIT, exc_return: int = EXC_THREAD_MSP,
          mmfar=None, bfar=None, xpsr=None) -> dict:
    """Falta com aterrissagem: o tratador consumiu a aterrissagem (0)."""
    return {"cfsr": cfsr, "hfsr": hfsr,
            "mmfar": mmfar if cfsr & MMARVALID else None,
            "bfar": bfar if cfsr & BFARVALID else None,
            "pc": pc,
            "xpsr": xpsr if xpsr is not None else ((apsr & APSR_MASK) | xpsr_extra, XPSR_MASK),
            "exc_return": exc_return, "landing": 0, "ipsr": ipsr, "count": 1}


def no_fault(landing) -> dict:
    """Nenhuma falta: registro zerado, aterrissagem ainda publicada (não usada)."""
    return {"cfsr": 0, "hfsr": 0, "mmfar": 0, "bfar": 0, "pc": 0, "xpsr": 0,
            "exc_return": 0, "landing": landing, "ipsr": 0, "count": 0}


class Mem:
    """Janela c1_scratch (32 B) no oráculo: pré-enchida com 0xA5 pelo main."""

    def __init__(self, fill: int = 0xA5):
        self.b = bytearray([fill] * 32)

    def store(self, off: int, value: int, size: int) -> None:
        self.b[off:off + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")

    def load(self, off: int, size: int, signed: bool = False) -> int:
        v = int.from_bytes(self.b[off:off + size], "little")
        return arm.sign_extend(v, 8 * size) if signed else v

    def word(self, k: int) -> int:
        return self.load(4 * k, 4)

    def fields(self) -> dict:
        return {f"mem{k}": self.word(k) for k in range(8)}


def pattern(seed: int, k: int) -> int:
    """Palavra k do padrão FILLWIN/SEEDREGS: semente + k·0x01010101."""
    return arm.u32(seed + k * 0x0101_0101)
