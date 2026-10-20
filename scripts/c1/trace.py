"""Nível de instrução: traço por passo único (stepi), placa e Renode.

Com C1_HOST_TRACE o firmware chama cada rotina UMA vez (o 1º vetor de cada
forma no c1-func; o bloco K de cada variante no c1-cycle). O GDB para em
c1_call_go (o BLX) e executa stepi até c1_call_back, gravando o PC de cada
instrução: a sequência dinâmica exatamente como executou, inclusive a
entrada e o retorno de exceções e o tratador de faltas.

O MESMO script roda contra o OpenOCD (placa) e contra o servidor GDB do
Renode. O traço é feito em execuções separadas das de medição: o CYCCNT não
conta com o núcleo parado (TRM §11.5.1) e cada parada esvazia o pipeline.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import targets
from .disasm import symbols

STEP_LIMIT = 4000


def gdb_script(port: int, reset: str, host: targets.HostBlock, sym: dict[str, int]) -> str:
    go, back, fin, done = (sym[s] & ~1 for s in ("c1_call_go", "c1_call_back", "c1_finish",
                                                 "c1_complete"))
    return "\n".join([
        "set pagination off", "set confirm off", "set remotetimeout 15",
        f"target extended-remote 127.0.0.1:{port}", reset.strip(),
        "hbreak *main", "continue", host.gdb_set(host.flags).strip(), "delete",
        f"hbreak *0x{go:x}", f"hbreak *0x{done:x}", "set $n = 0", "continue",
        f"while (((unsigned int)$pc & ~1) != 0x{done:x})",
        '  printf "CALL %d\\n", $n',
        "  set $k = 0",
        # Também para em c1_finish: um caso terminal termina dentro do
        # tratador de faltas e nunca volta a c1_call_back (o resto, a
        # varredura da pilha em c1_finish, não é do caso).
        f"  while ((((unsigned int)$pc & ~1) != 0x{back:x}) && (((unsigned int)$pc & ~1) != 0x{fin:x})"
        f" && (((unsigned int)$pc & ~1) != 0x{done:x}) && ($k < {STEP_LIMIT}))",
        '    printf "PC %x\\n", $pc',
        "    stepi",
        "    set $k = $k + 1",
        "  end",
        '  printf "END %d\\n", $k',
        "  set $n = $n + 1",
        f"  if (((unsigned int)$pc & ~1) != 0x{done:x})",
        "    continue",
        "  end",
        "end",
        'printf "C1_PC=0x%x\\n", $pc',
        'printf "C1_COMPLETE=0x%x\\n", &c1_complete',
        "delete", "detach", "quit 0", ""])


def parse(text: str) -> list[list[int]]:
    calls = []
    for m in re.finditer(r"^CALL (\d+)\n(.*?)^END (\d+)$", text, re.S | re.M):
        pcs = [int(x, 16) for x in re.findall(r"^PC ([0-9a-f]+)$", m[2], re.M)]
        if len(pcs) != int(m[3]) or int(m[1]) != len(calls):
            raise targets.TargetError(f"traço malformado na chamada {m[1]}")
        if len(pcs) >= STEP_LIMIT:
            raise targets.TargetError(f"chamada {m[1]}: limite de {STEP_LIMIT} passos")
        calls.append(pcs)
    return calls


def summarize(calls: list[list[int]]) -> list[dict]:
    return [{"count": len(pcs), "sha256": hashlib.sha256(" ".join(f"{p:x}" for p in pcs).encode())
             .hexdigest()[:16], "pcs": [f"{p:x}" for p in pcs]} for pcs in calls]


def trace_hw(bench: targets.Bench, elf: Path, out: Path, host: targets.HostBlock,
             timeout_s: float) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    sym = symbols(elf)
    try:
        text = targets.run_gdb(elf, gdb_script(targets.HW_GDB_PORT, "monitor reset halt", host, sym),
                               out / "stepi.log", timeout_s)
        targets.check_stopped_at_complete(text)
    finally:
        bench.recover(elf, out)
    return summarize(parse(text))


def trace_renode(elf: Path, out: Path, host: targets.HostBlock, profile: str, timeout_s: float,
                 port_base: int = targets.RENODE_PORT_BASE) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    sym = symbols(elf)
    with targets.RenodeSession(elf, out, profile, port_base) as session:
        text = targets.run_gdb(elf, gdb_script(session.port, "", host, sym), out / "stepi.log",
                               timeout_s, watch=session.abort_watch())
        targets.check_stopped_at_complete(text)
    return summarize(parse(text))
