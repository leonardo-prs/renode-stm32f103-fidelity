"""Coleta do Q-02 no Renode: um processo novo por execução (obs.renode).

Mesma plataforma e perfil R1 do Q-01 e do C2 (renode/stm32f103_hsi8.repl,
8 MIPS, quantum 125 ns). Em TODAS as variantes há os estímulos do caso,
que fazem parte do experimento e não da observação:

  - monitor, antes da partida: grava q02_magic (.noinit);
  - gancho de estímulo em q02_trigger: grava HOOK_VALUE em q02_mbox2;
  - monitor, com a simulação parada nos instantes PAUSES_NS: lê q02_echo e
    q02_mbox, registra tempo virtual, instruções e PC, e grava o valor da
    pausa em q02_mbox. A pausa é o fim de um `emulation RunFor`.

Variantes de observação (o que se verifica):
  bare   nenhum gancho de observação (só o de fim, que lê q02_rec)
  hooks  ganchos de endereço (pontos, 1ª instrução dos tratadores), de
         início e fim de exceção e de escrita (q02_sink[0] e ICSR)
  full   + traço de execução (formato PC)

Registros (uma linha por evento):
  events.txt  P pc vt instr id
              H pc vt instr xpsr shcsr                (1ª instrução de tratador)
              B idx vt instr pc xpsr shcsr            (início de exceção)
              E idx vt instr pc xpsr shcsr            (fim de exceção)
              W addr value width vt instr pc          (escrita vigiada)
              F pc vt instr xpsr                      (q02_fault; todas as variantes)
  stim.txt    S vt instr pc                           (gancho de estímulo)
              M vt instr pc echo mbox                 (monitor na pausa, antes de gravar)
  mem.txt     status + palavras de q02_rec
  trace.txt   um PC por instrução executada (full)
vt em ns de tempo virtual; instr = instruções executadas pelo núcleo.
"""
from __future__ import annotations

from pathlib import Path

from obs.elf import Elf
from obs.renode import TIMEOUT_S, run_renode

from . import spec

PRESET = "q02"
PLATFORM = "renode/stm32f103_hsi8.repl"
MIPS = 8
QUANTUM = "0.000000125"
NS_PER_TICK = 125
VARIANTS = {"bare": (False, False), "hooks": (True, False), "full": (True, True)}
REG_XPSR = 25                                   # CortexMRegisters (Renode)
RAW = ("events.txt", "stim.txt", "mem.txt", "trace.txt")

_HEAD = "f = open(r'{out}', 'a')\nvt = machine.ElapsedVirtualTime.TimeElapsed.Ticks\n"
POINT_PY = _HEAD + "f.write('P %x %d %d %x\\n' % (pc, vt, self.ExecutedInstructions, self.GetRegister(0).RawValue))\nf.close()\n"
HANDLER_PY = _HEAD + ("f.write('H %x %d %d %x %x\\n' % (pc, vt, self.ExecutedInstructions,"
                      " self.GetRegister({xpsr}).RawValue, machine.SystemBus.ReadDoubleWord({shcsr})))\nf.close()\n")
EXC_PY = _HEAD + ("f.write('{tag} %d %d %d %x %x %x\\n' % (exceptionIndex, vt, self.ExecutedInstructions,"
                  " self.PC.RawValue, self.GetRegister({xpsr}).RawValue, machine.SystemBus.ReadDoubleWord({shcsr})))\n"
                  "f.close()\n")
WRITE_PY = ("f = open(r'{out}', 'a')\n"
            "f.write('W %x %x %s %d %d %x\\n' % (address, value, width, self.Machine.ElapsedVirtualTime.TimeElapsed.Ticks,"
            " cpu.ExecutedInstructions, cpu.PC.RawValue))\nf.close()\n")
FAULT_PY = _HEAD + "f.write('F %x %d %d %x\\n' % (pc, vt, self.ExecutedInstructions, self.GetRegister({xpsr}).RawValue))\nf.close()\n"
STIM_PY = ("machine.SystemBus.WriteDoubleWord(0x{mbox2:x}, 0x{value:x})\n"
           "f = open(r'{out}', 'a')\n"
           "f.write('S %d %d %x\\n' % (machine.ElapsedVirtualTime.TimeElapsed.Ticks, self.ExecutedInstructions, pc))\n"
           "f.close()\n")
# Comando `python` do monitor: `monitor` está no escopo (simulação parada).
PAUSE_PY = ("m = monitor.Machine\nc = m['sysbus.cpu']\nb = m.SystemBus\n"
            "f = open(r'{out}', 'a')\n"
            "f.write('M %d %d %x %x %x\\n' % (m.ElapsedVirtualTime.TimeElapsed.Ticks, c.ExecutedInstructions,"
            " c.PC.RawValue, b.ReadDoubleWord(0x{echo:x}), b.ReadDoubleWord(0x{mbox:x})))\n"
            "f.close()\n"
            "b.WriteDoubleWord(0x{mbox:x}, 0x{value:x})\n")
