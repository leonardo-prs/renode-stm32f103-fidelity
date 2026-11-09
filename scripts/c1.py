"""C1 — the core (firmware src/c1/c1.c), board oracle (#oP) for every case.

    python3 scripts/c1.py [--cases C1-01 …] [--board] [--analyze]

Renode: each case in robot/c1.robot. Board (--board): the same ELF through scripts/board.py; no
wire is used and no pin is driven. Each case compares the Renode record with the board record,
item by item; the board is the reference. Data: data/c1/renode/<case>/ and data/c1/board/<case>/,
each replaced when that case runs again in that environment; result.md judges every case found.

  C1-01 (c1_01_arithmetic)        arithmetic and flags: result and APSR of each operation, high word of long multiplies
  C1-02 (c1_02_conversions)       conversions: extensions, narrow loads/stores, CMP and 14 conditions
  C1-03 (c1_03_memory)            common memory: byte order, widths, unaligned, multiple, stack, indexing
  C1-04 (c1_04_timebase)          timebase: consecutive DWT_CYCCNT reads, counter disabled, ΔTIM2_CNT − ΔDWT
  C1-05 (c1_05_instruction_cost)  ticks of each class at 16 and at 32 instructions, 1st and 2nd execution
  C1-06 (c1_06_exception_frame)   the frame SVC stacks, EXC_RETURN and the return, on both stacks, with STKALIGN 0 and 1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import board
import sim

FIRMWARE = "c1"
ELF = sim.ROOT / "build" / FIRMWARE / "firmware.elf"
DATA = sim.ROOT / "data" / "c1"
SYMBOLS = ("selected_case", "record_complete", "unexpected_exception", "record_length", "record")
REPS = 3                    # runs per environment; a difference between them stops the analysis
MS = 1_000_000

# case directory name → (selected_case number, case ID, short title, virtual run time in ns)
CASES = {
    "c1_01_arithmetic":       (1, "C1-01", "arithmetic and flags",           5 * MS),
    "c1_02_conversions":      (2, "C1-02", "conversions and comparisons",    5 * MS),
    "c1_03_memory":           (3, "C1-03", "memory access and addressing",   5 * MS),
    "c1_04_timebase":         (4, "C1-04", "DWT_CYCCNT timebase",           20 * MS),
    "c1_05_instruction_cost": (5, "C1-05", "instruction and bus cycle cost", 5 * MS),
    "c1_06_exception_frame":  (6, "C1-06", "exception frame and return",     5 * MS),
}

# tables: the same order and sizes are in src/c1/c1.c
ARITHMETIC_OPS = ["ADDS", "ADCS", "SUBS", "SBCS", "MUL", "UMULL", "SMULL", "UDIV", "SDIV",
                  "LSLS", "LSRS", "ASRS", "RORS", "SSAT #8", "USAT #8"]
ARITHMETIC_POINTS = 59
LONG_MULTIPLIES = ("UMULL", "SMULL")      # the only operations with a high word
EXTENSION_VALUES = [0x0000007F, 0x00000080, 0x123456FF, 0x00007FFF, 0x00008000, 0xABCD8001]
CMP_LEFT = [1, 2, 0xFFFFFFFF, 1, 0x80000000, 0x7FFFFFFF, 5]
CMP_RIGHT = [2, 1, 1, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000, 5]
CMP_CONDITIONS = ["EQ", "NE", "HS", "LO", "MI", "PL", "VS", "VC", "HI", "LS", "GE", "LT", "GT", "LE"]
TIMEBASE_WAITS = [1000, 50000]
# (class, unit of its cost); each one is measured at two lengths, after the empty window
COST_CLASSES = [("NOP", "instruction"), ("taken B", "branch"), ("loop SUBS + BNE", "iteration"),
                ("LDR SRAM", "instruction"), ("STR SRAM", "instruction"),
                ("LDR.W SRAM, word-aligned", "instruction"), ("LDR.W SRAM, halfword-aligned", "instruction"),
                ("LDR flash", "instruction"), ("LDR GPIOA_IDR (APB2)", "instruction"),
                ("STR GPIOA_BSRR (APB2)", "instruction"), ("LDR TIM2_CNT (APB1)", "instruction"),
                ("DSB", "instruction"), ("ISB", "instruction"),
                ("UDIV ÷ 0", "instruction"), ("UDIV largest quotient", "instruction"),
                ("UMULL small operands", "instruction"), ("UMULL largest operands", "instruction"),
                ("LDM 4 registers", "instruction"), ("PUSH + POP 4 registers", "pair"),
                ("LDR unaligned at +1", "instruction"), ("LDR unaligned at +2", "instruction")]
LENGTHS = (16, 32)
# (process stack, SP misaligned, STKALIGN)
FRAME_POINTS = [(0, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1), (1, 0, 0), (1, 1, 0), (1, 0, 1), (1, 1, 1)]
FRAME_RECORD_WORDS = 18
FRAME_REGISTERS = ("r0", "r1", "r2", "r3", "r12", "lr")


def flags(apsr: int) -> str:
    return "".join(c if apsr >> (31 - i) & 1 else "-" for i, c in enumerate("NZCVQ"))


def hex32(v: int) -> str:
    return f"{v:#010x}"


# ───────────────────── judged items of each case: (label, value) ─────────────────────

def c1_01_arithmetic(record: list[int]) -> list[tuple[str, object]]:
    if len(record) != 7 * ARITHMETIC_POINTS:
        raise SystemExit(f"c1_01_arithmetic: expected {7 * ARITHMETIC_POINTS} words, got {len(record)}")
    items = []
    for k in range(ARITHMETIC_POINTS):
        operation, first, second, flags_in, low_word, high_word, flags_out = record[7 * k:7 * k + 7]
        name = f"{ARITHMETIC_OPS[operation]} {hex32(first)}, {hex32(second)} (in {flags(flags_in)})"
        items += [(f"{name}: result", hex32(low_word)), (f"{name}: flags", flags(flags_out))]
        if ARITHMETIC_OPS[operation] in LONG_MULTIPLIES:
            items.append((f"{name}: high word", hex32(high_word)))
    return items


def c1_02_conversions(record: list[int]) -> list[tuple[str, object]]:
    expected = 4 * len(EXTENSION_VALUES) + 10 + 2 + 2 * len(CMP_LEFT)
    if len(record) != expected:
        raise SystemExit(f"c1_02_conversions: expected {expected} words, got {len(record)}")
    items = []
    for k, value in enumerate(EXTENSION_VALUES):
        items += [(f"{operation} {hex32(value)}", hex32(extended))
                  for operation, extended in zip(("SXTB", "UXTB", "SXTH", "UXTH"), record[4 * k:4 * k + 4])]
    position = 4 * len(EXTENSION_VALUES)
    loads = [f"{load} byte {byte:#04x}" for byte in (0x7F, 0x80, 0xFF) for load in ("LDRSB", "LDRB")]
    loads += [f"{load} halfword {halfword:#06x}" for halfword in (0x8000, 0x7FFF) for load in ("LDRSH", "LDRH")]
    loads += ["STRB 0x12345680 into 0xffffffff", "STRH 0x1234abcd into 0xffffffff"]
    items += [(label, hex32(word)) for label, word in zip(loads, record[position:position + 12])]
    position += 12
    for k, (left, right) in enumerate(zip(CMP_LEFT, CMP_RIGHT)):
        apsr, true_mask = record[position + 2 * k:position + 2 * k + 2]
        items += [(f"CMP {hex32(left)}, {hex32(right)}: flags", flags(apsr)),
                  (f"CMP {hex32(left)}, {hex32(right)}: true conditions",
                   " ".join(condition for bit, condition in enumerate(CMP_CONDITIONS) if true_mask >> bit & 1))]
    return items


MEMORY_LABELS = (
    "(a) STR 0x11223344, LDRB +0", "(a) LDRB +1", "(a) LDRB +2", "(a) LDRB +3",
    "(b) STRB 0xaa at +1, STRH 0xbbcc at +2 into 0xffffffff",
    "(c) LDR at +1", "(c) LDR at +2", "(c) LDR at +3", "(c) LDRH at +1", "(c) LDRH at +3",
    "(c) STR 0xdeadbeef at +1: word 0", "(c) STR 0xdeadbeef at +1: word 1",
    "(d) STMIA! base advance (bytes)", "(d) STMIA word 0 (r4)", "(d) STMIA word 1 (r5)", "(d) STMIA word 2 (r6)",
    "(d) STMIA word 3 (r7)", "(d) LDMIA r7", "(d) LDMIA r6", "(d) LDMIA r5", "(d) LDMIA r4",
    "(e) PUSH {r4-r7}: SP decrease (bytes)", "(e) [SP] (r4)", "(e) [SP + 12] (r7)",
    "(f) STRD: lower word", "(f) STRD: upper word", "(f) LDRD first", "(f) LDRD second",
    "(g) LDR [p, #4]!: value", "(g) LDR [p, #4]!: base advance", "(g) LDR [p], #4: value",
    "(g) LDR [p], #4: base advance",
)


def c1_03_memory(record: list[int]) -> list[tuple[str, object]]:
    if len(record) != len(MEMORY_LABELS):
        raise SystemExit(f"c1_03_memory: expected {len(MEMORY_LABELS)} words, got {len(record)}")
    return [(label, hex32(word)) for label, word in zip(MEMORY_LABELS, record)]


def c1_04_timebase(record: list[int]) -> list[tuple[str, object]]:
    expected = 5 + 2 * len(TIMEBASE_WAITS)
    if len(record) != expected:
        raise SystemExit(f"c1_04_timebase: expected {expected} words, got {len(record)}")
    items: list[tuple[str, object]] = [
        ("(a) consecutive reads 1 → 2 (ticks)", record[0]),
        ("(a) reads 2 → 3", record[1]),
        ("(a) reads 3 → 4", record[2]),
        ("(b) CYCCNTENA = 0: Δ across 16 NOP", record[3]),
        ("(b) CYCCNTENA = 1: Δ across 16 NOP", record[4]),
    ]
    for k, wait in enumerate(TIMEBASE_WAITS):
        dwt_ticks, timer_ticks = record[5 + 2 * k:7 + 2 * k]
        items.append((f"(c) ΔTIM2_CNT − ΔDWT over ≥ {wait} ticks", timer_ticks - dwt_ticks))
    return items


def timebase_raw(record: list[int]) -> list[str]:
    return [f"(c) wait ≥ {wait}: ΔDWT {record[5 + 2 * k]}, ΔTIM2_CNT {record[6 + 2 * k]}"
            for k, wait in enumerate(TIMEBASE_WAITS)]


def c1_05_instruction_cost(record: list[int]) -> list[tuple[str, object]]:
    expected = 2 * (1 + len(LENGTHS) * len(COST_CLASSES))
    if len(record) != expected:
        raise SystemExit(f"c1_05_instruction_cost: expected {expected} words, got {len(record)}")
    labels = ["empty (observer only)"] + [f"{name}, N = {length}" for name, _ in COST_CLASSES for length in LENGTHS]
    return [(f"{label}, {execution} execution (ticks)", record[2 * k + index])
            for k, label in enumerate(labels) for index, execution in enumerate(("1st", "2nd"))]


def class_costs(record: list[int]) -> list[float]:
    """(t32 − t16) / 16 of the 2nd execution of each class: the mean cost of instructions 17 to 32."""
    second_executions = record[3::2]    # after the empty window: one per class and length
    return [(second_executions[2 * k + 1] - second_executions[2 * k]) / 16 for k in range(len(COST_CLASSES))]


def cost_table(renode: list[int], on_board: list[int]) -> list[str]:
    rows = [f"| {name} | {unit} | {in_renode:g} | {at_board:g} | {'yes' if in_renode == at_board else 'no'} |"
            for (name, unit), in_renode, at_board in zip(COST_CLASSES, class_costs(renode), class_costs(on_board))]
    return ["Ticks per unit, (t32 − t16) / 16 of the 2nd execution: the mean over instructions 17 to 32, free "
            "of what the reads of DWT_CYCCNT add at the ends of the window.", "",
            "| Class | Unit | Renode | Board | Equal |", "|---|---|---|---|---|", *rows]


def c1_06_exception_frame(record: list[int]) -> list[tuple[str, object]]:
    expected = 1 + len(FRAME_POINTS) * FRAME_RECORD_WORDS
    if len(record) != expected:
        raise SystemExit(f"c1_06_exception_frame: expected {expected} words, got {len(record)}")
    items: list[tuple[str, object]] = [("STKALIGN at reset", record[0])]
    for k, (process_stack, misaligned, stkalign) in enumerate(FRAME_POINTS):
        words = record[1 + k * FRAME_RECORD_WORDS:1 + (k + 1) * FRAME_RECORD_WORDS]
        sp_before, registers, sp_after = words[0], words[1:7], words[7]
        frame_address, exc_return, frame = words[8], words[9], words[10:]
        name = f"{'PSP' if process_stack else 'MSP'}, SP {'misaligned' if misaligned else 'aligned'}, STKALIGN {stkalign}"
        items += [(f"{name}: frame address below SP (bytes)", sp_before - frame_address),
                  (f"{name}: EXC_RETURN", hex32(exc_return)),
                  (f"{name}: stacked PC", hex32(frame[6])),
                  (f"{name}: stacked xPSR", hex32(frame[7])),
                  (f"{name}: SP after the return − before", sp_after - sp_before)]
        items += [(f"{name}: stacked {register}", hex32(value)) for register, value in zip(FRAME_REGISTERS, frame)]
        items += [(f"{name}: {register} after the return", hex32(value)) for register, value in zip(FRAME_REGISTERS, registers)]
    return items


ITEMS = {
    "c1_01_arithmetic": c1_01_arithmetic,
    "c1_02_conversions": c1_02_conversions,
    "c1_03_memory": c1_03_memory,
    "c1_04_timebase": c1_04_timebase,
    "c1_05_instruction_cost": c1_05_instruction_cost,
    "c1_06_exception_frame": c1_06_exception_frame,
}


# ───────────────────────────── analysis ─────────────────────────────

def read_record(directory: Path, reps: int, log: str) -> list[int]:
    """The record of the case, identical across all repetitions. A run that cannot be analyzed or
    differs across repetitions stops the script: run the case again."""
    records = []
    for k in range(1, reps + 1):
        run_dir = directory / f"run-{k}"
        try:
            run = sim.read_run(run_dir, log)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"{run_dir}: {exc}; run the case again") from exc
        if run.unexpected_exception:
            raise SystemExit(f"{run_dir}: the firmware did not reach the end; run the case again")
        records.append(list(run.record))
    if any(record != records[0] for record in records):
        raise SystemExit(f"{directory}: the {reps} repetitions in {log} differ")
    return records[0]


def versus_board(case: str, renode: list[int], on_board: list[int]) -> tuple[str, list[str], list[str]]:
    renode_items, board_items = ITEMS[case](renode), ITEMS[case](on_board)
    differences = [f"{label}: Renode {in_renode}, board {at_board}"
                   for (label, in_renode), (_, at_board) in zip(renode_items, board_items) if in_renode != at_board]
    detail = [f"{len(renode_items) - len(differences)}/{len(renode_items)} items equal to the board"]
    detail += (["differences:"] + [f"  {difference}" for difference in differences]) if differences else []
    if case == "c1_04_timebase":
        detail += [f"Renode {line}" for line in timebase_raw(renode)] + [f"board {line}" for line in timebase_raw(on_board)]
    table = cost_table(renode, on_board) if case == "c1_05_instruction_cost" else []
    return ("DIVERGES" if differences else "EQUAL"), detail, table


def write_result(data: Path) -> None:
    rows, sections, judged = [], [], []
    for case, (_, code, title, _) in CASES.items():
        renode_dir, board_dir = data / "renode" / case, data / "board" / case
        if not sim.has_data(renode_dir):
            continue
        judged.append(renode_dir)
        renode_reps = sim.read_environment(renode_dir)["reps"]
        detail = [f"{renode_reps} runs in Renode"]
        renode = read_record(renode_dir, renode_reps, "renode.log")
        if not sim.has_data(board_dir):
            raise SystemExit(f"{board_dir}: no board data; run the case with --board")
        judged.append(board_dir)
        board_reps = sim.read_environment(board_dir)["reps"]
        detail.append(f"{board_reps} runs on the board")
        verdict, comparison, table = versus_board(case, renode, read_record(board_dir, board_reps, "board.log"))
        detail += comparison
        heading = f"{code} — {title} (`{case}`)"
        rows.append((heading, verdict))
        sections.append((heading, verdict, detail, table))
    lines = ["# C1 — The core", "",
             *sim.environment_table(judged, data), "",
             "| Case | Verdict (board oracle) |", "|---|---|",
             *(f"| {heading} | **{verdict}** |" for heading, verdict in rows)]
    for heading, verdict, detail, table in sections:
        lines += ["", f"## {heading}: {verdict}", "", *(table + [""] if table else []), *(f"- {line}" for line in detail)]
    (data / "result.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ───────────────────────────── execution ─────────────────────────────

def run_renode(out: Path, case: str, sym: dict[str, int]) -> None:
    _, _, _, run_ns = CASES[case]
    directory = out / case
    sim.new_case(directory, FIRMWARE, sym, SYMBOLS, {"reps": REPS})
    for k in range(1, REPS + 1):
        (directory / f"run-{k}").mkdir()
    variables = {"OUT": str(out), "REPS": str(REPS), "ELF": str(ELF),
                 "RUN_NS": str(run_ns), **{symbol.upper(): hex(sym[symbol]) for symbol in SYMBOLS}}
    sim.run_robot("c1", case, directory / "_robot", variables)


def run_board(out: Path, case: str, sym: dict[str, int]) -> None:
    number, _, _, _ = CASES[case]
    directory = out / case
    sim.new_case(directory, FIRMWARE, sym, SYMBOLS, {"reps": REPS}, renode=False)
    for k in range(1, REPS + 1):
        run_dir = directory / f"run-{k}"
        run_dir.mkdir()
        board.run(sym, number, run_dir, timeout_ms=30_000)


def select_cases(requested: list[str] | None) -> list[str]:
    if not requested:
        return list(CASES)
    by_code = {code: name for name, (_, code, _, _) in CASES.items()}
    selected = []
    for item in requested:
        name = by_code.get(item, item)
        if name not in CASES:
            raise SystemExit(f"unknown case: {item}")
        if name not in selected:
            selected.append(name)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="*", help="case IDs (e.g. C1-01 or c1_01_arithmetic); default: all")
    parser.add_argument("--board", action="store_true", help="also run the cases on the board (no wire used)")
    parser.add_argument("--analyze", action="store_true", help="only redo result.md")
    args = parser.parse_args()
    selected = select_cases(args.cases)
    if not args.analyze:
        sym = sim.firmware_symbols(FIRMWARE, build=True)
        for case in selected:
            print(f"{case} …", flush=True)
            run_renode(DATA / "renode", case, sym)
        if args.board:
            board.flash(ELF, DATA / "board" / "flash.log")
            for case in selected:
                print(f"board {case} …", flush=True)
                run_board(DATA / "board", case, sym)
    write_result(DATA)


if __name__ == "__main__":
    main()
