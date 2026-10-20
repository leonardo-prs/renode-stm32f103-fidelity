"""FA — aritmética e flags (src/c1/func/fa.S).

Toda soma e subtração é AddWithCarry (§A2.2.1); a subtração x − y é
AddWithCarry(x, NOT y, 1), por isso C = 1 significa "não houve empréstimo".
"""
from __future__ import annotations

from .. import arm
from ..catalog import Insn
from ..vectors import FLAGS_C, MOD_CONSTS, NZCV16, rows, table
from .common import arith, carry, hx, imm_re, vbin, vflg1, vflg2, vun

SRC = "@armlimited2021"
NOT = lambda y: arm.u32(~y)  # noqa: E731


def _adds(x, y, ap):
    r, c, v = arm.add_with_carry(x, y, 0)
    return r, arith(ap, r, c, v)


def _adcs(x, y, ap):
    r, c, v = arm.add_with_carry(x, y, carry(ap))
    return r, arith(ap, r, c, v)


def _subs(x, y, ap):
    r, c, v = arm.add_with_carry(x, NOT(y), 1)
    return r, arith(ap, r, c, v)


def _sbcs(x, y, ap):
    r, c, v = arm.add_with_carry(x, NOT(y), carry(ap))
    return r, arith(ap, r, c, v)


def _rsbs(x, y, ap):           # Rd = Rm − Rn  (x = Rn, y = Rm)
    r, c, v = arm.add_with_carry(NOT(x), y, 1)
    return r, arith(ap, r, c, v)


def _flags_of(fn):
    return lambda x, y, ap: fn(x, y, ap)[1]


def _unchanged(fn):
    """Formas sem S: resultado de fn, APSR inalterado."""
    return lambda x, y, ap: (fn(x, y), ap & 0xF800_0000)


