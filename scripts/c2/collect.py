"""Coleta no Renode do C2 #oD: um processo novo por execução, sem GDB e sem porta.

O .resc de cada execução é gerado aqui e gravado junto dos dados: a mesma
plataforma e o perfil R1 do Q-01 (renode/stm32f103_hsi8.repl, 8 MIPS,
quantum 125 ns), o bloco de parâmetros do caso gravado na SRAM com a
simulação parada (antes da partida) e os instrumentos da variante:

  bare   só o gancho de fim (c2_done), que lê da memória o que o firmware viu;
         é a execução sem observador externo durante o caso
  hooks  + observador externo: ganchos de endereço (pontos marcados,
         tratadores, c2_fault), de início e de fim de interrupção e de
         escrita nos registradores do NVIC/SCB
  full   + traço de execução do Renode (formato PC)

Os ganchos só LEEM estado (registradores, memória, tempo virtual, contador
de instruções) e escrevem em arquivo no host ("observar não pode mudar o
observado", 03-quadro-comum.typ); a comparação entre variantes confere isso.

Registro do observador (events.txt, uma linha por evento, em ordem):
  P pc vt instr id  iser0 iser1 ispr0 ispr1 iabr0 iabr1 icsr  basepri primask
  H pc vt instr xpsr iabr0 iabr1 ispr0 ispr1      (1ª instrução de um tratador)
  B idx vt instr pc xpsr                          (início de interrupção)
  E idx vt instr pc xpsr                          (fim de interrupção)
  W addr value vt instr pc                        (escrita de palavra no NVIC/SCB)
  F pc vt instr xpsr                              (c2_fault: execução inválida)
vt em ns de tempo virtual; instr = instruções executadas pelo núcleo.
Caracterização dos ganchos no Renode 1.17.0 (piloto do C2-09, ver
desenvolvimento/c2.typ): o índice de B não é o número da exceção (o número
vem do IPSR lido em H) e o tempo virtual em B e E fica um tick atrás das
instruções contadas.
"""
from __future__ import annotations

from pathlib import Path

from . import catalog as K
from obs.elf import ROOT, Elf
from obs.renode import CollectError, renode_version, revision, run_renode  # noqa: F401

PRESET = "c2-od"
PLATFORM = "renode/stm32f103_hsi8.repl"
MIPS = 8
QUANTUM = "0.000000125"
NS_PER_TICK = 125
TIMEOUT_S = 300.0
VARIANTS = {"bare": (False, False), "hooks": (True, False), "full": (True, True)}

NVIC_STATE = (0xE000E100, 0xE000E104, 0xE000E200, 0xE000E204, 0xE000E300, 0xE000E304, 0xE000ED04)
# Escritas de palavra observadas: ISER/ICER/ISPR/ICPR (0 e 1), STIR, VTOR, AIRCR.
WATCH = (0xE000E100, 0xE000E104, 0xE000E180, 0xE000E184, 0xE000E200, 0xE000E204,
         0xE000E280, 0xE000E284, 0xE000EF00, 0xE000ED08, 0xE000ED0C)
REG_XPSR, REG_BASEPRI, REG_PRIMASK = 25, 19, 28     # CortexMRegisters (Renode)

_HEAD = "f = open(r'{out}', 'a')\nvt = machine.ElapsedVirtualTime.TimeElapsed.Ticks\nrd = machine.SystemBus.ReadDoubleWord\n"
POINT_PY = _HEAD + (
    "st = ' '.join('%x' % rd(a) for a in ({state}))\n"
    "f.write('P %x %d %d %x %s %x %x\\n' % (pc, vt, self.ExecutedInstructions, self.GetRegister(0).RawValue,"
    " st, self.GetRegister({basepri}).RawValue, self.GetRegister({primask}).RawValue))\nf.close()\n")
HANDLER_PY = _HEAD + (
    "f.write('H %x %d %d %x %x %x %x %x\\n' % (pc, vt, self.ExecutedInstructions, self.GetRegister({xpsr}).RawValue,"
    " rd(0xE000E300), rd(0xE000E304), rd(0xE000E200), rd(0xE000E204)))\nf.close()\n")
IRQ_PY = _HEAD + (
    "f.write('{tag} %d %d %d %x %x\\n' % (exceptionIndex, vt, self.ExecutedInstructions, self.PC.RawValue,"
    " self.GetRegister({xpsr}).RawValue))\nf.close()\n")
WRITE_PY = ("f = open(r'{out}', 'a')\n"
            "f.write('W %x %x %d %d %x\\n' % (address, value, self.Machine.ElapsedVirtualTime.TimeElapsed.Ticks,"
            " cpu.ExecutedInstructions, cpu.PC.RawValue))\nf.close()\n")
