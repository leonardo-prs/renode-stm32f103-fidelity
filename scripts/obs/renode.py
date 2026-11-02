"""Uma execução = um processo novo do Renode, sem GDB e sem porta.

`--port -1`: o monitor roda o script direto e `quit` encerra o processo
(com `--port N` o Renode só executa quando um cliente telnet conecta).
Toda falha aqui é falha do instrumento (EVIDÊNCIA INVÁLIDA), nunca resultado.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .elf import ROOT

TIMEOUT_S = 300.0


class CollectError(RuntimeError):
    """Falha do instrumento: vira EVIDÊNCIA INVÁLIDA, nunca divergência."""


def run_renode(resc: Path, run_dir: Path, must_exist: str, what: str,
               timeout_s: float = TIMEOUT_S) -> None:
    """Executa `resc`; exige código 0, nenhum erro de Python nos ganchos e o
    arquivo `must_exist` (gravado pelo gancho de fim) em `run_dir`."""
    log_path = run_dir / "renode.log"
    with log_path.open("w") as log:
        try:
            proc = subprocess.run(["renode", "--disable-xwt", "--plain", "--port", "-1", "-e", f"i @{resc}"],
                                  stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  cwd=ROOT, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            raise CollectError(f"tempo esgotado ({timeout_s:.0f} s)") from None
    if proc.returncode != 0:
        raise CollectError(f"Renode terminou com código {proc.returncode} (ver renode.log)")
    if "Python runtime error" in log_path.read_text(errors="replace"):
        raise CollectError("erro de Python num gancho (ver renode.log)")
    if not (run_dir / must_exist).is_file():
        raise CollectError(f"gancho de fim não executou ({what})")


def renode_version() -> str:
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
