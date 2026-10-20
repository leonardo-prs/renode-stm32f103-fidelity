"""FMEM — larguras, extensão de sinal e modos de endereçamento (src/c1/func/fmem.S)."""
from __future__ import annotations

from .. import arm
from ..catalog import F_MEM, Form, Insn
from ..vectors import rows
from .common import Mem, ins, pattern

SRC = "@armlimited2021"
SEEDS = (0x1020_3040, 0xF0E0_D0C0)
ROM = bytes([0x11, 0x22, 0x33, 0x44, 0x80, 0x7F, 0xFF, 0x01,
             0xA5, 0x5A, 0x00, 0x80, 0xFE, 0xDC, 0xBA, 0x98])     # c1_rom em fmem.S


def rom(off: int, size: int, signed: bool = False) -> int:
    v = int.from_bytes(ROM[off:off + size], "little")
    return arm.sign_extend(v, 8 * size) if signed else v


FORMS: list[Form] = []

# FMEM-01: escrita de subpalavra em c1_scratch + 12; vizinhos intactos.
for op, size in (("str", 4), ("strh", 2), ("strb", 1)):
    def o1(vec, size=size):
        m = Mem()
        m.store(12, vec[0], size)
        return {"word": m.load(12, 4), **{f"b{k}": m.load(12 + k, 1) for k in range(4)},
                **m.fields()}
    FORMS.append(Form(f"FMEM-01.{op}", "FMEM-01", f"v_fmem01_{op}",
                      (rows((0x1122_3344, 0xA5, 0x5A5A, 0xFFFF_FFFF, 0x80)),),
                      ("word", "b0", "b1", "b2", "b3"), o1, (ins(f"{op} r3, [r2, #0]", 16),),
                      flags=F_MEM, level="N1",
                      source="@stmicroelectronics2021[§3.2] @armlimited2007[§2.4]"))

# FMEM-02: byte no deslocamento 1 e meia palavra no deslocamento 2.
_W2 = tuple((h << 16) | (b << 8) | 0x5A for b in (0x00, 0x7F, 0x80, 0xFF)
            for h in (0x0000, 0x7FFF, 0x8000, 0xFFFF))
for key, text, width, size, signed in (
        ("ldrb_t1", "ldrb r3, [r2, #1]", 16, 1, False), ("ldrb_w", "ldrb.w r3, [r2, #1]", 32, 1, False),
        ("ldrsb_r", "ldrsb r3, [r2, r4]", 16, 1, True), ("ldrsb_w", "ldrsb.w r3, [r2, #1]", 32, 1, True),
        ("ldrh_t1", "ldrh r3, [r2, #2]", 16, 2, False), ("ldrh_w", "ldrh.w r3, [r2, #2]", 32, 2, False),
        ("ldrsh_r", "ldrsh r3, [r2, r4]", 16, 2, True), ("ldrsh_w", "ldrsh.w r3, [r2, #2]", 32, 2, True)):
    def o2(vec, size=size, signed=signed):
        m = Mem()
        m.store(12, vec[0], 4)
        return {"rt": m.load(12 + (1 if size == 1 else 2), size, signed)}
    FORMS.append(Form(f"FMEM-02.{key}", "FMEM-02", f"v_fmem02_{key}", (rows(_W2),), ("rt",), o2,
                      (ins(text, width),), level="N1", source=f"{SRC}[§A7.7.46, §A7.7.59]"))

# FMEM-03: modos de endereçamento; base inicial c1_scratch + 16.
_V3 = (0x1122_3344, 0x8000_0001, 0xFFFF_FFFF)
for key, text, width, tgt, base in (
        ("ldr_imm12", "ldr.w r3, [r2, #4]", 32, 20, 16), ("ldr_neg8", "ldr.w r3, [r2, #-4]", 32, 12, 16),
        ("ldr_reg", "ldr r3, [r2, r4]", 16, 20, 16), ("ldr_lsl0", "ldr.w r3, [r2, r4]", 32, 20, 16),
        ("ldr_lsl1", "ldr.w r3, [r2, r4, lsl #1]", 32, 20, 16),
        ("ldr_lsl2", "ldr.w r3, [r2, r4, lsl #2]", 32, 20, 16),
        ("ldr_lsl3", "ldr.w r3, [r2, r4, lsl #3]", 32, 24, 16),
        ("ldr_pre", "ldr.w r3, [r2, #4]!", 32, 20, 20), ("ldr_post", "ldr.w r3, [r2], #4", 32, 16, 20)):
    FORMS.append(Form(f"FMEM-03.{key}", "FMEM-03", f"v_fmem03_{key}", (rows(_V3),), ("rt", "base"),
                      lambda vec, base=base: {"rt": vec[0], "base": base}, (ins(text, width),),
                      level="N1", source=f"{SRC}[§A7.7.43, §A7.7.45]",
                      note=f"alvo c1_scratch + {tgt}"))