FORMS = [
    vbin("FA-01.t1", "FA-01", "v_fa01_t1", _adds, Insn("adds", 16, r"r2, r2, r3"),
         level="N1", source=f"{SRC}[§A7.7.4]"),
    vbin("FA-01.t3", "FA-01", "v_fa01_t3", _adds, Insn("adds.w", 32, r"r2, r2, r3"),
         level="N1", source=f"{SRC}[§A7.7.4]"),
    vbin("FA-02.t1", "FA-02", "v_fa02_t1", _adcs, Insn("adcs", 16, r"r2, r3"),
         flags=FLAGS_C, source=f"{SRC}[§A7.7.2]"),
    vbin("FA-02.t2", "FA-02", "v_fa02_t2", _adcs, Insn("adcs.w", 32, r"r2, r2, r3"),
         flags=FLAGS_C, source=f"{SRC}[§A7.7.2]"),
    vbin("FA-03.t1", "FA-03", "v_fa03_t1", _subs, Insn("subs", 16, r"r2, r2, r3"),
         level="N1", source=f"{SRC}[§A7.7.175]"),
    vbin("FA-03.t2", "FA-03", "v_fa03_t2", _subs, Insn("subs.w", 32, r"r2, r2, r3"),
         level="N1", source=f"{SRC}[§A7.7.175]"),
    vbin("FA-04.t1", "FA-04", "v_fa04_t1", _sbcs, Insn("sbcs", 16, r"r2, r3"),
         flags=FLAGS_C, source=f"{SRC}[§A7.7.125]"),
    vbin("FA-04.t2", "FA-04", "v_fa04_t2", _sbcs, Insn("sbcs.w", 32, r"r2, r2, r3"),
         flags=FLAGS_C, source=f"{SRC}[§A7.7.125]"),
    vun("FA-05.i1", "FA-05", "v_fa05_i1", lambda x, ap: _rsbs(x, 0, ap),
        Insn("rsbs", 16, r"r2, r2, #0"), source=f"{SRC}[§A7.7.119]",
        note="NEGS (T1 só admite #0)"),
    vun("FA-05.i2.0", "FA-05", "v_fa05_i2_0", lambda x, ap: _rsbs(x, 0, ap),
        Insn("rsb.w|rsbs.w", 32, r"r2, r2, #0"), source=f"{SRC}[§A7.7.119]"),
    *[vun(f"FA-05.i2.{hx(c)}", "FA-05", f"v_fa05_i2_{hx(c)}",
          lambda x, ap, c=c: _rsbs(x, c, ap), Insn("rsbs.w", 32, r"r2, r2, " + imm_re(c)),
          source=f"{SRC}[§A7.7.119]") for c in MOD_CONSTS],
    vbin("FA-05.r", "FA-05", "v_fa05_r", _rsbs, Insn("rsbs", 32, r"r2, r2, r3"),
         source=f"{SRC}[§A7.7.120]", note="RSB registrador só tem forma de 32 bits"),
    vflg2("FA-06.cmp.t1", "FA-06", "v_fa06_cmp_t1", _flags_of(_subs), Insn("cmp", 16, r"r2, r3"),
          level="N1", source=f"{SRC}[§A7.7.28]"),
    vflg2("FA-06.cmp.t2", "FA-06", "v_fa06_cmp_t2", _flags_of(_subs), Insn("cmp", 16, r"r8, r3"),
          level="N1", source=f"{SRC}[§A7.7.28]", note="T2: registrador alto"),
    vflg2("FA-06.cmp.t3", "FA-06", "v_fa06_cmp_t3", _flags_of(_subs),
          Insn("cmp.w", 32, r"r2, r3"), level="N1", source=f"{SRC}[§A7.7.28]"),
    vflg2("FA-06.cmn.t1", "FA-06", "v_fa06_cmn_t1", _flags_of(_adds), Insn("cmn", 16, r"r2, r3"),
          level="N1", source=f"{SRC}[§A7.7.26]"),
    vflg2("FA-06.cmn.t2", "FA-06", "v_fa06_cmn_t2", _flags_of(_adds),
          Insn("cmn.w", 32, r"r2, r3"), level="N1", source=f"{SRC}[§A7.7.26]"),
    *[vflg1(f"FA-06.cmpi.t1.{c}", "FA-06", f"v_fa06_cmpi_t1_{c}",
            lambda x, ap, c=c: _subs(x, c, ap)[1], Insn("cmp", 16, r"r2, " + imm_re(c)),
            level="N1", source=f"{SRC}[§A7.7.27]") for c in (0, 1, 7, 255)],
    *[vflg1(f"FA-06.cmpi.t2.{hx(c)}", "FA-06", f"v_fa06_cmpi_t2_{hx(c)}",
            lambda x, ap, c=c: _subs(x, c, ap)[1], Insn("cmp.w", 32, r"r2, " + imm_re(c)),
            level="N1", source=f"{SRC}[§A7.7.27]") for c in MOD_CONSTS],
    *[vflg1(f"FA-06.cmni.{hx(c)}", "FA-06", f"v_fa06_cmni_{hx(c)}",
            lambda x, ap, c=c: _adds(x, c, ap)[1], Insn("cmn.w", 32, r"r2, " + imm_re(c)),
            level="N1", source=f"{SRC}[§A7.7.25]") for c in MOD_CONSTS],
]

