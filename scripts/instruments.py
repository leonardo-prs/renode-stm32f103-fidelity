"""Verification of the Renode instruments (Renode only).

Checks each instrument the scenarios use against a reference independent of it:

  address hook        virtual time vs instruction count vs DWT_CYCCNT vs trace
  write hook          same instruction and same arguments (R0, R1) as the store
  exception begin/end begin at the handler entry; end paired by IPSR, return instruction at N−1
  monitor, hooks      the firmware reads what they write; a pause ends at the requested instant

The reference run (only stimuli and record) and the instrumented run (every instrument) must give
the same firmware record (non-intrusion), and each must repeat identically.

  python3 scripts/instruments.py              clean build, runs, result (replaces data/instruments/)
  python3 scripts/instruments.py --analyze    only redo the result
"""
from __future__ import annotations

import argparse
import lzma
from pathlib import Path

import sim
from sim import Run

FIRMWARE = "instruments"
ELF = sim.ROOT / "build" / FIRMWARE / "firmware.elf"
DATA = sim.ROOT / "data" / "instruments"
NS = sim.NS_PER_TICK
VARIANTS = ("reference", "instrumented")
REPS = 3                    # runs per variant; identical runs show there is no random variable

BOOT_VALUE = 0xC0DE0001             # the monitor writes it to selected_case before boot
HOOK_VALUE = 0xC0FFEE01             # the hook at `trigger` writes it to `hook_mailbox`
PAUSES_NS = (20_000_000, 25_000_000, 30_000_000)      # instants of the monitor pauses
PAUSE_VALUES = (0x0BAD0001, 0x0BAD0002, 0x0BAD0003)   # what the monitor writes to `mailbox` at each
RUN_NS = 35_000_000
ICSR = 0xE000ED04       # watched peripheral register: in Renode the NVIC is a bus peripheral, like TIM2
ISPR0 = 0xE000E200                  # NVIC_ISPR0: bit 0 requests IRQ 0, the external line
EXTERNAL_REQUESTS = 6               # 3 by STIR (phases 7–9) + 1 by the monitor at each pause
STRESS_CALLS = 10_000               # minimum calls through one address hook in one run (non-intrusion under load)
HANDLERS = {"PendSV_Handler": (14, "n_pendsv"), "SysTick_Handler": (15, "n_systick"),
            "External_Handler": (16, "n_external")}           # handler → (exception number, field)
SOURCES = (("PendSV", 14), ("SysTick", 15), ("external STIR", 16), ("external monitor ISPR", 16))
SITUATIONS = ("simple", "tail-chain", "nested")
# argument of phase_mark → (source, situation) whose return the phase exercises
PHASES = {1 + 3*i + j: (i, j) for i in range(len(SOURCES)) for j in range(len(SITUATIONS))}
# record: DWT_CYCCNT at each marked point, then these fields (record_results() in the firmware)
FIELDS = ("selected_case", "hook_seen", "pause0", "pause1", "pause2", "wait0", "wait1",
          "n_pendsv", "n_systick", "n_external")
SYMBOLS = ("selected_case", "record", "record_length", "record_complete", "unexpected_exception",      # src/common/case.h
           "mark", "store", "trigger", "stress", "phase_mark", "sink", "mailbox", "hook_mailbox", *HANDLERS)


# ───────────────────────────── execution ─────────────────────────────

def execute() -> None:
    sym = sim.firmware_symbols(FIRMWARE, build=True)
    sim.new_case(DATA, FIRMWARE, sym, SYMBOLS, {"reps": REPS})
    for variant in VARIANTS:
        for k in range(1, REPS + 1):
            (DATA / variant / f"run-{k}").mkdir(parents=True)
    variables = {"OUT": str(DATA), "REPS": str(REPS), "ELF": str(ELF),
                 "BOOT_VALUE": str(BOOT_VALUE), "HOOK_VALUE": str(HOOK_VALUE),
                 "ICSR": hex(ICSR), "ISPR0": hex(ISPR0), "RUN_NS": str(RUN_NS),
                 "PAUSE_TIMES": ",".join(map(str, PAUSES_NS)),
                 "PAUSE_VALUES": ",".join(map(str, PAUSE_VALUES)),
                 **{s.upper(): hex(sym[s]) for s in SYMBOLS}}
    sim.run_robot("instruments", "instruments", DATA / "_robot", variables)
    for k in range(1, REPS + 1):
        compress_trace(DATA / "instrumented" / f"run-{k}")