for key, text, width, tgt, base in (
        ("str_imm12", "str.w r3, [r2, #4]", 32, 20, 16), ("str_neg8", "str.w r3, [r2, #-4]", 32, 12, 16),
        ("str_reg", "str r3, [r2, r4]", 16, 20, 16), ("str_lsl1", "str.w r3, [r2, r4, lsl #1]", 32, 20, 16),
        ("str_lsl2", "str.w r3, [r2, r4, lsl #2]", 32, 20, 16),
        ("str_lsl3", "str.w r3, [r2, r4, lsl #3]", 32, 24, 16),
        ("str_pre", "str.w r3, [r2, #4]!", 32, 20, 20), ("str_post", "str.w r3, [r2], #4", 32, 16, 20)):
    def o3(vec, tgt=tgt, base=base):
        m = Mem()
        m.store(tgt, vec[0], 4)
        return {"base": base, **m.fields()}
    FORMS.append(Form(f"FMEM-03.{key}", "FMEM-03", f"v_fmem03_{key}", (rows(_V3),), ("base",), o3,
                      (ins(text, width),), flags=F_MEM, level="N1",
                      source=f"{SRC}[§A7.7.158, §A7.7.161]"))

# FMEM-04: LDR literal com a instrução em endereço ≡ 0 e ≡ 2 (mod 4).
for key, rem in (("a4", 0), ("a2", 2)):
    FORMS.append(Form(f"FMEM-04.{key}", "FMEM-04", f"v_fmem04_{key}", (rows((0,)),), ("rt",),
                      lambda vec: {"rt": 0x5EED_F00D}, (Insn("ldr", 16, None, 0, (4, rem)),),
                      level="N1", source="@stmicroelectronics2024[§3.3.6]",
                      note="base Align(PC, 4)"))


# FMEM-05: LDM/STM/PUSH/POP (combinações codificáveis, §A7.7.41, §A7.7.159).
def _f5(name, routine, outs, fn, text, width, flags=0, k=0, extra=()):
    FORMS.append(Form(f"FMEM-05.{name}", "FMEM-05", routine, (rows(SEEDS),), outs,
                      lambda vec: fn(vec[0]), (ins(text, width, k), *extra), flags=flags,
                      level="N1", source=f"{SRC}[§A7.7.41, §A7.7.159] @armlimited2007[§2.3.2]"))


def _stored(seed, pairs):
    m = Mem()
    for k, value in pairs:
        m.store(4 * k, value, 4)
    return m.fields()


_f5("ldm1", "v_fmem05_ldm1", ("r3", "base"), lambda s: {"r3": pattern(s, 0), "base": 4},
    "ldmia r2!, {r3}", 16)
_f5("stm1", "v_fmem05_stm1", ("base",), lambda s: {"base": 4, **_stored(s, [(0, s)])},
    "stmia r2!, {r3}", 16, F_MEM)
for wb, base in (("_wb", 32), ("", 0)):
    _f5(f"ldm8{wb}", f"v_fmem05_ldm8{wb}", tuple(f"r{k}" for k in range(8)) + ("base",),
        lambda s, base=base: {**{f"r{k}": pattern(s, k) for k in range(8)}, "base": base},
        f"ldmia.w ip{'!' if wb else ''}, {{r0, r1, r2, r3, r4, r5, r6, r7}}", 32)
    _f5(f"stm8{wb}", f"v_fmem05_stm8{wb}", ("base",),
        lambda s, base=base: {"base": base, **_stored(s, [(k, pattern(s, k)) for k in range(8)])},
        f"stmia.w ip{'!' if wb else ''}, {{r0, r1, r2, r3, r4, r5, r6, r7}}", 32, F_MEM)
for wb, base in (("_wb", 20), ("", 0)):
    _f5(f"ldmsp{wb}", f"v_fmem05_ldmsp{wb}", ("r1", "r3", "r5", "r8", "r12", "base"),
        lambda s, base=base: {**dict(zip(("r1", "r3", "r5", "r8", "r12"),
                                         (pattern(s, k) for k in range(5)))), "base": base},
        f"ldmia.w r2{'!' if wb else ''}, {{r1, r3, r5, r8, ip}}", 32)
    _f5(f"stmsp{wb}", f"v_fmem05_stmsp{wb}", ("base",),
        lambda s, base=base: {"base": base, **_stored(s, list(enumerate(
            pattern(s, k) for k in (1, 3, 5, 6, 7))))},
        f"stmia.w r2{'!' if wb else ''}, {{r1, r3, r5, r8, ip}}", 32, F_MEM,
        extra=())
_f5("ldmbase.t1", "v_fmem05_ldmbase_t1", ("r1", "r2", "r3"),
    lambda s: {"r1": pattern(s, 0), "r2": pattern(s, 1), "r3": pattern(s, 2)},
    "ldmia r2, {r1, r2, r3}", 16)
_f5("ldmbase.t2", "v_fmem05_ldmbase_t2", ("r2", "r8"),
    lambda s: {"r2": pattern(s, 0), "r8": pattern(s, 1)}, "ldmia.w r2, {r2, r8}", 32)
