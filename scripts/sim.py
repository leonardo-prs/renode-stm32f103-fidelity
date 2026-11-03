"""Execução do Renode e registro do ambiente, comuns a todos os casos.

Cada execução é um processo novo do Renode, sem GDB. `--port -1` faz o
monitor rodar o script direto, e o `quit` no fim do script encerra o
processo (com `--port N` o Renode espera um cliente telnet).
"""
from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = "renode/stm32f103_hsi8.repl"     # plataforma do projeto
MIPS = 8                                    # 1 instrução por ciclo de 8 MHz
QUANTUM = "0.000000125"                     # 125 ns
NS_PER_TICK = 125


def machine(elf: Path) -> list[str]:
    """Linhas do .resc que criam a máquina do projeto e carregam o ELF."""
    return ['mach create "stm32f103"',
            f"machine LoadPlatformDescription @{PLATFORM}",
            f'emulation SetGlobalQuantum "{QUANTUM}"',
            f"sysbus.cpu PerformanceInMips {MIPS}",
            f"sysbus LoadELF @{elf}"]


def run(resc: Path, log: Path, timeout_s: float = 300) -> None:
    """Executa o script; falha se o Renode não terminar normalmente ou se
    algum gancho em Python der erro."""
    with log.open("w") as f:
        proc = subprocess.run(["renode", "--disable-xwt", "--plain", "--port", "-1", "-e", f"i @{resc}"],
                              stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=ROOT, timeout=timeout_s)
    if proc.returncode != 0:
        raise RuntimeError(f"Renode terminou com código {proc.returncode} (ver {log})")
    if "Python runtime error" in log.read_text(errors="replace"):
        raise RuntimeError(f"erro num gancho em Python (ver {log})")


def symbols(elf: Path) -> dict[str, int]:
    """Endereços dos símbolos do ELF (bit Thumb removido)."""
    out = subprocess.run(["arm-none-eabi-nm", str(elf)], check=True, capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) & ~1 for p in (line.split() for line in out.splitlines()) if len(p) == 3}


def environment(elf: Path) -> dict[str, str]:
    """O que identifica uma campanha: ELF, Renode, revisão do código e data."""
    ver = subprocess.run(["renode", "--version"], capture_output=True, text=True).stdout.split("\n")[0].strip()
    rev = subprocess.run(["jj", "log", "--no-graph", "-r", "@", "-T", 'change_id.short() ++ " " ++ commit_id.short()'],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"elf": str(elf.relative_to(ROOT)),
            "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "renode": ver,
            "revisao": rev or "?",
            "data": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