# FA-07: sem S, as flags não mudam. 16 NZCV iniciais × 4 pares de bordas
# (os pares listados, não o produto 4 × 4).
_PAIRS = ((0x7FFF_FFFF, 1), (0xFFFF_FFFF, 1), (0, 1), (0x8000_0000, 0xFFFF_FFFF))
_fa07 = [
    vbin("FA-07.add", "FA-07", "v_fa07_add", _unchanged(lambda x, y: arm.u32(x + y)),
         Insn("add.w", 32, r"r2, r2, r3"), source=f"{SRC}[§A7.7.4]"),
    vbin("FA-07.sub", "FA-07", "v_fa07_sub", _unchanged(lambda x, y: arm.u32(x - y)),
         Insn("sub.w", 32, r"r2, r2, r3"), source=f"{SRC}[§A7.7.175]"),
    vun("FA-07.addw", "FA-07", "v_fa07_addw", lambda x, ap: (arm.u32(x + 0xFFF), ap & 0xF800_0000),
        Insn("addw", 32, r"r2, r2, #4095"), source=f"{SRC}[§A7.7.3]"),
    vun("FA-07.subw", "FA-07", "v_fa07_subw", lambda x, ap: (arm.u32(x - 0xFFF), ap & 0xF800_0000),
        Insn("subw", 32, r"r2, r2, #4095"), source=f"{SRC}[§A7.7.174]"),
]
_fa07[0].axes = _fa07[1].axes = (table(*_PAIRS), rows(NZCV16))
_fa07[2].axes = _fa07[3].axes = (table(*[(a,) for a, _ in _PAIRS]), rows(NZCV16))
FORMS += _fa07

# FA-08: ADDS/SUBS com imediato.
for _op, _name, _fn in (("adds", "adds", _adds), ("subs", "subs", _subs)):
    FORMS += [vun(f"FA-08.{_name}.t1.{c}", "FA-08", f"v_fa08_{_name}_t1_{c}",
                  lambda x, ap, c=c, fn=_fn: fn(x, c, ap), Insn(_op, 16, r"r2, r3, " + imm_re(c)),
                  source=f"{SRC}[§A7.7.3, §A7.7.174]") for c in (0, 1, 7)]
    FORMS += [vun(f"FA-08.{_name}.t2.{c}", "FA-08", f"v_fa08_{_name}_t2_{c}",
                  lambda x, ap, c=c, fn=_fn: fn(x, c, ap), Insn(_op, 16, r"r2, " + imm_re(c)),
                  source=f"{SRC}[§A7.7.3, §A7.7.174]") for c in (0, 1, 7, 255)]
    FORMS += [vun(f"FA-08.{_name}.t3.{hx(c)}", "FA-08", f"v_fa08_{_name}_t3_{hx(c)}",
                  lambda x, ap, c=c, fn=_fn: fn(x, c, ap),
                  Insn(_op + ".w", 32, r"r2, r3, " + imm_re(c)),
                  source=f"{SRC}[§A7.7.3, §A7.7.174]") for c in MOD_CONSTS]

# FA-09: os exemplos resolvidos de Yiu (Tab. 4.7), pelas rotinas de FA-01/FA-03.
_YIU_ADD = ((0x70000000, 0x70000000), (0x90000000, 0x90000000), (0x80000000, 0x80000000))
_YIU_SUB = ((0x00001234, 0x00001000), (0x00000004, 0x00000005), (0xFFFFFFFF, 0xFFFFFFFC),
            (0x80000005, 0x80000004), (0x70000000, 0xF0000000), (0xA0000000, 0xA0000000))
_fa09_add = vbin("FA-09.add", "FA-09", "v_fa01_t1", _adds, Insn("adds", 16, r"r2, r2, r3"),
                 source="@yiu2014[Tab. 4.7]",
                 note="linha 2: 0x20000000 pelo pseudocódigo (o livro imprime 0x30000000)")
_fa09_add.axes = (table(*_YIU_ADD), rows((0,)))
_fa09_sub = vbin("FA-09.sub", "FA-09", "v_fa03_t1", _subs, Insn("subs", 16, r"r2, r2, r3"),
                 source="@yiu2014[Tab. 4.7]")
_fa09_sub.axes = (table(*_YIU_SUB), rows((0,)))
FORMS += [_fa09_add, _fa09_sub]


# FA-10: Q não é tocada por soma/subtração. Verificado nos próprios vetores de
# FA-01..FA-05 (as flags iniciais incluem Q = 0 e Q = 1 e o oráculo exige Q
# final = Q inicial); o relatório deriva o veredito do bit Q desses vetores.
DERIVED = {"FA-10": (("FA-01", "FA-02", "FA-03", "FA-04", "FA-05"), "apsr", 1 << arm.Q_BIT)}
