"""C3 — GPIO and EXTI: how an external event reaches the firmware, and where on that path Renode
stops behaving like the chip (firmware src/c3/c3.c). Cases run in order: each one relies on the
ones before it. Rules are judged against the document and time against the board; C3-06, whose
capture is a measure of time, goes to the board whole, its filter included (one oracle per case).

    python3 scripts/c3.py [--cases C3-01 …] [--board] [--analyze]

Renode: each case in robot/c3.robot, with the links of the bench in renode/c3_links.repl. Board
(--board): C3-06 and C3-07, same ELF through scripts/board.py, wires L2, L3 and L4 mounted. Data:
data/c3/renode/<case>/ and data/c3/board/<case>/, each replaced when that case runs again in that
environment; result.md judges every case found.

Oracles (RM0008 = STM32F10x reference manual):
  C3-01 (c3_01_output_registers)  ODR, BSRR and BRR read back (§9.1.2, §9.2.5); IDR of an output with
                                  no wire follows each level change (§9.1.8: the pin is sampled into
                                  IDR every APB2 cycle); a write to an input does not reach the
                                  line (§9.1.7); both write paths                          document
  C3-02 (c3_02_input_pull)        each change of the pull changes IDR, by both paths (§9.1.7, Tab. 20)  document
  C3-03 (c3_03_driven_line)       each link carries the level written (§9.1.7, §9.1.8)     document
  C3-04 (c3_04_exti_routing)      entries only on the selected edges and port (§9.4.3, §10.2.4)  document
  C3-05 (c3_05_exti_pending)      when an event stays pending and when it is lost (§10.2.2 Fig. 20:
                                  PR is after the AND with IMR; §10.3.6; Yiu, The Definitive Guide,
                                  §7.6); an edge wakes the core from WFI (§5.3.3, Tab. 12) and is
                                  served before the code after it (Yiu §9.2.4, Tab. 9.4)  document
  C3-06 (c3_06_input_capture)     (a) both captures, and CCR2 − CCR1 against the DWT_CYCCNT
                                  difference of the same edges; (b) the input filter (§15.3.5,
                                  §15.3.6, §15.4.7), item by item                          board
  C3-07 (c3_07_event_response)    ticks from the event to the handler and from pin to pin, core
                                  running                                                  board

Time with the core asleep is not judged: the board runs with a debugger connected, and the core does
not allow HCLK to be turned off during a debug session (§31.16.1).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import board
import sim

FIRMWARE = "c3"
ELF = sim.ROOT / "build" / FIRMWARE / "firmware.elf"
DATA = sim.ROOT / "data" / "c3"
SYMBOLS = ("selected_case", "record_complete", "unexpected_exception", "record_length", "record")
REPS = 3                    # runs per environment; a difference between them stops the analysis
MS = 1_000_000

# case directory name → (selected_case number, case ID, short title, virtual run time in ns)
CASES = {
    "c3_01_output_registers": (1, "C3-01", "output registers and input isolation",  5 * MS),
    "c3_02_input_pull":       (2, "C3-02", "internal pull on a free pin",           5 * MS),
    "c3_03_driven_line":      (3, "C3-03", "driven line between pins",              5 * MS),
    "c3_04_exti_routing":     (4, "C3-04", "AFIO routing and EXTI0 edges",          5 * MS),
    "c3_05_exti_pending":     (5, "C3-05", "EXTI pending and lost events",         10 * MS),
    "c3_06_input_capture":    (6, "C3-06", "input capture and filter",             10 * MS),
    "c3_07_event_response":   (7, "C3-07", "response time to an event",            20 * MS),
}
BOARD_CASES = ("c3_06_input_capture", "c3_07_event_response")

PA3, PA4 = 1 << 3, 1 << 4
CC1IF, CC2IF = 1 << 1, 1 << 2       # TIM2_SR (RM0008 §15.4.5)

# Point tables: the same values and order are in src/c3/c3.c.
PATHS = ("ODR", "BSRR/BRR")         # the two write paths of the output data
# (previous level, path of the change): each direction by each path; the previous level comes from BSRR/BRR
LEVEL_PREVIOUS = [0, 1, 0, 1]
LEVEL_PATHS = ["ODR", "ODR", "BSRR", "BRR"]
PULL_NAMES = ["pull-down", "pull-up"]
LINKS = ("L2 PA6 → PA0", "L3 PA7 → PA1", "L4 PA5 → PB0")
LINK_LEVELS = 3             # the source at 0, 1, 0
# (name, entries after the rise, after the fall); each edge pin with its port and with the other one
ROUTING_POINTS = [("port A, rising, edge on PA0", 1, 0),
                  ("port A, falling, edge on PA0", 0, 1),
                  ("port A, both, edge on PA0", 1, 1),
                  ("port A, both, edge on PB0", 0, 0),
                  ("port B, both, edge on PB0", 1, 1),
                  ("port B, both, edge on PA0", 0, 0)]
# (label, expected) of each word of C3-05, in the order of the record
PENDING_ITEMS = [("masked line: EXTI_PR after the rise", 0),
                 ("masked line: entries once unmasked", 0),
                 ("NVIC disabled: EXTI_PR after the rise", 1),
                 ("NVIC disabled: entries before the enable", 0),
                 ("NVIC disabled: entries after the enable", 1),
                 ("pulse over: EXTI_PR", 1),
                 ("pulse over: IDR0", 0),
                 ("pulse over: entries after the enable", 1),
                 ("two rises with the NVIC disabled: entries after the enable", 1),
                 ("rise in the handler before the clear: entries", 1),
                 ("rise in the handler after the clear: entries", 2)]
CAPTURE_POINTS = ("TI1 by L2, rise → fall, near", "TI1 by L2, rise → fall, far",
                  "TI1 by L2 → TI2 by L3, rise → rise, near", "TI1 by L2 → TI2 by L3, rise → rise, far")
# no filter: the control; N = 8 at f_CK_INT rejects the short pulse only (RM0008 §15.4.7)
FILTER_POINTS = ("IC1F = 0, short (2 stores)", "IC1F = 0, long (24 NOPs)",
                 "IC1F = 3, short (2 stores)", "IC1F = 3, long (24 NOPs)")
RESPONSE_MEASURES = ("event to handler, by the compare interrupt", "event to handler, by the pin", "pin to pin")
EVENTS_PER_POINT = 8


def check_length(case: str, record: list[int], expected: int) -> None:
    if len(record) != expected:
        raise SystemExit(f"{case}: expected {expected} words, got {len(record)}; run the case again")


# ───────────── document-oracle items of each case: (label, observed, expected) ─────────────

Item = tuple[str, object, object]


def level_changes(words: list[int], name) -> list[Item]:
    """Each level change is one item, the pair of reads: a pin that keeps its level fails it in
    either direction, and no read passes alone."""
    return [(name(previous, path), (words[2 * k], words[2 * k + 1]), (previous, previous ^ 1))
            for k, (previous, path) in enumerate(zip(LEVEL_PREVIOUS, LEVEL_PATHS))]


def output_register_items(record: list[int]) -> list[Item]:
    check_length("c3_01_output_registers", record, 5 + 2 * len(LEVEL_PREVIOUS) + 4)
    read_back = [("ODR = PA3 | PA4", PA3 | PA4), ("ODR = PA3", PA3), ("BSRR sets PA4: PA3 stays", PA3 | PA4),
                 ("BRR resets PA3: PA4 stays", PA4), ("BSRR sets and resets PA4: BS has priority", PA4)]
    items: list[Item] = [(f"{label}: ODR read back", word, expected)
                         for (label, expected), word in zip(read_back, record)]
    items += level_changes(record[5:13], lambda previous, path: f"PA4 output, {previous} → {previous ^ 1} via {path}: IDR4 before, after")
    words = record[13:17]
    for k, path in enumerate(PATHS):
        items.append((f"PA6 input, writing 1 by {path}: IDR0 before, after", (words[2 * k], words[2 * k + 1]), (0, 0)))
    return items


def input_pull_items(record: list[int]) -> list[Item]:
    check_length("c3_02_input_pull", record, 2 * len(LEVEL_PREVIOUS))
    return level_changes(record, lambda previous, path: f"{PULL_NAMES[previous]} → {PULL_NAMES[previous ^ 1]} via {path}: IDR4 before, after")


def driven_line_items(record: list[int]) -> list[Item]:
    """The rise and the fall of each link: (source, destination) before and after."""
    check_length("c3_03_driven_line", record, 2 * LINK_LEVELS * len(LINKS))
    items: list[Item] = []
    for k, link in enumerate(LINKS):
        low, high, low_again = (tuple(record[6 * k + 2 * j:6 * k + 2 * j + 2]) for j in range(LINK_LEVELS))
        items += [(f"{link}, rise: (source, destination) before, after", (low, high), ((0, 0), (1, 1))),
                  (f"{link}, fall: (source, destination) before, after", (high, low_again), ((1, 1), (0, 0)))]
    return items


def exti_routing_items(record: list[int]) -> list[Item]:
    check_length("c3_04_exti_routing", record, 2 * len(ROUTING_POINTS))
    words = iter(record)
    return [(f"{name}: entries (rise, fall)", (next(words), next(words)), (rise, fall))
            for name, rise, fall in ROUTING_POINTS]


def exti_pending_items(record: list[int]) -> list[Item]:
    check_length("c3_05_exti_pending", record, len(PENDING_ITEMS) + 2 * EVENTS_PER_POINT)
    items: list[Item] = [(label, word, expected) for (label, expected), word in zip(PENDING_ITEMS, record)]
    wake = record[len(PENDING_ITEMS):]
    items.append(("edge with the core in WFI: entries at each wake-up", wake[::2], [1] * EVENTS_PER_POINT))
    return items


def wake_ticks(record: list[int]) -> list[int]:
    """Ticks from the compare to the first read with the core in WFI: reported, not judged."""
    return sorted(set(record[len(PENDING_ITEMS) + 1::2]))


# ───────────── board-oracle items of C3-06: (label, value), compared item by item ─────────────

Value = tuple[str, object]


def capture_parts(record: list[int]) -> tuple[list[int], list[int]]:
    """The words of the capture points and of the filter points."""
    capture_words = 3 * len(CAPTURE_POINTS)
    check_length("c3_06_input_capture", record, capture_words + len(FILTER_POINTS))
    return record[:capture_words], record[capture_words:]


def capture_items(record: list[int]) -> list[Value]:
    """The capture flags, and how far CCR2 − CCR1 is from the DWT_CYCCNT difference of the same
    two edges. The residual, not the width: the wait between the edges may differ per environment."""
    words = iter(capture_parts(record)[0])
    items: list[Value] = []
    for name in CAPTURE_POINTS:
        flags, difference, dwt = next(words), next(words), next(words)
        items += [(f"{name}: CC1IF | CC2IF", f"{flags:#x}"),
                  (f"{name}: (CCR2 − CCR1) − DWT difference (ticks)", difference - dwt)]
    return items


def filter_items(record: list[int]) -> list[Value]:
    return [(f"{label}: CC1IF", int(word != 0)) for label, word in zip(FILTER_POINTS, capture_parts(record)[1])]


# ───────────────────────────── board-oracle measures of C3-07 ─────────────────────────────

Measures = dict[str, list[int | str]]


def response_values(record: list[int]) -> Measures:
    """Per measure, the value of each event. An event outside the NOP sled does not answer the
    question of its point: the run stops."""
    case = "c3_07_event_response"
    check_length(case, record, 3 * EVENTS_PER_POINT * len(RESPONSE_MEASURES))
    words = iter(record)
    values: Measures = {}
    for measure in RESPONSE_MEASURES:
        row: list[int | str] = []
        for _ in range(EVENTS_PER_POINT):
            value, flags, valid = next(words), next(words), next(words)
            if not valid:
                raise SystemExit(f"{case}: {measure}: the event fell outside the NOP sled; run the case again")
            # pin to pin reads two captures: without both, there is no interval to compare
            missing = measure == "pin to pin" and flags != CC1IF | CC2IF
            row.append(f"captures {flags:#x}" if missing else value)
        values[measure] = row
    return values


def response_aspect(measure: str, renode: Measures, on_board: Measures) -> tuple[str, list[str]]:
    """EQUAL if every Renode value lies inside the range the board showed for that measure."""
    b = [v for v in on_board[measure] if isinstance(v, int)]
    if len(b) != EVENTS_PER_POINT:
        raise SystemExit(f"c3_07_event_response: {measure}: the board did not capture; run the case again")
    r = renode[measure]
    equal = all(isinstance(v, int) and min(b) <= v <= max(b) for v in r)
    return ("EQUAL" if equal else "DIVERGES"), [f"board {min(b)}–{max(b)} ticks; Renode {sorted(set(map(str, r)))}"]


# ───────────────────────────── verdicts ─────────────────────────────
# Each judge gives the parts of its case: (part, verdict, detail lines). `renode` and `board_` are
# the records of all repetitions (board_ is None for a case that runs only in Renode).

Part = tuple[str, str, list[str]]


def identical(records: list[list[int]], where: str) -> list[int]:
    """The record of a case, the same in every repetition; a difference stops the analysis."""
    if any(r != records[0] for r in records):
        raise SystemExit(f"{where}: the {len(records)} repetitions differ; run the case again")
    return records[0]


def document_verdict(items: list[Item]) -> tuple[str, list[str]]:
    equal = sum(observed == expected for _, observed, expected in items)
    rows = [f"{label}: observed {observed}, document {expected}{'' if observed == expected else '  ← differs'}"
            for label, observed, expected in items]
    return ("EQUAL" if equal == len(items) else "DIVERGES"), [f"{equal}/{len(items)} items equal to the document", *rows]


def judge_output_registers(renode: list[list[int]], _board: None) -> list[Part]:
    return [("document", *document_verdict(output_register_items(identical(renode, "C3-01"))))]


def judge_input_pull(renode: list[list[int]], _board: None) -> list[Part]:
    return [("document", *document_verdict(input_pull_items(identical(renode, "C3-02"))))]


def judge_driven_line(renode: list[list[int]], _board: None) -> list[Part]:
    return [("document", *document_verdict(driven_line_items(identical(renode, "C3-03"))))]


def judge_exti_routing(renode: list[list[int]], _board: None) -> list[Part]:
    return [("document", *document_verdict(exti_routing_items(identical(renode, "C3-04"))))]


def judge_exti_pending(renode: list[list[int]], _board: None) -> list[Part]:
    record = identical(renode, "C3-05")
    verdict, detail = document_verdict(exti_pending_items(record))
    return [("document", verdict, [*detail, f"compare to the first read, core in WFI (observed, not judged): {wake_ticks(record)} ticks"])]


def board_verdict(renode: list[Value], on_board: list[Value]) -> tuple[str, list[str]]:
    equal = sum(r == b for (_, r), (_, b) in zip(renode, on_board))
    rows = [f"{label}: Renode {r}, board {b}{'' if r == b else '  ← differs'}"
            for (label, r), (_, b) in zip(renode, on_board)]
    return ("EQUAL" if equal == len(renode) else "DIVERGES"), [f"{equal}/{len(renode)} items equal to the board", *rows]


def judge_input_capture(renode: list[list[int]], board_: list[list[int]]) -> list[Part]:
    r, b = identical(renode, "C3-06 in Renode"), identical(board_, "C3-06 on the board")
    return [("(a) capture, board", *board_verdict(capture_items(r), capture_items(b))),
            ("(b) filter, board", *board_verdict(filter_items(r), filter_items(b)))]


def judge_event_response(renode: list[list[int]], board_: list[list[int]]) -> list[Part]:
    r = response_values(identical(renode, "C3-07 in Renode"))
    b = response_values(identical(board_, "C3-07 on the board"))
    parts: list[Part] = [(f"{measure}, board", *response_aspect(measure, r, b)) for measure in RESPONSE_MEASURES]
    by_compare, by_pin = RESPONSE_MEASURES[:2]
    added = (f"the path through the pin adds: board {int(b[by_pin][0]) - int(b[by_compare][0])} ticks; "
             f"Renode {int(r[by_pin][0]) - int(r[by_compare][0])} ticks")
    parts[1] = (parts[1][0], parts[1][1], [*parts[1][2], added])
    return parts


JUDGES = {
    "c3_01_output_registers": judge_output_registers,
    "c3_02_input_pull": judge_input_pull,
    "c3_03_driven_line": judge_driven_line,
    "c3_04_exti_routing": judge_exti_routing,
    "c3_05_exti_pending": judge_exti_pending,
    "c3_06_input_capture": judge_input_capture,
    "c3_07_event_response": judge_event_response,
}


# ───────────────────────────── analysis ─────────────────────────────

def read_records(directory: Path, log: str) -> list[list[int]]:
    """The record of each repetition of a case. A run that cannot be analyzed stops the script:
    run the case again."""
    records = []
    for k in range(1, sim.read_environment(directory)["reps"] + 1):
        run_dir = directory / f"run-{k}"
        try:
            run = sim.read_run(run_dir, log)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"{run_dir}: {exc}; run the case again") from exc
        if run.unexpected_exception:
            raise SystemExit(f"{run_dir}: the firmware did not reach the end; run the case again")
        records.append(run.record)
    return records


def write_result(data: Path) -> None:
    rows, sections, judged = [], [], []
    for case, (_, code, title, _) in CASES.items():
        r_dir, b_dir = data / "renode" / case, data / "board" / case
        if not sim.has_data(r_dir):
            continue
        judged.append(r_dir)
        board_records = None
        if case in BOARD_CASES:
            if not sim.has_data(b_dir):
                raise SystemExit(f"{b_dir}: no board data; run the case with --board")
            judged.append(b_dir)
            board_records = read_records(b_dir, "board.log")
        heading = f"{code} — {title} (`{case}`)"
        for part, v, detail in JUDGES[case](read_records(r_dir, "renode.log"), board_records):
            rows.append((heading, part, v))
            sections.append((f"{heading}, {part}", v, detail))
    lines = ["# C3 — GPIO and EXTI", "",
             *sim.environment_table(judged, data), "",
             "| Case | Oracle / part | Verdict |", "|---|---|---|",
             *(f"| {heading} | {part} | **{v}** |" for heading, part, v in rows)]
    for title, v, detail in sections:
        lines += ["", f"## {title}: {v}", "", *(f"- {x}" for x in detail)]
    (data / "result.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ───────────────────────────── execution ─────────────────────────────

def run_renode(out: Path, case: str, sym: dict[str, int]) -> None:
    _, _, _, run_ns = CASES[case]
    d = out / case
    sim.new_case(d, FIRMWARE, sym, SYMBOLS, {"reps": REPS})
    for k in range(1, REPS + 1):
        (d / f"run-{k}").mkdir()
    variables = {"OUT": str(out), "REPS": str(REPS), "ELF": str(ELF),
                 "RUN_NS": str(run_ns), **{s.upper(): hex(sym[s]) for s in SYMBOLS}}
    sim.run_robot("c3", case, d / "_robot", variables)


def run_board(out: Path, case: str, sym: dict[str, int]) -> None:
    number, _, _, _ = CASES[case]
    d = out / case
    sim.new_case(d, FIRMWARE, sym, SYMBOLS, {"reps": REPS}, renode=False)
    for k in range(1, REPS + 1):
        r = d / f"run-{k}"
        r.mkdir()
        board.run(sym, number, r, timeout_ms=30_000)


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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", help="case IDs (e.g. C3-01 or c3_01_output_registers); default: all")
    ap.add_argument("--board", action="store_true", help="also run C3-06 and C3-07 on the board (L2, L3 and L4 mounted)")
    ap.add_argument("--analyze", action="store_true", help="only redo result.md")
    args = ap.parse_args()
    selected = select_cases(args.cases)
    if not args.analyze:
        sym = sim.firmware_symbols(FIRMWARE, build=True)
        for case in selected:
            print(f"{case} …", flush=True)
            run_renode(DATA / "renode", case, sym)
        on_board = [case for case in selected if case in BOARD_CASES] if args.board else []
        if on_board:
            board.flash(ELF, DATA / "board" / "flash.log")
            for case in on_board:
                print(f"board {case} …", flush=True)
                run_board(DATA / "board", case, sym)
    write_result(DATA)


if __name__ == "__main__":
    main()