FAULT_PY = _HEAD + ("f.write('F %x %d %d %x\\n' % (pc, vt, self.ExecutedInstructions,"
                    " self.GetRegister({xpsr}).RawValue))\nf.close()\n")
DONE_PY = """f = open(r'{out}', 'w')
rd = machine.SystemBus.ReadDoubleWord
f.write('status %d\\n' % rd(0x{status:x}))
for i in range({n}):
    f.write('rec %d %s\\n' % (i, ' '.join('%d' % rd(0x{rec:x} + 4 * ({nrec} * i + k)) for k in range({nrec}))))
f.write('served %s\\n' % ' '.join('%d' % rd(0x{served:x} + 4 * k) for k in range({nirq})))
f.close()
"""
RAW = ("events.txt", "mem.txt", "trace.txt")


def param_words(case: str, points: list[K.Point]) -> list[tuple[int, int]]:
    """(deslocamento em c2_param, valor) de cada palavra gravada pelo monitor."""
    words = [(0, K.MAGIC), (4, K.CASES[case]), (8, len(points)), (12, 0)]
    for p in points:
        for k, v in enumerate(p.args):
            words.append((16 + 4 * (K.N_ARGS * p.index + k), v))
    return words


def write_resc(run_dir: Path, fw: Elf, case: str, points: list[K.Point], variant: str,
               run_for_s: float) -> Path:
    hooks, trace = VARIANTS[variant]
    run_dir.mkdir(parents=True, exist_ok=True)
    s = fw.symbols
    ev = run_dir / "events.txt"
    fmt = dict(out=ev, xpsr=REG_XPSR)
    scripts = {
        "point": POINT_PY.format(state=", ".join(f"0x{a:08x}" for a in NVIC_STATE),
                                 basepri=REG_BASEPRI, primask=REG_PRIMASK, **fmt),
        "handler": HANDLER_PY.format(**fmt),
        "begin": IRQ_PY.format(tag="B", **fmt),
        "end": IRQ_PY.format(tag="E", **fmt),
        "write": WRITE_PY.format(out=ev),
        "fault": FAULT_PY.format(**fmt),
        "done": DONE_PY.format(out=run_dir / "mem.txt", status=s["c2_status"], rec=s["c2_rec"],
                               served=s["c2_served"], n=len(points), nrec=K.N_REC, nirq=K.N_IRQ),
    }
    for name, text in scripts.items():
        (run_dir / f"{name}.py").write_text(text)

    def run_py(name: str) -> str:
        return f"\"exec(open(r'{run_dir / (name + '.py')}').read())\""

    lines = [f"# C2 #oD, caso {case}, variante {variant} (gerado por scripts/c2/collect.py)",
             'mach create "stm32f103"',
             f"machine LoadPlatformDescription @{PLATFORM}",
             f'emulation SetGlobalQuantum "{QUANTUM}"',
             f"sysbus.cpu PerformanceInMips {MIPS}",
             f"sysbus LoadELF @{fw.path}"]
    lines += [f"sysbus WriteDoubleWord 0x{s['c2_param'] + off:08x} 0x{v:08x}"
              for off, v in param_words(case, points)]
    if hooks:
        lines += [f"sysbus.cpu AddHook 0x{s['c2_point']:08x} {run_py('point')}",
                  f"sysbus.cpu AddHook 0x{s['c2_irq_handler']:08x} {run_py('handler')}",
                  f"sysbus.cpu AddHookAtInterruptBegin {run_py('begin')}",
                  f"sysbus.cpu AddHookAtInterruptEnd {run_py('end')}"]
        lines += [f"sysbus AddWatchpointHook 0x{a:08x} DoubleWord Write {run_py('write')}" for a in WATCH]
    lines += [f"sysbus.cpu AddHook 0x{s['c2_fault']:08x} {run_py('fault')}",
              f"sysbus.cpu AddHook 0x{s['c2_done']:08x} {run_py('done')}"]
    if trace:
        lines.append(f'sysbus.cpu CreateExecutionTracing "c2" @{run_dir / "trace.txt"} PC')
    lines += [f'emulation RunFor "{run_for_s:.6f}"', "quit", ""]
    resc = run_dir / "run.resc"
    resc.write_text("\n".join(lines))
    return resc


def run(run_dir: Path, fw: Elf, case: str, points: list[K.Point], variant: str, run_for_s: float,
        timeout_s: float = TIMEOUT_S) -> None:
    """Executa uma variante num processo novo do Renode (obs.renode)."""
    for stale in RAW:
        (run_dir / stale).unlink(missing_ok=True)
    resc = write_resc(run_dir, fw, case, points, variant, run_for_s)
    run_renode(resc, run_dir, "mem.txt", f"c2_done não alcançado em {run_for_s} s", timeout_s)
