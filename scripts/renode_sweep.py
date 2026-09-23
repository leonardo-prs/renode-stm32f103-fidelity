#!/usr/bin/env python3
"""renode_sweep.py — bateria Renode headless e paralela (sem GDB, sem portas).

Cada job gera um .resc próprio, roda `emulation RunFor` por um tempo virtual
fixo, lê os buffers com `sysbus ReadBytes` e sai. Como não há StartGdbServer
nem monitor telnet (-P), N instâncias do Renode rodam lado a lado sem
conflito de porta. Saída: OUTDIR/<tag>.bin (mesmo formato do dump_sram.sh:
c*_results truncado em c*_n words) + OUTDIR/<tag>.json (metadados).

Uso (dentro de `nix develop`):
    scripts/renode_sweep.py OUTDIR JOB [JOB ...] [-j N]
    JOB = tag:caso:mips:escala:quantum_s:runfor_s
    ex.: c2_m8:c2:8:1:0.000001:1.2

Casos: c1 c2 c2busy c3 c4 (c4 = DUT + peer de echo via UARTHub; o peer usa
o mesmo mips/escala do DUT).

Calibração da CPU: o único knob efetivo do CortexM é `PerformanceInMips`
(UInt32). `cpu CyclesPerInstruction` existe mas NÃO altera CYCCNT nem a taxa
de instruções (medido: C1 idêntico com 1,0 e 1,5). Para um CPI efetivo
fracionário, `escala` = k multiplica TODAS as frequências do .repl (DWT,
SysTick, timers, USART1) por k; com PerformanceInMips = M, o CPI efetivo
visto pelo CYCCNT é 8·k/M. Em ciclos, timers e UART ficam invariantes.
quantum_s e runfor_s são dados em tempo equivalente a 8 MHz (divididos por k).

ARMADILHA do quantum: MIPS × quantum_real tem de dar um inteiro EXATO em ponto
flutuante. Ex.: 50 MIPS × 0,12 µs = 5,999… → o Renode executa só 84% das
instruções (CPI efetivo 1,71 em vez de 1,44). Medido com 50 MIPS: 0,1/0,2/
0,5/1 µs limpos; 0,12 e 0,25 µs não. O campo `efficiency` do .json
(instruções executadas ÷ MIPS × tempo) tem de ser 1,000 nos casos sem WFI
(c1, c2busy); o runner avisa quando não for.
"""

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

REPL = "renode/stm32f103_hsi8.repl"
CASES = {
    #          ELF                        results       n       done      aux
    "c1":     ("build/c1/firmware.elf",     "c1_results", "c1_n", "c1_done", None),
    "c2":     ("build/c2/firmware.elf",     "c2_results", "c2_n", "c2_done", None),
    "c2busy": ("build/c2busy/firmware.elf", "c2_results", "c2_n", "c2_done", None),
    "c3":     ("build/c3/firmware.elf",     "c3_results", "c3_n", "c3_done", None),
    "c4":     ("build/c4/firmware.elf",     "c4_results", "c4_n", "c4_done", ("c4_aux", "c4_auxn")),
}
TIMEOUT_S = 1800  # por job; sobrescrito por --timeout
SIZES = {"c1_results": 0xAF0, "c2_results": 0x2000, "c3_results": 0x2000,
         "c4_results": 0x2000, "c4_aux": 0x400}


def sym(s):
    return '`sysbus GetSymbolAddress "%s"`' % s


def scaled_repl(k, outdir):
    """Cópia do .repl com todas as frequências de 8 MHz multiplicadas por k."""
    if k == 1:
        return REPL
    path = os.path.join(outdir, f"stm32f103_hsi8_x{k}.repl")
    with open(REPL) as f:
        txt = f.read()
    txt, n = re.subn(r"(?m)^(\s*(?:frequency|systickFrequency):\s*)8000000\b",
                     lambda m: m.group(1) + str(8000000 * k), txt)
    assert n == 17, f"esperava 17 frequências no .repl, achei {n}"
    with open(path, "w") as f:
        f.write(txt)
    return path


