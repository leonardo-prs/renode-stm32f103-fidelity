"""C1 — contagem dinâmica de instruções por stepi (placa e Renode).

Para cada combinação carga × tamanho do c1-timing, a PRIMEIRA execução
(rep 0) é percorrida instrução a instrução pelo GDB: começa em
fid_measure_call (BLX logo após a leitura t0 do CYCCNT) e termina ao chegar
em fid_measure_back (leitura t1). O resultado é a sequência de PCs e o
número exato de instruções executadas dentro do intervalo medido.

O MESMO script GDB roda contra o OpenOCD (placa) e contra o servidor GDB do
Renode. Assim:
  - igualdade das sequências de PC = mesmo caminho dinâmico de instruções
    (evidência do nível "instruction-accurate" para essas cargas);
  - ticks HW / instruções = CPI físico daquele intervalo (contagem medida,
    não inferida);
  - ticks Renode (8 MIPS) / instruções mostra se o modelo temporal é
    exatamente "1 instrução = 1 tick".
As demais repetições têm entradas idênticas, portanto o mesmo caminho.
Este traço é diagnóstico: a placa fica parada a cada instrução, então os
tempos não são medidos aqui (vêm das execuções normais do c1-timing).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import c1, targets


def symbols(elf: Path) -> dict[str, int]:
    out = subprocess.run(["arm-none-eabi-nm", str(elf)], capture_output=True, text=True,
                         check=True).stdout
    return {name: int(addr, 16) for addr, _, name in
            (line.split() for line in out.splitlines() if len(line.split()) == 3)}


def call_plan() -> list[tuple[str, int, int]]:
    """Ordem das chamadas a fid_measure no c1-timing: (carga, n, rep)."""
    plan = [("empty", 0, r) for r in range(c1.REPS)]
    for load in c1.LOADS[1:]:
        for n in c1.SIZES:
            plan += [(load, n, r) for r in range(c1.REPS)]
    return plan


def gdb_script(port: int, reset: str, sym: dict[str, int]) -> str:
    call, back = sym["fid_measure_call"], sym["fid_measure_back"]
    lines = ["set pagination off", "set confirm off", "set remotetimeout 15",
             f"target extended-remote 127.0.0.1:{port}", reset.strip(),
             f"hbreak *0x{call:x}"]
    for load, n, rep in call_plan():
        lines.append("continue")
        if rep != 0:
            continue
        lines += [
            f'printf "BEGIN {load} {n} fn=0x%x arg=%u\\n", $r4, $r0',
            "set $count = 0",
            f"while ($pc != 0x{back:x})",
            '  printf "PC %x\\n", $pc',
            "  stepi",
            "  set $count = $count + 1",
            "end",
            'printf "END count=%u\\n", $count',
        ]
    lines += ["delete", "detach", "quit 0"]
    return "\n".join(line for line in lines if line) + "\n"


def parse(text: str, sym: dict[str, int]) -> dict:
    """{(carga, n): {count, pcs_sha256, first_pcs}}; confere fn/arg."""
    fn_addr = {name.removeprefix("load_"): addr for name, addr in sym.items()
               if name.startswith("load_")}
    out = {}
    for m in re.finditer(r"BEGIN (\w+) (\d+) fn=0x([0-9a-f]+) arg=(\d+)\n(.*?)END count=(\d+)",
                         text, re.S):
        load, n, fn, arg, body, count = m[1], int(m[2]), int(m[3], 16), int(m[4]), m[5], int(m[6])
        expected_fn = fn_addr["div" if load.startswith("div") else load]
        if (fn & ~1) != (expected_fn & ~1) or arg != n:
            raise ValueError(f"traço {load}/{n}: chamada fora da ordem (fn 0x{fn:x}, n {arg})")
        pcs = re.findall(r"^PC ([0-9a-f]+)$", body, re.M)
        if len(pcs) != count:
            raise ValueError(f"traço {load}/{n}: {len(pcs)} PCs para count={count}")
        out[f"{load}/{n}"] = {"load": load, "n": n, "count": count,
                              "pcs_sha256": hashlib.sha256(" ".join(pcs).encode()).hexdigest(),
                              "first_pcs": pcs[:8]}
    expected = {f"{load}/{n}" for load, n, rep in call_plan() if rep == 0}
    if set(out) != expected:
        raise ValueError(f"traços ausentes: {sorted(expected - set(out))}")
    return out


def trace_hw(elf: Path, out_dir: Path, timeout_s: float = 3600) -> dict:
    """Traço na placa: OpenOCD próprio, grava o ELF e roda o MESMO script GDB.

    Custo medido: ~25–30 passos/s (o passo único via ST-Link domina; um laço
    Tcl dentro do OpenOCD não foi mais rápido). ~41 mil instruções ≈ 25 min.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    sym = symbols(elf)
    with targets.Bench(out_dir) as bench:
        bench.flash(elf, out_dir / "flash.log")
        text = targets.run_gdb(elf, gdb_script(targets.HW_GDB_PORT, "monitor reset halt", sym),
                               out_dir / "stepi.log", timeout_s)
        bench.recover(elf, out_dir)
    return _save(parse(text, sym), out_dir)


def trace_renode(elf: Path, out_dir: Path, timeout_s: float = 1800) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sym = symbols(elf)
    with targets.RenodeSession(elf, out_dir) as session:
        text = targets.run_gdb(elf, gdb_script(session.port, "", sym),
                               out_dir / "stepi.log", timeout_s)
    return _save(parse(text, sym), out_dir)


def _save(result: dict, out_dir: Path) -> dict:
    (out_dir / "instructions.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    return result
