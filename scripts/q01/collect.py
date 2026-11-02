"""Coleta no Renode: um processo novo por execução, sem GDB e sem porta.

O script .resc de cada execução é gerado aqui (e gravado junto dos dados):
mesma plataforma e perfil R1 do C1 (renode/stm32f103_hsi8.repl, 8 MIPS,
quantum 125 ns), mais os instrumentos da variante:

  bare   só o gancho de fim (q01_done), que lê o vetor do CYCCNT da memória;
         é a execução sem observador externo durante a medida
  hooks  + um gancho em cada ponto marcado (PC, tempo virtual, instruções
         executadas pelo núcleo)
  full   + traço de execução do Renode em formato PC

Os ganchos só LEEM estado (tempo virtual, contador de instruções, memória)
e escrevem em arquivo no host, conforme a regra "observar não pode mudar o
observado"; a comparação entre variantes confere isso no próprio caso.

O monitor do Renode chama o código Python do gancho com `machine`, `self`
(a CPU) e `pc` no escopo (Renode, CPU hooks). `ElapsedVirtualTime` é o
tempo virtual da máquina; `TimeInterval.Ticks` é em nanossegundos na 1.17.0.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESET = "q01"
ELF = ROOT / "build" / PRESET / "firmware.elf"
PLATFORM = "renode/stm32f103_hsi8.repl"
MIPS = 8
QUANTUM = "0.000000125"
NS_PER_TICK = 125                       # 1 ciclo de 8 MHz = 1 instrução em R1
RUN_FOR = "0.002"                       # tempo virtual: a sequência acaba em ~0,2 ms
TIMEOUT_S = 180.0
VARIANTS = {"bare": (False, False), "hooks": (True, False), "full": (True, True)}

HOOK_PY = """f = open(r'{out}', 'a')
f.write('%x %d %d\\n' % (pc, machine.ElapsedVirtualTime.TimeElapsed.Ticks, self.ExecutedInstructions))
f.close()
"""
DONE_PY = """f = open(r'{out}', 'w')
n = machine.SystemBus.ReadDoubleWord(0x{count:x})
f.write('%d\\n' % n)
for i in range(min(n, {slots})):
    f.write('%d\\n' % machine.SystemBus.ReadDoubleWord(0x{cyc:x} + 4 * i))
f.close()
"""
FAULT_PY = """f = open(r'{out}', 'a')
f.write('%x %d\\n' % (pc, machine.ElapsedVirtualTime.TimeElapsed.Ticks))
f.close()
"""


class CollectError(RuntimeError):
    """Falha do instrumento: vira EVIDÊNCIA INVÁLIDA, nunca divergência."""


@dataclass(frozen=True)
class Firmware:
    elf: Path
    sha256: str
    symbols: dict[str, int]

    @property
    def points(self) -> list[tuple[int, int]]:
        """[(n, endereço)] dos pontos q01_pN, em ordem de N (= ordem de execução)."""
        pts = [(int(m[1]), a) for s, a in self.symbols.items() if (m := re.fullmatch(r"q01_p(\d+)", s))]
        return sorted(pts)


def load_firmware(elf: Path = ELF) -> Firmware:
    if not elf.is_file():
        raise CollectError(f"ELF ausente: {elf} (cmake --workflow --preset {PRESET})")
    out = subprocess.run(["arm-none-eabi-nm", str(elf)], check=True, capture_output=True, text=True).stdout
    sym = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            sym[parts[2]] = int(parts[0], 16) & ~1
    for need in ("q01_done", "q01_fault", "q01_count", "q01_cyc", "q01_p0"):
        if need not in sym:
            raise CollectError(f"símbolo {need} ausente no ELF")
    return Firmware(elf, hashlib.sha256(elf.read_bytes()).hexdigest(), sym)


def slots(fw: Firmware) -> int:
    out = subprocess.run(["arm-none-eabi-nm", "-S", str(fw.elf)], check=True, capture_output=True,
                         text=True).stdout
    m = re.search(r"^[0-9a-f]+ ([0-9a-f]+) \w q01_cyc$", out, re.M)
    if not m:
        raise CollectError("tamanho de q01_cyc não encontrado")
    return int(m[1], 16) // 4


def write_resc(run_dir: Path, fw: Firmware, variant: str) -> Path:
    hooks, trace = VARIANTS[variant]
    run_dir.mkdir(parents=True, exist_ok=True)
    files = {"hook": HOOK_PY.format(out=run_dir / "hooks.txt"),
             "done": DONE_PY.format(out=run_dir / "mem.txt", count=fw.symbols["q01_count"],
                                    cyc=fw.symbols["q01_cyc"], slots=slots(fw)),
             "fault": FAULT_PY.format(out=run_dir / "fault.txt")}
    for name, text in files.items():
        (run_dir / f"{name}.py").write_text(text)

    def hook(addr: int, name: str) -> str:
        return f"sysbus.cpu AddHook 0x{addr:08x} \"exec(open(r'{run_dir / (name + '.py')}').read())\""

    lines = [f"# Q-01, variante {variant} (gerado por scripts/q01/collect.py)",
             'mach create "stm32f103"',
             f"machine LoadPlatformDescription @{PLATFORM}",
             f'emulation SetGlobalQuantum "{QUANTUM}"',
             f"sysbus.cpu PerformanceInMips {MIPS}",
             f"sysbus LoadELF @{fw.elf}"]
    if hooks:
        lines += [hook(a, "hook") for _, a in fw.points]
    lines += [hook(fw.symbols["q01_done"], "done"), hook(fw.symbols["q01_fault"], "fault")]
    if trace:
        lines.append(f'sysbus.cpu CreateExecutionTracing "q01" @{run_dir / "trace.txt"} PC')
    lines += [f'emulation RunFor "{RUN_FOR}"', "quit", ""]
    resc = run_dir / "run.resc"
    resc.write_text("\n".join(lines))
    return resc


def run(run_dir: Path, fw: Firmware, variant: str, timeout_s: float = TIMEOUT_S) -> None:
    """Executa uma variante. Sem --port: o monitor roda o script direto
    (`--port -1`, ver AGENTS.md) e `quit` encerra o processo."""
    for stale in ("hooks.txt", "mem.txt", "fault.txt", "trace.txt"):
        (run_dir / stale).unlink(missing_ok=True)
    resc = write_resc(run_dir, fw, variant)
    with (run_dir / "renode.log").open("w") as log:
        try:
            proc = subprocess.run(["renode", "--disable-xwt", "--plain", "--port", "-1", "-e", f"i @{resc}"],
                                  stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  cwd=ROOT, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            raise CollectError(f"tempo esgotado ({timeout_s:.0f} s)") from None
    if proc.returncode != 0:
        raise CollectError(f"Renode terminou com código {proc.returncode} (ver renode.log)")
    if not (run_dir / "mem.txt").is_file():
        raise CollectError("gancho de fim não executou (q01_done não alcançado em "
                           f"{RUN_FOR} s de tempo virtual)")


def renode_version() -> str:
    """'Renode v1.17.0 (1.17.0+git…)': 1ª linha + linha `build:` do --version."""
    out = subprocess.run(["renode", "--version"], capture_output=True, text=True, timeout=60).stdout
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    build = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("build:")), "?")
    return f"{lines[0]} ({build})" if lines else "?"


def revision() -> str:
    try:
        return subprocess.run(["jj", "log", "--no-graph", "-r", "@", "-T",
                               'change_id.short() ++ " " ++ commit_id.short()'],
                              cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "?"