def make_resc(case, mips, k, quantum, runfor, outdir):
    elf, res, n, done, aux = CASES[case]
    repl = scaled_repl(k, outdir)
    q = float(quantum) / k
    rf = float(runfor) / k
    L = ['mach create "dut"',
         f"machine LoadPlatformDescription @{repl}",
         "logLevel 3",
         f'emulation SetGlobalQuantum "{q:.12f}"',
         f"sysbus LoadELF @{elf}",
         f"cpu PerformanceInMips {mips}"]
    if case == "c4":
        L += ['mach create "peer"',
              f"machine LoadPlatformDescription @{repl}",
              "sysbus LoadELF @build/echo/firmware.elf",
              f"cpu PerformanceInMips {mips}",
              'emulation CreateUARTHub "hub"',
              "mach set 0", "connector Connect sysbus.usart1 hub",
              "mach set 1", "connector Connect sysbus.usart1 hub",
              "mach set 0"]
    L.append(f'emulation RunFor "{rf:.12f}"')
    # Ordem de leitura fixa: done, n, results, [auxn, aux], métricas da CPU.
    reads = [(done, 1), (n, 4), (res, SIZES[res])]
    if aux:
        reads += [(aux[1], 4), (aux[0], SIZES[aux[0]])]
    for s, nb in reads:
        L.append(f"sysbus ReadBytes {sym(s)} {nb}")
    L += ["cpu ExecutedInstructions", "cpu ElapsedCycles", "quit"]
    return "\n".join(L) + "\n", reads


def parse(out, reads):
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    blocks = re.findall(r"^\[\s*\n(.*?)^\]", out, re.S | re.M)
    if len(blocks) != len(reads):
        raise RuntimeError(f"esperava {len(reads)} blocos ReadBytes, veio {len(blocks)}")
    data = {}
    for (s, _), b in zip(reads, blocks):
        data[s] = bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", b))
    tail = re.findall(r"^0x([0-9A-Fa-f]+)\s*$", out.split(blocks[-1])[-1], re.M)
    return data, [int(t, 16) for t in tail[-2:]]


def run_job(job, outdir, renode):
    tag, case, mips, k, q, rf = job.split(":")
    k = int(k)
    resc, reads = make_resc(case, mips, k, q, rf, outdir)
    rpath = os.path.join(outdir, tag + ".resc")
    with open(rpath, "w") as f:
        f.write(resc)
    t0 = time.time()
    p = subprocess.run([renode, "--disable-xwt", "--console", "-e", f"i @{rpath}"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       timeout=TIMEOUT_S)
    wall = time.time() - t0
    with open(os.path.join(outdir, tag + ".log"), "w") as f:
        f.write(p.stdout + p.stderr)
    data, cpu = parse(p.stdout, reads)
    _, res, n, done, aux = CASES[case]
    nwords = struct.unpack("<I", data[n])[0]
    with open(os.path.join(outdir, tag + ".bin"), "wb") as f:
        f.write(data[res][: nwords * 4])
    if aux:
        na = struct.unpack("<I", data[aux[1]])[0]
        with open(os.path.join(outdir, tag + "_aux.bin"), "wb") as f:
            f.write(data[aux[0]][: na * 4])
    expected = int(mips) * 1e6 * float(rf) / k
    eff = (cpu[0] / expected) if cpu else None
    meta = dict(tag=tag, case=case, mips=int(mips), scale=k, cpi_eff=8 * k / int(mips),
                efficiency=round(eff, 4) if eff else None,
                quantum=q, runfor=rf,
                done=data[done][0], n=nwords, executed_instr=cpu[0] if cpu else None,
                elapsed_cycles=cpu[1] if len(cpu) > 1 else None, wall_s=round(wall, 1))
    with open(os.path.join(outdir, tag + ".json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("-j", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--renode", default="renode")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_S, help="s de relógio por job")
    a = ap.parse_args()
    globals()["TIMEOUT_S"] = a.timeout
    os.makedirs(a.outdir, exist_ok=True)
    ok = True
    with ThreadPoolExecutor(a.j) as ex:
        futs = {ex.submit(run_job, j, a.outdir, a.renode): j for j in a.jobs}
        for fu in futs:
            try:
                m = fu.result()
                flag = "OK " if m["done"] == 1 else "NAO-DONE"
                if m["case"] in ("c1", "c2busy") and abs((m["efficiency"] or 0) - 1) > 1e-3:
                    flag += " [AVISO eficiencia=%s: quantum nao-inteiro?]" % m["efficiency"]
                ok &= m["done"] == 1
                print(f"{flag} {m['tag']}: done={m['done']} n={m['n']} "
                      f"instr={m['executed_instr']} cyc={m['elapsed_cycles']} wall={m['wall_s']}s",
                      flush=True)
            except Exception as e:  # noqa: BLE001 — reportar e seguir os outros jobs
                ok = False
                print(f"ERRO {futs[fu]}: {e}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