DONE_PY = """f = open(r'{out}', 'w')
rd = machine.SystemBus.ReadDoubleWord
f.write('rec %s\\n' % ' '.join('%d' % rd(0x{rec:x} + 4 * k) for k in range({n})))
f.close()
"""


def watched(fw: Elf) -> tuple[int, ...]:
    return (fw.symbols["q02_sink"], spec.ICSR)


def _seconds(ns: int) -> str:
    return f"{ns / 1e9:.9f}"


def write_resc(run_dir: Path, fw: Elf, variant: str) -> Path:
    hooks, trace = VARIANTS[variant]
    run_dir.mkdir(parents=True, exist_ok=True)
    s = fw.symbols
    ev, st = run_dir / "events.txt", run_dir / "stim.txt"
    fmt = dict(out=ev, xpsr=REG_XPSR, shcsr=f"0x{spec.SHCSR:08x}")
    scripts = {
        "point": POINT_PY.format(**fmt),
        "handler": HANDLER_PY.format(**fmt),
        "begin": EXC_PY.format(tag="B", **fmt),
        "end": EXC_PY.format(tag="E", **fmt),
        "write": WRITE_PY.format(out=ev),
        "fault": FAULT_PY.format(**fmt),
        "stim": STIM_PY.format(out=st, mbox2=s["q02_mbox2"], value=spec.HOOK_VALUE),
        "done": DONE_PY.format(out=run_dir / "mem.txt", rec=s["q02_rec"], n=spec.REC_WORDS),
    }
    for k, value in enumerate(spec.PAUSE_VALUES):
        scripts[f"pause{k}"] = PAUSE_PY.format(out=st, echo=s["q02_echo"], mbox=s["q02_mbox"], value=value)
    for name, text in scripts.items():
        (run_dir / f"{name}.py").write_text(text)

    def py(name: str) -> str:
        return f"\"exec(open(r'{run_dir / (name + '.py')}').read())\""

    lines = [f"# Q-02, variante {variant} (gerado por scripts/q02/collect.py)",
             'mach create "stm32f103"',
             f"machine LoadPlatformDescription @{PLATFORM}",
             f'emulation SetGlobalQuantum "{QUANTUM}"',
             f"sysbus.cpu PerformanceInMips {MIPS}",
             f"sysbus LoadELF @{fw.path}",
             f"sysbus WriteDoubleWord 0x{s['q02_magic']:08x} 0x{spec.MAGIC:08x}",
             f"sysbus.cpu AddHook 0x{s['q02_trigger']:08x} {py('stim')}"]
    if hooks:
        lines += [f"sysbus.cpu AddHook 0x{s['q02_point']:08x} {py('point')}",
                  f"sysbus.cpu AddHook 0x{s['PendSV_Handler']:08x} {py('handler')}",
                  f"sysbus.cpu AddHook 0x{s['SysTick_Handler']:08x} {py('handler')}",
                  f"sysbus.cpu AddHookAtInterruptBegin {py('begin')}",
                  f"sysbus.cpu AddHookAtInterruptEnd {py('end')}"]
        lines += [f"sysbus AddWatchpointHook 0x{a:08x} DoubleWord Write {py('write')}" for a in watched(fw)]
    lines += [f"sysbus.cpu AddHook 0x{s['q02_fault']:08x} {py('fault')}",
              f"sysbus.cpu AddHook 0x{s['q02_done']:08x} {py('done')}"]
    if trace:
        lines.append(f'sysbus.cpu CreateExecutionTracing "q02" @{run_dir / "trace.txt"} PC')
    t = 0
    for k, pause in enumerate(spec.PAUSES_NS):
        lines += [f'emulation RunFor "{_seconds(pause - t)}"', f"python {py(f'pause{k}')}"]
        t = pause
    lines += [f'emulation RunFor "{_seconds(spec.RUN_NS - t)}"', "quit", ""]
    resc = run_dir / "run.resc"
    resc.write_text("\n".join(lines))
    return resc


def run(run_dir: Path, fw: Elf, variant: str, timeout_s: float = TIMEOUT_S) -> None:
    for stale in RAW:
        (run_dir / stale).unlink(missing_ok=True)
    resc = write_resc(run_dir, fw, variant)
    run_renode(resc, run_dir, "mem.txt", f"q02_done não alcançado em {spec.RUN_NS} ns", timeout_s)