def compress_trace(directory: Path) -> None:
    """Renode writes trace.txt (about 4 MB); the published data keeps it as trace.txt.xz."""
    text = directory / "trace.txt"
    (directory / "trace.txt.xz").write_bytes(lzma.compress(text.read_bytes()))
    text.unlink()


# ───────────────────────────── analysis ─────────────────────────────

def read_trace(directory: Path) -> list[tuple[int, str]]:
    """Execution trace of an instrumented run: (pc, opcode) per executed instruction, in order.
    A missing trace stops the script: run the case again."""
    path = directory / "trace.txt.xz"
    if not path.exists():
        raise SystemExit(f"{path} is missing; run the case again")
    trace = []
    for line in lzma.decompress(path.read_bytes()).decode().splitlines():
        pc, opcode = line.split(": ")
        trace.append((int(pc, 16), opcode.removeprefix("0x").upper()))
    return trace


def is_return(opcode: str) -> bool:
    """bx lr, pop {…, pc} or pop.w {…, pc}: the instructions that can return from an exception here."""
    return opcode == "4770" or (len(opcode) == 4 and opcode.startswith("BD")) or \
        (len(opcode) == 8 and opcode.startswith("E8BD") and int(opcode[4:], 16) & 0x8000 != 0)


def check_run(run: Run, trace: list, sym: dict[str, int], instrumented: bool) -> list[tuple[str, bool, str]]:
    """(criterion, ok, detail) of one run."""
    out: list[tuple[str, bool, str]] = []

    def c(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, bool(ok), detail))

    cyc, rec = split(run.record)
    c("monitor writes selected_case before boot: the firmware reads the value", rec["selected_case"] == BOOT_VALUE)
    c("address hook writes to memory: the firmware reads the value", rec["hook_seen"] == HOOK_VALUE)
    times = [p.time_ns for p in run.monitor_pauses]
    c("monitor pause ends at the requested instant (and on a whole instruction)",
      times == list(PAUSES_NS) and all(p.instructions * NS == p.time_ns for p in run.monitor_pauses), f"{times} ns")
    c("monitor writes in the pause: the firmware reads the value",
      (rec["pause0"], rec["pause1"], rec["pause2"]) == PAUSE_VALUES)
    c("monitor reads memory in the pause: record_length and record so far equal to the final record",
      all(p.words[0] == len(p.words) - 1 and list(p.words[1:]) == run.record[:p.words[0]] for p in run.monitor_pauses))
    if not instrumented:
        return out

    marks = [a for a in run.address_hooks if a.pc == sym["mark"]]
    stores = [a for a in run.address_hooks if a.pc == sym["store"]]
    entries = [a for a in run.address_hooks if a.pc in {sym[h] for h in HANDLERS}]
    c("address and write hooks: virtual time = 125 ns × instructions",
      all(e.time_ns == NS * e.instructions for e in run.address_hooks + run.writes),
      f"{len(run.address_hooks) + len(run.writes)} events")
    d_cyc = [b - a for a, b in zip(cyc, cyc[1:])]
    d_ins = [b.instructions - a.instructions for a, b in zip(marks, marks[1:])]
    c("Δ DWT_CYCCNT = Δ instructions between marked points", len(marks) == len(cyc) and d_cyc == d_ins,
      f"{len(cyc)} points")
    c("trace: the instruction at the index of each address hook is the hook PC",
      all(a.instructions < len(trace) and trace[a.instructions][0] == a.pc for a in run.address_hooks),
      f"{len(run.address_hooks)} hooks, trace of {len(trace)}")
    want = sorted((a.instructions, a.r0, a.r1, sym["store"]) for a in stores)
    got = sorted((w.instructions, w.address, w.value, w.pc) for w in run.writes)
    c("write hook: one per call of store, at the store instruction, with address and value from R0/R1",
      bool(want) and want == got, f"{len(run.writes)} writes")
    for h, (exc, field) in HANDLERS.items():
        hs = [a for a in run.address_hooks if a.pc == sym[h]]
        c(f"hook at the 1st address of {h}: one pass per entry, IPSR = {exc}",
          len(hs) == rec[field] and all(a.ipsr == exc for a in hs), f"{len(hs)} entries")
    c("exception begin at the instruction of each handler entry; one end per begin",
      sorted(b.instructions for b in run.exception_entries) == sorted(a.instructions for a in entries)
      and len(run.exception_exits) == len(run.exception_entries),
      f"{len(run.exception_entries)} begins, {len(run.exception_exits)} ends")
    _, errors = check_returns(run, trace, sym)
    c("exception ends: paired by IPSR, return at N-1 and correct successor", not errors,
      "; ".join(errors[:5]) if errors else f"{len(run.exception_exits)} ends; all {len(PHASES)} matrix cells")
    c(f"address hook under load: at least {STRESS_CALLS} calls",
      sum(a.pc == sym["stress"] for a in run.address_hooks) >= STRESS_CALLS)
    c(f"external line: {EXTERNAL_REQUESTS} entries (firmware STIR and monitor ISPR requests)",
      rec["n_external"] == EXTERNAL_REQUESTS, f"{rec['n_external']} entries")
    return out


