"""FSY — registradores especiais e privilégio (src/c1/func/fsy.S)."""
from __future__ import annotations

from ..catalog import F_FAULT, Form
from ..vectors import V32, rows
from .common import (BFARVALID, HFSR_FORCED, IPSR_BUS, IPSR_HARD, PRECISERR, T_BIT, UNDEFINSTR,
                     apsr_out, fault, ins)

SRC = "@armlimited2021"
FLAGS = (0x0000_0000, 0xF800_0000)
NO_APSR = 0x07FF_FFFF        # no tratador o APSR é UNKNOWN (§B1.5.6, ExceptionTaken)


def _form(name, routine, axes, outs, oracle, insns, level="N2", flags=0, source=f"{SRC}[§B5.2.2–3]",
          note=""):
    return Form(name, name.split(".")[0], routine, axes, outs, oracle, insns, flags=flags,
                level=level, source=source, note=note)


FORMS = [
    _form("FSY-01", "v_fsy01", (rows(V32),), ("read",), lambda v: {"read": apsr_out(v[0])},
          (ins("msr CPSR_f, r2", 32, 0), ins("mrs r3, CPSR", 32, 1)), level="N1",
          note="o objdump usa os nomes do perfil A (CPSR_f = APSR_nzcvq)"),
    _form("FSY-02", "v_fsy02", (rows(FLAGS),),
          ("ipsr_t", "epsr_t", "xpsr_t", "ipsr_h", "epsr_h", "xpsr_h"),
          lambda v: {"ipsr_t": 0, "epsr_t": 0, "xpsr_t": apsr_out(v[0]), "ipsr_h": 11, "epsr_h": 0,
                     "xpsr_h": (11, NO_APSR)},
          tuple(ins(t, 32, k) for k, t in enumerate(
              ("mrs r3, IPSR", "mrs r3, EPSR", "mrs r3, PSR") * 2)), level="N1",
          note="EPSR lê 0 por MRS; IPSR = 11 no SVC"),
    _form("FSY-03.thread", "v_fsy03_thread", (rows((0,)),),
          tuple(f"{m}_{k}" for m in ("pm", "fm") for k in ("msr1", "msr0", "cpsid", "cpsie")),
          lambda v: dict(zip(tuple(f"{m}_{k}" for m in ("pm", "fm") for k in
                                   ("msr1", "msr0", "cpsid", "cpsie")), (1, 0, 1, 0) * 2)),
          (ins("msr PRIMASK, r2", 32, 0), ins("cpsid i", 16, 1), ins("cpsie i", 16, 2),
           ins("cpsid f", 16, 3), ins("cpsie f", 16, 4)), level="N1",
          source=f"{SRC}[§B5.2.1–3]"),
    _form("FSY-03.ret", "v_fsy03_ret", (rows((0,)),), ("fm_handler", "fm_thread"),
          lambda v: {"fm_handler": 1, "fm_thread": 0}, (ins("cpsid f", 16, 0),), level="N1",
          source=f"{SRC}[§B1.5.8]",
          note="\"Returning from any exception except NMI clears FAULTMASK to 0\""),
    _form("FSY-03.hf", "v_fsy03_hf", (rows((0,)),), ("fm_hardfault",),
          lambda v: {"fm_hardfault": 0, **fault(UNDEFINSTR, "v_fsy03_hf_x0", hfsr=HFSR_FORCED,
                                                  ipsr=IPSR_HARD, xpsr=(T_BIT, NO_APSR))},
          (ins("udf #0", 16, 0), ins("cpsid f", 16, 1)), level="N1", flags=F_FAULT,
          source=f"{SRC}[§B1.4.3, §B5.2.1]",
          note="o HardFault (prioridade −1) não pode ligar FAULTMASK"),
    _form("FSY-04", "v_fsy04", (rows((0,)),), ("bp_ff", "max80", "max20", "max0", "max80_from0"),
          lambda v: {"bp_ff": 0xF0, "max80": 0x40, "max20": 0x20, "max0": 0x20, "max80_from0": 0x80},
          (ins("msr BASEPRI, r2", 32, 0), ins("msr BASEPRI_MAX, r2", 32, 1)),
          source=f"{SRC}[§B5.2.3] @stmicroelectronics2024[§2.1.3]",
          note="só os bits [7:4] existem no STM32"),
    _form("FSY-05", "v_fsy05", (rows((0x2000_1000, 0x2000_4FFC, 0x2000_2008)),), ("msp", "psp"),
          lambda v: {"msp": v[0], "psp": v[0]},
          (ins("msr MSP, r2", 32, 0), ins("mrs r3, MSP", 32, 1), ins("msr PSP, r2", 32, 2)),
          source=f"{SRC}[§A5.1.3, §B5.2.2–3]", note="escrita com bits [1:0] ≠ 0 é X"),
    _form("FSY-06", "v_fsy06", (rows((0,)),), ("sp", "psp", "pushed", "sp_push", "msp_delta"),
          lambda v: {"sp": "_epsp", "psp": "_epsp", "pushed": 0xC0FF_EE00, "sp_push": "_epsp-4",
                     "msp_delta": 0},
          (ins("msr CONTROL, r2", 32, 0),), source=f"{SRC}[§B5.2.3]"),
    _form("FSY-07", "v_fsy07", (rows((0,)),),
          ("control_u", "primask_u", "basepri_u", "faultmask_u", "cpsid_u", "control_msr_u",
           "control_p", "primask_p", "basepri_p", "faultmask_p"),
          lambda v: {"control_u": 1, "primask_u": 0, "basepri_u": 0, "faultmask_u": 0, "cpsid_u": 0,
                     "control_msr_u": 1, "control_p": 0, "primask_p": 0, "basepri_p": 0,
                     "faultmask_p": 0},
          (ins("msr PRIMASK, r2", 32, 0), ins("cpsid i", 16, 1), ins("msr CONTROL, r2", 32, 2)),
          note="escritas sem privilégio ignoradas, sem falta; MRS das máscaras lê 0"),
    _form("FSY-08", "v_fsy08", (rows(FLAGS),), ("rt",),
          lambda v: {"rt": 0xDEAD_BEEF, **fault(PRECISERR | BFARVALID, "v_fsy08_x0", apsr=v[0],
                                                 ipsr=IPSR_BUS, bfar=0xE000_ED00)},
          (ins("ldr r3, [r2, #0]", 16),), flags=F_FAULT,
          source=f"{SRC}[§B3.1.1] @armlimited2007[§8.1]",
          note="na r1p1 BFAR e MMFAR são o mesmo registrador: o MMFAR bruto é caracterização"),
]
