"""Plano declarativo de uma campanha de medição (reprodutível e versionado).

    scripts/fidelity.py campaign --name v1            # gate → HW → Renode → análise

Configurações do Renode (pré-declaradas ANTES de ver os resultados finais):
  nominal     8 MIPS, quantum 1 µs  — hipótese "1 instrução por ciclo de HCLK"
  control100  100 MIPS (padrão do Renode) — controle de sensibilidade
  quantum     8 MIPS, quantum 125 ns — sensibilidade à sincronização
  calibrated  7 MIPS — único valor global, inteiro mais próximo de
              8 / CPI(mix S1A) = 8 / (22/18) = 6,545 (o Renode trunca MIPS
              para inteiro); validado fora da amostra em S1B/S2/S4.
  S3 apenas: as mesmas com AutoUpdateDelay=false (o receptor do STM32_UART
  já ritma 1 quadro/char; com o atraso do hub o byte chega após 2 quadros).
HW: OpenOCD próprio, gravação única por firmware + compare-sections; cada run
é um reset completo. "free" = sem debugger conectado durante a execução.
"""
from __future__ import annotations

import subprocess
import sys
import time

from . import analysis, firmware, gate, runner

MIPS_CALIBRATED = 7

RENODE_CONFIGS = {
    "nominal": runner.RenodeConfig(mips=8, quantum="0.000001"),
    "control100": runner.RenodeConfig(mips=100, quantum="0.000001"),
    "quantum": runner.RenodeConfig(mips=8, quantum="0.000000125"),
    "calibrated": runner.RenodeConfig(mips=MIPS_CALIBRATED, quantum="0.000001"),
}
RENODE_UART_EXTRA = {
    "nominal-nodelay": runner.RenodeConfig(mips=8, quantum="0.000001", uart_delay=False),
    "calibrated-nodelay": runner.RenodeConfig(mips=MIPS_CALIBRATED, quantum="0.000001", uart_delay=False),
}

PLAN = {
    "hw_runs": 10,
    "hw_free_runs": {"s1a": 3, "s2a": 3, "s4b": 3},
    "renode_runs": {"nominal": 3, "control100": 2, "quantum": 2, "calibrated": 2,
                    "nominal-nodelay": 2, "calibrated-nodelay": 2},
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(name: str, firmwares: list[str]) -> int:
    fws = [firmware.get(n) for n in firmwares]
    gate_rows = [r for fw in fws for r in gate.check(fw.name)]
    bad = [r for r in gate_rows if not r["ok"]]
    if bad:
        for r in bad:
            log(f"GATE FALHOU: {r['firmware']} {r['check']} {r['detail']}")
        return 2
    log(f"gate ok ({len(gate_rows)} verificações)")
    failures = 0
    bench_dir = runner.ROOT / "data" / "fidelity" / name / "_bench"
    with runner.HWBench(bench_dir) as bench:
        for fw in fws:
            batch = runner.batch_identity(fw)
            bench.flash(fw)
            for tag, free, n in (("hw", False, PLAN["hw_runs"]),
                                 ("hw-free", True, PLAN["hw_free_runs"].get(fw.name, 0))):
                if not n:
                    continue
                base = runner.campaign_dir(name, fw, tag)
                runner.record_batch(base, {"utc": runner.utc(), "runs": n, **batch})
                for _ in range(n):
                    res = bench.run(fw, runner.next_run_dir(base), batch, free_run=free)
                    failures += not res.ok
                    log(f"{tag} {fw.name} {res.path.name}: {'ok' if res.ok else 'ERRO ' + res.error}")
    for fw in fws:
        batch = runner.batch_identity(fw)
        configs = dict(RENODE_CONFIGS)
        if fw.uart_loopback:
            configs |= RENODE_UART_EXTRA
        for label, cfg in configs.items():
            n = PLAN["renode_runs"][label]
            base = runner.campaign_dir(name, fw, cfg.tag)
            runner.record_batch(base, {"utc": runner.utc(), "runs": n, "label": label,
                                       "tools": runner.tool_versions(), **batch})
            for _ in range(n):
                res = runner.run_renode(fw, cfg, runner.next_run_dir(base), batch)
                failures += not res.ok
                log(f"{cfg.tag} {fw.name} {res.path.name}: {'ok' if res.ok else 'ERRO ' + res.error}")
    log(f"aquisição concluída, falhas: {failures}")
    return 1 if failures else 0


def main(args) -> int:
    names = args.firmware or list(firmware.FIRMWARES)
    code = run(args.name, names)

    class A:
        firmware = names
        campaign = args.name
    analysis.main(A)
    return code