def check_returns(run: Run, trace: list, sym: dict[str, int]) -> tuple[dict[int, int], list[str]]:
    """Checks every exception end: paired by IPSR with the innermost open entry, a return
    instruction at trace index N−1, and at N the interrupted instruction or a chained handler.
    Returns (ends per return-matrix cell, errors)."""
    handlers = {sym[h] for h in HANDLERS}
    entry_at = {a.instructions: a.pc for a in run.address_hooks if a.pc in handlers}     # handler entries by count
    begins: list[sim.ExceptionEntry] = []           # begins waiting for their handler entry hook
    open_entries: list[tuple[int, int]] = []  # (ipsr, interrupted pc), innermost last
    phase, cells, errors = 0, {}, []
    for ev in run.events:
        if type(ev) is sim.ExceptionEntry:
            begins.append(ev)
        elif type(ev) is sim.AddressHook and ev.pc == sym["phase_mark"]:
            phase = ev.r0
        elif type(ev) is sim.AddressHook and ev.pc in handlers:
            begin = next((b for b in begins if b.instructions == ev.instructions), None)
            if begin is None:
                errors.append(f"entry without begin at {ev.instructions}")
                continue
            begins.remove(begin)
            open_entries.append((ev.ipsr, begin.pc))
        elif type(ev) is sim.ExceptionExit:
            if not open_entries or open_entries[-1][0] != ev.ipsr:
                errors.append(f"unpaired end {ev.instructions} IPSR {ev.ipsr}")
                continue
            depth = len(open_entries)
            _, interrupted = open_entries.pop()
            if not 1 <= ev.instructions < len(trace):
                errors.append(f"end {ev.instructions} outside trace")
                continue
            if not is_return(trace[ev.instructions - 1][1]):
                errors.append(f"end {ev.instructions}: opcode {trace[ev.instructions - 1][1]} is not a return")
            successor = trace[ev.instructions][0]
            chained = entry_at.get(ev.instructions) == successor
            if successor != interrupted and not chained:
                errors.append(f"end {ev.instructions}: unexpected successor {successor:#x}, interrupted {interrupted:#x}")
            if depth == 1:
                situation = 1 if chained else 0           # tail-chain or simple return
            else:
                situation = None if chained else 2        # nested: back to the outer handler
            if phase in PHASES:
                source, wanted = PHASES[phase]
                if ev.ipsr == SOURCES[source][1] and situation == wanted:
                    cells[phase] = cells.get(phase, 0) + 1
    if open_entries or begins:
        errors.append(f"unclosed events: entries {open_entries}, begins {begins}")
    missing = sorted(PHASES.keys() - cells.keys())
    if missing:
        errors.append(f"missing matrix cells {missing}")
    return cells, errors


