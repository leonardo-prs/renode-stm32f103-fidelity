"""Caso Q-01: verificação dos instrumentos do Renode (03-quadro-comum.typ, família Q).

Roda o firmware src/q/q.c no Renode e confere cada instrumento usado pelos
cenários contra uma referência independente dele:

  gancho de endereço       tempo virtual × contador de instruções × DWT_CYCCNT × traço
  gancho de escrita        mesma instrução e mesmos argumentos (R0, R1) do store
  início/fim de exceção    mesma instrução da entrada no tratador; contagem do firmware
  traço de execução        PC no índice de cada gancho de endereço
  monitor e ganchos que gravam: o firmware lê os valores gravados; a pausa
                           termina no instante pedido

Duas variantes: "bare" (só os estímulos e o fim) e "full" (todos os
instrumentos). O registro do firmware tem de ser igual nas duas (não
intrusão) e cada variante tem de se repetir igual (determinismo).

Uso (dentro de `nix develop`):
  python3 scripts/q.py --name piloto-01            build do zero, execuções e resultado
  python3 scripts/q.py --name piloto-01 --analyze  só refaz o resultado
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import sim

ELF = sim.ROOT / "build" / "q" / "firmware.elf"
DATA = sim.ROOT / "data" / "q"
NS = sim.NS_PER_TICK

MAGIC = 0xC0DE0001                  # monitor grava em q_magic antes da partida
HOOK_VALUE = 0xC0FFEE01             # gancho em q_trigger grava em q_mbox2
PAUSES_NS = (200_000, 250_000)      # instantes das pausas do monitor
PAUSE_VALUES = (0x0BAD0001, 0x0BAD0002)
RUN_NS = 300_000
ICSR = 0xE000ED04
HANDLERS = {"PendSV_Handler": (14, "n_pendsv"), "SysTick_Handler": (15, "n_systick")}
REC = ("status", "magic", "n_pendsv", "n_systick", "hook_seen",
       "pause0", "pause1", "wait0", "wait1", "n_mark")       # depois: 16 valores do CYCCNT
N_CYC = 16
SYMBOLS = ("q_mark", "q_store", "q_trigger", "q_done", "q_fault", "q_magic", "q_sink", "q_mbox",
           "q_mbox2", "q_rec", *HANDLERS)
VARIANTS = ("bare", "full")
RAW = ("events.txt", "pauses.txt", "mem.txt", "trace.txt")

# Código Python dos ganchos (o Renode o executa com `self`, `machine`, `pc`…).
VT = "machine.ElapsedVirtualTime.TimeElapsed.Ticks"        # ns de tempo virtual
HOOK = {
    "addr": f"f = open(r'{{ev}}', 'a'); f.write('A %x %d %d %x %x %x\\n' % (pc, {VT}, self.ExecutedInstructions,"
            " self.GetRegister(0).RawValue, self.GetRegister(1).RawValue, self.GetRegister(25).RawValue)); f.close()",
    "write": "f = open(r'{ev}', 'a'); f.write('W %x %x %d %d %x\\n' % (address, value,"
             " self.Machine.ElapsedVirtualTime.TimeElapsed.Ticks, cpu.ExecutedInstructions, cpu.PC.RawValue)); f.close()",
    "begin": f"f = open(r'{{ev}}', 'a'); f.write('B %d %d %x %x\\n' % ({VT}, self.ExecutedInstructions,"
             " self.PC.RawValue, self.GetRegister(25).RawValue)); f.close()",
    "end": f"f = open(r'{{ev}}', 'a'); f.write('E %d %d %x %x\\n' % ({VT}, self.ExecutedInstructions,"
           " self.PC.RawValue, self.GetRegister(25).RawValue)); f.close()",
    "trigger": "machine.SystemBus.WriteDoubleWord({q_mbox2}, {hook_value})",
    "fault": "f = open(r'{dir}/fault.txt', 'w'); f.write('%x' % pc); f.close()",
    "done": "rd = machine.SystemBus.ReadDoubleWord; f = open(r'{dir}/mem.txt', 'w'); f.write("
            "' '.join('%d' % rd({q_rec} + 4 * k) for k in range({n}))); f.close()",
    # comando `python` do monitor, com a simulação parada
    "pause": "m = monitor.Machine; c = m['sysbus.cpu']; rd = m.SystemBus.ReadDoubleWord\n"
             "f = open(r'{dir}/pauses.txt', 'a'); f.write('M %d %d %s\\n' % (m.ElapsedVirtualTime.TimeElapsed.Ticks,"
             " c.ExecutedInstructions, ' '.join('%d' % rd({q_rec} + 4 * k) for k in range({n})))); f.close()\n"
             "m.SystemBus.WriteDoubleWord({q_mbox}, {value})",
}


# ───────────────────────────── execução ─────────────────────────────

def write_resc(d: Path, sym: dict[str, int], full: bool) -> Path:
    fmt = dict(ev=d / "events.txt", dir=d, n=len(REC) + N_CYC, hook_value=HOOK_VALUE, **sym)
    for name, code in HOOK.items():
        if name != "pause":
            (d / f"{name}.py").write_text(code.format(**fmt) + "\n")
    for k, value in enumerate(PAUSE_VALUES):
        (d / f"pause{k}.py").write_text(HOOK["pause"].format(value=value, **fmt) + "\n")

    def py(name: str) -> str:
        return f"\"exec(open(r'{d / name}.py').read())\""

    lines = [f"# caso Q-01, variante {'full' if full else 'bare'} (gerado por scripts/q.py)",
             *sim.machine(ELF),
             f"sysbus WriteDoubleWord 0x{sym['q_magic']:08x} 0x{MAGIC:08x}",
             f"sysbus.cpu AddHook 0x{sym['q_trigger']:08x} {py('trigger')}",
             f"sysbus.cpu AddHook 0x{sym['q_fault']:08x} {py('fault')}",
             f"sysbus.cpu AddHook 0x{sym['q_done']:08x} {py('done')}"]
    if full:
        lines += [f"sysbus.cpu AddHook 0x{sym[s]:08x} {py('addr')}" for s in ("q_mark", "q_store", *HANDLERS)]
        lines += [f"sysbus.cpu AddHookAtInterruptBegin {py('begin')}",
                  f"sysbus.cpu AddHookAtInterruptEnd {py('end')}",
                  f"sysbus AddWatchpointHook 0x{sym['q_sink']:08x} DoubleWord Write {py('write')}",
                  f"sysbus AddWatchpointHook 0x{ICSR:08x} DoubleWord Write {py('write')}",
                  f'sysbus.cpu CreateExecutionTracing "q" @{d / "trace.txt"} PC']
    t = 0
    for k, pause in enumerate(PAUSES_NS):
        lines += [f'emulation RunFor "{(pause - t) / 1e9:.9f}"', f"python {py(f'pause{k}')}"]
        t = pause
    lines += [f'emulation RunFor "{(RUN_NS - t) / 1e9:.9f}"', "quit", ""]
    resc = d / "run.resc"
    resc.write_text("\n".join(lines))
    return resc


def campaign(name: str, reps: int, build: bool) -> Path:
    out = DATA / name
    if out.exists():
        raise SystemExit(f"{out} já existe")
    if build:
        shutil.rmtree(sim.ROOT / "build" / "q", ignore_errors=True)
        subprocess.run(["cmake", "--workflow", "--preset", "q"], cwd=sim.ROOT, check=True,
                       stdout=subprocess.DEVNULL)
    sym = sim.symbols(ELF)
    out.mkdir(parents=True)
    used = {s: sym[s] for s in SYMBOLS}
    env = {**sim.environment(ELF), "simbolos": used, "repeticoes": reps}
    (out / "ambiente.json").write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n")
    for variant in VARIANTS:
        for rep in range(reps):
            d = out / f"{variant}-{rep}"
            d.mkdir()
            print(f"{d.name} …", flush=True)
            sim.run(write_resc(d, used, variant == "full"), d / "renode.log")
    return out


# ───────────────────────────── análise ─────────────────────────────

def read_run(d: Path) -> dict:
    def ints(fields: list[str], hexes: str) -> tuple[int, ...]:
        return tuple(int(x, 16 if h == "x" else 10) for x, h in zip(fields, hexes))

    fmt = {"A": "xddxxx", "W": "xxddx", "B": "ddxx", "E": "ddxx"}
    ev: dict[str, list] = {k: [] for k in fmt}
    if (d / "events.txt").exists():
        for line in (d / "events.txt").read_text().splitlines():
            k, *f = line.split()
            ev[k].append(ints(f, fmt[k]))
    words = [int(x) for x in (d / "mem.txt").read_text().split()] if (d / "mem.txt").exists() else []
    pauses = [[int(x) for x in line.split()[1:]] for line in (d / "pauses.txt").read_text().splitlines()]
    trace = [int(x, 16) for x in (d / "trace.txt").read_text().split()] if (d / "trace.txt").exists() else None
    return {**ev, "rec": dict(zip(REC, words)), "cyc": words[len(REC):], "words": words,
            "pauses": pauses, "trace": trace, "fault": (d / "fault.txt").exists()}


def check_run(r: dict, sym: dict[str, int], full: bool) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def c(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, bool(ok), detail))

    rec = r["rec"]
    c("firmware chegou ao fim, sem exceção inesperada", rec.get("status") == 1 and not r["fault"])
    c("monitor grava antes da partida: o firmware lê o valor", rec.get("magic") == MAGIC)
    c("gancho de endereço grava na memória: o firmware lê o valor", rec.get("hook_seen") == HOOK_VALUE)
    vt = [p[0] for p in r["pauses"]]
    c("pausa do monitor termina no instante pedido (e em instrução inteira)",
      vt == list(PAUSES_NS) and all(p[1] * NS == p[0] for p in r["pauses"]), f"{vt} ns")
    c("monitor grava na pausa: o firmware lê o valor", (rec.get("pause0"), rec.get("pause1")) == PAUSE_VALUES)
    c("monitor lê a memória na pausa: igual à memória no fim (campos já finais)",
      all(p[2 + len(REC):2 + len(REC) + p[2 + REC.index("n_mark")]] ==
          r["cyc"][:p[2 + REC.index("n_mark")]] for p in r["pauses"]))
    if not full:
        return out

    A, W, B, E, trace = r["A"], r["W"], r["B"], r["E"], r["trace"] or []
    marks = [a for a in A if a[0] == sym["q_mark"]]
    stores = [a for a in A if a[0] == sym["q_store"]]
    entries = [a for a in A if a[0] in (sym[h] for h in HANDLERS)]
    c("ganchos de endereço e de escrita: tempo virtual = 125 ns × instruções",
      all(a[1] == NS * a[2] for a in A) and all(w[2] == NS * w[3] for w in W), f"{len(A) + len(W)} eventos")
    off = {k: sorted({e[0] // NS - e[1] for e in r[k]}) for k in "BE"}
    c("início/fim de exceção: diferença constante entre tempo/125 ns e instruções",
      len(off["B"]) == 1 and len(off["E"]) == 1, f"início {off['B']}, fim {off['E']}")
    n = rec["n_mark"]
    d_cyc = [b - a for a, b in zip(r["cyc"][:n], r["cyc"][1:n])]
    d_ins = [b[2] - a[2] for a, b in zip(marks, marks[1:])]
    c("Δ DWT_CYCCNT = Δ instruções entre pontos marcados", len(marks) == n and d_cyc == d_ins, f"{n} pontos")
    c("traço: a instrução no índice de cada gancho de endereço é a do PC do gancho",
      all(a[2] < len(trace) and trace[a[2]] == a[0] for a in A), f"{len(A)} ganchos, traço de {len(trace)}")
    want = sorted((a[2], a[3], a[4], sym["q_store"]) for a in stores)
    got = sorted((w[3], w[0], w[1], w[4]) for w in W)
    c("gancho de escrita: um por q_store, na instrução do store, com endereço e valor de R0/R1",
      bool(want) and want == got, f"{len(W)} escritas")
    for h, (exc, field) in HANDLERS.items():
        hs = [a for a in A if a[0] == sym[h]]
        c(f"gancho no 1º endereço do {h}: uma passagem por entrada, IPSR = {exc}",
          len(hs) == rec[field] and all(a[5] & 0x1FF == exc for a in hs), f"{len(hs)} entradas")
    c("início de exceção na instrução de cada entrada em tratador; um fim por início",
      sorted(b[1] for b in B) == sorted(a[2] for a in entries) and len(E) == len(B),
      f"{len(B)} inícios, {len(E)} fins")
    return out


def analyze(out: Path) -> bool:
    env = json.loads((out / "ambiente.json").read_text())
    sym = env["simbolos"]
    runs = {d.name: read_run(d) for d in sorted(out.iterdir()) if d.is_dir()}
    rows: dict[str, list[tuple[bool, str]]] = {}
    for name, r in runs.items():
        for crit, ok, detail in check_run(r, sym, name.startswith("full")):
            rows.setdefault(crit, []).append((ok, f"{name}: {detail}" if detail else ""))
    words = {name: r["words"] for name, r in runs.items()}
    rows["não intrusão: registro do firmware igual com e sem instrumentos"] = \
        [(len({tuple(w) for w in words.values()}) == 1, "")]
    for v in VARIANTS:
        same = {tuple((out / name / f).read_bytes() if (out / name / f).exists() else b"" for f in RAW)
                for name in runs if name.startswith(v)}
        rows[f"repetições da variante {v} idênticas (arquivos brutos)"] = [(len(same) == 1, "")]

    ok_all = all(ok for v in rows.values() for ok, _ in v)
    lines = [f"# Caso Q-01 — instrumentos do Renode: `{out.name}`", "",
             f"**Veredito: {'IGUAL' if ok_all else 'REPROVADO'}**", "",
             "| | |", "|---|---|",
             *(f"| {k} | `{v}` |" for k, v in env.items() if k != "simbolos"), "",
             "| Critério | Resultado | Detalhe |", "|---|---|---|"]
    for crit, res in rows.items():
        detail = next((d for ok, d in res if d and not ok), next((d for _, d in res if d), ""))
        lines.append(f"| {crit} | {'ok' if all(ok for ok, _ in res) else '**FALHOU**'} | {detail} |")
    full = runs.get("full-0")
    if full:
        rec = full["rec"]
        lines += ["", "Valores (full-0): "
                  f"{rec['n_pendsv']} entradas no PendSV, {rec['n_systick']} no SysTick; "
                  f"espera do monitor {rec['wait0']} e {rec['wait1']} voltas; "
                  f"instruções nas pausas {[p[1] for p in full['pauses']]}."]
    (out / "resultado.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return ok_all


def main() -> None:
    ap = argparse.ArgumentParser(description="Caso Q-01: instrumentos do Renode")
    ap.add_argument("--name", required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--analyze", action="store_true", help="só refaz o resultado")
    a = ap.parse_args()
    out = DATA / a.name if a.analyze else campaign(a.name, a.reps, not a.no_build)
    raise SystemExit(0 if analyze(out) else 1)


if __name__ == "__main__":
    main()