for wb, base in (("_wb", 24), ("", 32)):
    _f5(f"ldmdb{wb}", f"v_fmem05_ldmdb{wb}", ("r3", "r4", "base"),
        lambda s, base=base: {"r3": pattern(s, 6), "r4": pattern(s, 7), "base": base},
        f"ldmdb r2{'!' if wb else ''}, {{r3, r4}}", 32)
    _f5(f"stmdb{wb}", f"v_fmem05_stmdb{wb}", ("base",),
        lambda s, base=base: {"base": base, **_stored(s, [(6, pattern(s, 3)), (7, pattern(s, 4))])},
        f"stmdb r2{'!' if wb else ''}, {{r3, r4}}", 32, F_MEM)


def _pushpop(n, first):
    def fn(s):
        vals = [pattern(s, first + k) for k in range(n)]
        out = {"push_delta": 4 * n, **{f"m{k}": v for k, v in enumerate(vals)},
               **{f"p{k}": v for k, v in enumerate(vals)}, "pop_delta": 0}
        return out
    return fn


for n, first, push, pop, w in ((1, 3, "push {r3}", "pop {r3}", 16),
                               (4, 4, "push {r4, r5, r6, r7}", "pop {r4, r5, r6, r7}", 16),
                               (8, 1, "stmdb sp!, {r4, r5, r6, r7, r8, r9, sl, fp}",
                                "ldmia.w sp!, {r4, r5, r6, r7, r8, r9, sl, fp}", 32)):
    outs = ("push_delta", *(f"m{k}" for k in range(n)), *(f"p{k}" for k in range(n)), "pop_delta")
    _f5(f"push{n}", f"v_fmem05_push{n}", outs, _pushpop(n, first), push, w,
        extra=(ins(pop, w, 1),))


# FMEM-06: LDRD/STRD com addr mod 8 = 0 e 4; base ≠ dados (§A7.7.50, errata 602117).
for key, text, addr, base in (("ldrd", "ldrd r3, r4, [r2, #8]", 8, 0),
                              ("ldrd_pre", "ldrd r3, r4, [r2, #8]!", 8, 8),
                              ("ldrd_post", "ldrd r3, r4, [r2], #8", 0, 8)):
    FORMS.append(Form(
        f"FMEM-06.{key}", "FMEM-06", f"v_fmem06_{key}", (rows(SEEDS), rows((0, 4))),
        ("r3", "r4", "base"),
        lambda vec, addr=addr, base=base: {"r3": pattern(vec[0], (vec[1] + addr) // 4),
                                           "r4": pattern(vec[0], (vec[1] + addr) // 4 + 1),
                                           "base": vec[1] + base},
        (ins(text, 32),), source=f"{SRC}[§A7.7.50]"))
for key, text, addr, base in (("strd", "strd r3, r4, [r2, #8]", 8, 0),
                              ("strd_pre", "strd r3, r4, [r2, #8]!", 8, 8),
                              ("strd_post", "strd r3, r4, [r2], #8", 0, 8)):
    def o6(vec, addr=addr, base=base):
        m = Mem()
        m.store(vec[1] + addr, vec[0], 4)
        m.store(vec[1] + addr + 4, pattern(vec[0], 1), 4)
        return {"base": vec[1] + base, **m.fields()}
    FORMS.append(Form(f"FMEM-06.{key}", "FMEM-06", f"v_fmem06_{key}", (rows(SEEDS), rows((0, 4))),
                      ("base",), o6, (ins(text, 32),), flags=F_MEM, source=f"{SRC}[§A7.7.166]"))

# FMEM-07: cargas de c1_rom (flash, DCode).
FORMS.append(Form(
    "FMEM-07", "FMEM-07", "v_fmem07", (rows((0,)),), ("ldr", "ldrb", "ldrh", "ldrsb", "ldrsh"),
    lambda vec: {"ldr": rom(4, 4), "ldrb": rom(6, 1), "ldrh": rom(10, 2),
                 "ldrsb": rom(4, 1, True), "ldrsh": rom(12, 2, True)},
    (ins("ldr r3, [r2, #4]", 16, 0), ins("ldrb r3, [r2, #6]", 16, 1), ins("ldrh r3, [r2, #10]", 16, 2),
     ins("ldrsb r3, [r2, r4]", 16, 3), ins("ldrsh r3, [r2, r4]", 16, 4)),
    source="@armlimited2007[§14.4]", note="mesmos bytes da imagem ELF (c1_rom)"))

# FMEM-08: STRB em cada faixa, STRH em cada metade.
for key, off, size, text in (*((f"strb_{k}", k, 1, f"strb r3, [r2, #{k}]") for k in range(4)),
                             ("strh_0", 0, 2, "strh r3, [r2, #0]"), ("strh_2", 2, 2, "strh r3, [r2, #2]")):
    def o8(vec, off=off, size=size):
        m = Mem()
        m.store(12, vec[0], 4)
        m.store(12 + off, vec[1], size)
        return {"word": m.load(12, 4)}
    FORMS.append(Form(f"FMEM-08.{key}", "FMEM-08", f"v_fmem08_{key}",
                      (rows((0xFFFF_FFFF, 0x0000_0000)), rows((0x0000_005A, 0x1234_A5C3))), ("word",),
                      o8, (ins(text, 16),), source="@armlimited2007[§2.4]"))