def split(record: list[int]) -> tuple[list[int], dict[str, int]]:
    """record → (DWT_CYCCNT of the marked points, fields)."""
    n = len(record) - len(FIELDS)
    return record[:n], dict(zip(FIELDS, record[n:]))


def read_runs(data: Path, reps: int) -> dict[str, tuple[Run, list]]:
    """Every run, as "<variant>/run-<k>" → (events, trace). A run that cannot be analyzed (no
    end, fault, short record) stops the script: run the case again."""
    runs = {}
    for variant in VARIANTS:
        for k in range(1, reps + 1):
            name = f"{variant}/run-{k}"
            run = sim.read_run(data / name)
            if run.unexpected_exception or len(run.record) < len(FIELDS):
                raise SystemExit(f"{data / name}: the firmware did not reach the end; run the case again")
            trace = read_trace(data / name) if variant == "instrumented" else []    # only instrumented runs trace
            runs[name] = (run, trace)
    return runs


def analyze(data: Path) -> bool:
    env = sim.read_environment(data)
    sym = env["symbols"]
    runs = read_runs(data, env["reps"])
    rows: dict[str, list[tuple[bool, str]]] = {}
    for name, (run, trace) in runs.items():
        for criterion, ok, detail in check_run(run, trace, sym, name.startswith("instrumented")):
            rows.setdefault(criterion, []).append((ok, f"{name}: {detail}" if detail else ""))
    records = {tuple(run.record) for run, _ in runs.values()}
    rows["non-intrusion: firmware record equal with and without instruments"] = [(len(records) == 1, "")]
    for variant in VARIANTS:
        same = {(sim.repetition_signature(run), tuple(trace))
                for name, (run, trace) in runs.items() if name.startswith(variant)}
        rows[f"repetitions of the {variant} run identical (parsed events)"] = [(len(same) == 1, "")]

    equal = all(ok for res in rows.values() for ok, _ in res)
    lines = ["# Verification of the Renode instruments", "",
             f"**Verdict: {'EQUAL' if equal else 'DIVERGES'}**", "",
             "| | |", "|---|---|",
             *(f"| {k} | `{v}` |" for k, v in env.items() if k != "symbols"), "",
             "| Criterion | Result | Detail |", "|---|---|---|"]
    for criterion, res in rows.items():
        detail = next((d for ok, d in res if d and not ok), next((d for _, d in res if d), ""))
        lines.append(f"| {criterion} | {'ok' if all(ok for ok, _ in res) else '**differs**'} | {detail} |")

    run, trace = runs["instrumented/run-1"]
    rec = split(run.record)[1]
    offsets = {"begin": sorted({e.time_ns // NS - e.instructions for e in run.exception_entries}),
               "end": sorted({e.time_ns // NS - e.instructions for e in run.exception_exits})}
    cells, _ = check_returns(run, trace, sym)
    lines += ["", f"Begin/end hook time offsets in ticks (observation, not judged): {offsets}.",
              "", "Return matrix (instrumented/run-1, ends per cell):", "",
              "| Source | " + " | ".join(SITUATIONS) + " |", "|---|---:|---:|---:|"]
    for i, (source, _) in enumerate(SOURCES):
        lines.append(f"| {source} | " + " | ".join(str(cells.get(1 + 3*i + j, 0)) for j in range(3)) + " |")
    lines += ["", "Values (instrumented/run-1): "
              f"{rec['n_pendsv']} PendSV entries, {rec['n_systick']} SysTick, {rec['n_external']} external; "
              f"monitor wait {rec['wait0']} and {rec['wait1']} rounds; "
              f"instructions at the pauses {[p.instructions for p in run.monitor_pauses]}."]
    (data / "result.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return equal


def main() -> None:
    ap = argparse.ArgumentParser(description="Verification of the Renode instruments")
    ap.add_argument("--analyze", action="store_true", help="only redo the result")
    if not ap.parse_args().analyze:
        execute()
    raise SystemExit(0 if analyze(DATA) else 1)


if __name__ == "__main__":
    main()
