"""FAL — acesso desalinhado (src/c1/func/fal.S)."""
from __future__ import annotations

from ..catalog import F_FAULT, F_MEM, Form
from ..vectors import rows
from .common import UNALIGNED, Mem, fault, ins, no_fault
from .fmem import rom

SRC = "@armlimited2021[§A3.2.1]"
SENTINEL = 0xDEAD_BEEF
SIZES = {"ldr": (4, False), "ldrh": (2, False), "ldrsh": (2, True), "str": (4, None), "strh": (2, None)}
OFFSETS = {"ldr": (0, 1, 2, 3), "ldrh": (0, 1, 3), "ldrsh": (0, 1, 3), "str": (0, 1, 2, 3),
           "strh": (0, 1, 3)}


def ramp() -> Mem:
    m = Mem()
    for k in range(32):
        m.b[k] = 0x80 + k
    return m


def _unal(op: str, trap: bool):
    size, signed = SIZES[op]
    routine = f"v_fal0{3 if trap else 1}_{op}"

    def oracle(vec):
        off, ap = vec
        m = ramp()
        if trap and off % size:
            # A instrução que falha não completa: Rt (destino da carga ou
            # valor da escrita) e a memória ficam como estavam.
            rt = 0xDDCC_BBAA if op == "str" else SENTINEL
            return {"rt": rt, **m.fields(), **fault(UNALIGNED, f"{routine}_x0", apsr=ap)}
        if signed is None:                       # escrita
            value = 0xDDCC_BBAA if op == "str" else SENTINEL
            m.store(8 + off, value, size)
            rt = value
        else:
            rt = m.load(8 + off, size, signed)
        return {"rt": rt, **m.fields(), **no_fault(f"{routine}_land")}
    return Form(f"FAL-0{3 if trap else 1}.{op}", f"FAL-0{3 if trap else 1}", routine,
                (rows(OFFSETS[op]), rows((0x0000_0000,))), ("rt",), oracle,
                (ins(f"{op} r3, [r2, r4]", 16),), flags=F_MEM | F_FAULT,
                source=f"{SRC} @armlimited2007[Tab. 14-2]" if not trap
                else "@stmicroelectronics2024[§4.4.7]",
                note="CCR.UNALIGN_TRP = 1 é precondição" if trap else "")


FORMS = [_unal(op, False) for op in SIZES] + [_unal(op, True) for op in SIZES]
for op, offs in (("ldr", (1, 2, 3)), ("ldrh", (1, 3))):
    size = 4 if op == "ldr" else 2
    FORMS.append(Form(f"FAL-02.{op}", "FAL-02", f"v_fal02_{op}", (rows(offs),), ("rt",),
                      lambda vec, size=size: {"rt": rom(vec[0], size)}, (ins(f"{op} r3, [r2, r4]", 16),),
                      source="@armlimited2007[§14.4]"))

for key, text, width in (("ldm", "ldmia.w r2, {r3, r4}", 32), ("stm", "stmia r2!, {r3}", 16),
                         ("ldrd", "ldrd r3, r4, [r2]", 32), ("strd", "strd r3, r4, [r2]", 32),
                         ("ldrex", "ldrex r3, [r2]", 32), ("ldrexh", "ldrexh r3, [r2]", 32)):
    def o4(vec, key=key):
        return {"rt": SENTINEL, **fault(UNALIGNED, f"v_fal04_{key}_x0", apsr=vec[1])}
    FORMS.append(Form(f"FAL-04.{key}", "FAL-04", f"v_fal04_{key}", (rows((0, 1)), rows((0x0000_0000,))),
                      ("rt",), o4, (ins(text, width),), flags=F_FAULT, source=SRC,
                      note="falta com UNALIGN_TRP = 0 e = 1"))
