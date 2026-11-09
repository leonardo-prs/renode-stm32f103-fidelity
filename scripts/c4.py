"""C4 — serial link: USART2 (transmitter, TX on PA2) → link L1 → USART3 (receiver, RX on PB11),
by polling; only C4-05 takes an interrupt (firmware src/c4/c4.c). Cases run in order: each one
relies on the ones before it. C4-01 to C4-05 have the same configuration at both ends and are
judged against the document; C4-06, the line (ends that disagree, a pin not connected), against
the board: the document gives no outcome outside the receiver's tolerance, and one oracle per case.

    python3 scripts/c4.py [--cases C4-02 …] [--board] [--analyze]

Renode: each case in robot/c4.robot with the UART hub in its default mode (UH-A); C4-06 also in
the strict mode (UH-E). Board (--board): the same ELF, C4-06, through scripts/board.py, link L1
mounted. Data: data/c4/uh-a/<case>/, data/c4/uh-e/c4_06_line_mismatch/ and
data/c4/board/c4_06_line_mismatch/, each replaced when that case runs again in that condition;
result.md judges every case found.

  C4-01 (c4_01_link_enable)        words cross only with TE and RE (RM0008 §27.3.2,
                                   §27.3.3, §27.6.4)                                     document
  C4-02 (c4_02_equal_link)         8N1 at 9600 and 115 200: reception and transmitter
                                   (§27.3.2, §27.3.3)                                    document
  C4-03 (c4_03_frame_format)       9N1, 8E1, 7E1, 8N2 at both ends: value, flags and frame
                                   time (§27.3.3, §27.3.7, §27.6.2)                      document
  C4-04 (c4_04_slow_consumer)      read deferred past RXNE: words lost, ORE (§27.3.3)    document
  C4-05 (c4_05_receive_interrupt)  one handler entry per word, none without RXNEIE
                                   (§27.4)                                               document
  C4-06 (c4_06_line_mismatch)      the class of each point: a transmitter rate or format the
                                   receiver does not expect, PA2 not connected (§27.3.5,
                                   §9.1.4), in both hubs                                 board
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple, NoReturn

import board
import sim
from sim import Run

FIRMWARE = "c4"
ELF = sim.ROOT / "build" / FIRMWARE / "firmware.elf"
DATA = sim.ROOT / "data" / "c4"
SYMBOLS = ("selected_case", "record_complete", "unexpected_exception", "record_length", "record")
REPS = 3                    # runs per environment; a difference between them stops the analysis
MS = 1_000_000

MAX_EVENTS = 24                     # src/c4/c4.c C4_MAX_EVENTS
WRITE, READ, SEEN = 0, 1, 2         # event kinds (src/c4/c4.c)
PE, FE, NE, ORE, RXNE, TC = 0x01, 0x02, 0x04, 0x08, 0x20, 0x40     # USART_SR bits
ERRORS = PE | FE | NE | ORE
Q_POLL = 120                        # a polled instant lags its flag by at most the rest of the turn that
                                    # missed it and one turn that served the other end (about 56 cycles
                                    # each at 0 wait states), so a span between two is known within 120
BRR_9600, BRR_115200 = 832, 69      # bit time in cycles (src/c4/c4.c)
FRAME_115200 = 10 * BRR_115200
LATER = 1 << 32                     # the document gives no upper bound for the first RXNE

# Point tables: the same order and sizes are in src/c4/c4.c.
WORDS_01 = [0x5A, 0xA5]
POINTS_01 = ["control", "RE = 0", "TE = 0"]
READ_01 = [tuple(WORDS_01), (), ()]
WORDS_02 = [0x00, 0xFF, 0x55, 0xAA, 0x01, 0x80, 0x7F, 0xFE]
BRR_02 = [BRR_9600, BRR_115200]
FORMATS_03 = ["9N1", "8E1", "7E1", "8N2"]
WORDS_03 = [[0x1A5, 0x0A5, 0x15A, 0x05A], [0x0A5, 0x1A5, 0x1A7, 0x0A7], [0x0A5, 0x025, 0x027, 0x0A7],
            [0x0A5, 0x0A7, 0x05A, 0x000]]
# The parity bit replaces the MSB of the frame, and the value read carries it (§27.3.7, §27.6.2).
READ_03 = [[0x1A5, 0x0A5, 0x15A, 0x05A], [0x0A5, 0x0A5, 0x1A7, 0x1A7], [0x0A5, 0x0A5, 0x027, 0x027],
           [0x0A5, 0x0A7, 0x05A, 0x000]]
BITS_03 = [11, 11, 10, 11]          # bits per frame: start, data or data and parity, stop bits
D_04 = [345, 1035, 2415]
WORDS_04 = [0x61, 0x62, 0x63, 0x64, 0x65, 0x66]
WORDS_05 = [0x31, 0x32, 0x33, 0x34]
BRR_06 = [832, 831, 808, 858, 800, 770, 904]       # transmitter rates of C4-06; the receiver is at 832
WORD_06 = 0x55
WORDS_06 = 8


class Event(NamedTuple):
    t: int          # DWT_CYCCNT
    kind: int
    sr: int
    value: int


class Burst(NamedTuple):
    total: int                  # events that happened (only the first MAX_EVENTS are recorded)
    events: list[Event]

    def of(self, kind: int) -> list[Event]:
        return [e for e in self.events if e.kind == kind]


class Item(NamedTuple):
    """One judged observation. `expected` is a value or a range of accepted values."""
    label: str
    observed: object
    expected: object
    aspect: str = ""        # a case judged in more than one aspect has one verdict for each


Judgement = tuple[list[Item], list[str]]    # items and the raw values to report beside them


def stop(case: str, reason: str) -> NoReturn:
    """A run that cannot be analyzed is not a result."""
    raise SystemExit(f"{case}: {reason}; run the case again")


def bursts(case: str, record: list[int], expected: int) -> list[Burst]:
    """The record of a run as `expected` bursts (layout in src/c4/c4.c)."""
    words, out, i = record, [], 0
    while i < len(words):
        count = words[i]
        n = min(count, MAX_EVENTS)
        pairs = words[i + 1:i + 1 + 2 * n]
        if len(pairs) != 2 * n:
            stop(case, f"burst {len(out)}: truncated record")
        out.append(Burst(count, [Event(pairs[2 * k], pairs[2 * k + 1] >> 30, (pairs[2 * k + 1] >> 16) & 0x3FF,
                                       pairs[2 * k + 1] & 0x1FF) for k in range(n)]))
        i += 1 + 2 * n
    if len(out) != expected:
        stop(case, f"{len(out)} bursts recorded, {expected} expected")
    return out


def complete(case: str, b: Burst, label: str) -> Burst:
    if b.total > MAX_EVENTS:
        stop(case, f"{label}: {b.total} events, record holds {MAX_EVENTS}")
    return b


def reads(b: Burst) -> list[tuple[int, int]]:
    return [(e.value, e.sr & ERRORS) for e in b.of(READ)]


def values(b: Burst) -> tuple[int, ...]:
    return tuple(e.value for e in b.of(READ))


def flags_or(got: list[tuple[int, int]]) -> int:
    out = 0
    for _, f in got:
        out |= f
    return out


def around(center: int) -> range:
    return range(center - Q_POLL, center + Q_POLL + 1)


def span(events: list[Event]) -> int | None:
    """Ticks from the first event to the last; each interval alone carries the jitter of the loop."""
    return events[-1].t - events[0].t if len(events) > 1 else None


# ───────────────────────────── the cases, in order ─────────────────────────────

# The base of the ladder: without a negative control, words that arrive say nothing about the
# configuration. Without RE the receiver does not search for a start bit (§27.3.3, §27.6.4);
# without TE the transmitter sends nothing (§27.3.2, §27.6.4).
def c4_01_link_enable(run: Run) -> Judgement:
    case = "c4_01_link_enable"
    items = [Item(f"{POINTS_01[k]}: words read", values(complete(case, b, POINTS_01[k])), READ_01[k])
             for k, b in enumerate(bursts(case, run.record, len(POINTS_01)))]
    return items, []


# Reception: the 8 words, no error flag, the first RXNE no earlier than 9.5 bits after the first
# write (the frame starts at the write or later, and the word is not complete before the stop bit
# is sampled at its middle, §27.3.2, §27.3.3), and contiguous frames every 10 bits.
# Transmitter: TXE rises when a frame starts (§27.3.2), so from the second write on the writes are
# one frame apart; TC stays 0 while another word follows (§27.3.2 Fig. 282).
def c4_02_equal_link(run: Run) -> Judgement:
    case = "c4_02_equal_link"
    items, notes = [], []
    for k, b in enumerate(bursts(case, run.record, len(BRR_02))):
        bit = BRR_02[k]
        complete(case, b, f"BRR {bit}")
        w, r, got = b.of(WRITE), b.of(READ), reads(b)
        frames = len(WORDS_02) - 1
        items += [Item(f"BRR {bit}: words read", values(b), tuple(WORDS_02), "reception"),
                  Item(f"BRR {bit}: error flags of each word", tuple(f for _, f in got), (0,) * len(WORDS_02), "reception"),
                  Item(f"BRR {bit}: latency write→1st RXNE", latency(case, b), range(bit * 19 // 2, LATER), "reception"),
                  Item(f"BRR {bit}: span of RXNE over {frames} frames", span(r), around(frames * 10 * bit), "reception"),
                  Item(f"BRR {bit}: span of writes 2–8 over {frames - 1} frames", span(w[1:]),
                       around((frames - 1) * 10 * bit), "transmitter"),
                  Item(f"BRR {bit}: TC before writes 2–8", tuple(bool(e.sr & TC) for e in w[1:]),
                       (False,) * frames, "transmitter")]
        notes.append(f"BRR {bit}: intervals between writes {[y.t - x.t for x, y in zip(w, w[1:])]}, "
                     f"between RXNE {[y.t - x.t for x, y in zip(r, r[1:])]}")
    return items, notes


def latency(case: str, b: Burst) -> int:
    w, r = b.of(WRITE), b.of(READ)
    if not w or not r:
        stop(case, "burst without writes or reads")
    return r[0].t - w[0].t


# The same format at both ends: what DR returns with M and parity, no error flag, and contiguous
# frames as long as the format (§27.3.3: with 2 stop bits RXNE is set at the end of the first, so
# the frames still follow each other every 11 bits).
def c4_03_frame_format(run: Run) -> Judgement:
    case = "c4_03_frame_format"
    items = []
    for k, b in enumerate(bursts(case, run.record, len(FORMATS_03))):
        complete(case, b, FORMATS_03[k])
        frames = len(READ_03[k]) - 1
        items += [Item(f"{FORMATS_03[k]}: words read", values(b), tuple(READ_03[k]), "value and flags"),
                  Item(f"{FORMATS_03[k]}: error flags of each word", tuple(f for _, f in reads(b)),
                       (0,) * len(READ_03[k]), "value and flags"),
                  Item(f"{FORMATS_03[k]}: span of RXNE over {frames} frames", span(b.of(READ)),
                       around(frames * BITS_03[k] * BRR_115200), "frame time")]
    return items, []


# Contiguous frames: word j is complete j frames after word 0. With RXNE = 1 from word 0 until the
# first read at D, the words with j·frame < D are lost and ORE is set (§27.3.3); the others arrive.
# Reading SR then DR clears ORE (§27.6.1), so only the first read carries it.
def c4_04_slow_consumer(run: Run) -> Judgement:
    case = "c4_04_slow_consumer"
    items = []
    for k, b in enumerate(bursts(case, run.record, len(D_04))):
        complete(case, b, f"D {D_04[k]}")
        lost = [j for j in range(1, len(WORDS_04)) if j * FRAME_115200 < D_04[k]]
        arrived = tuple(w for j, w in enumerate(WORDS_04) if j not in lost)
        items += [Item(f"read deferred {D_04[k]} cycles: words read", values(b), arrived),
                  Item(f"read deferred {D_04[k]} cycles: error flags of each read", tuple(f for _, f in reads(b)),
                       (ORE if lost else 0,) + (0,) * (len(arrived) - 1))]
    return items, []


# RXNE and RXNEIE make the request (§27.4 Fig. 302). Reading DR clears RXNE, so one entry per word
# means no re-entry. USART3 is the only line with a handler (src/c4/c4.c): any other ends the run.
def c4_05_receive_interrupt(run: Run) -> Judgement:
    case = "c4_05_receive_interrupt"
    off, by_flag, on = (complete(case, b, "handler") for b in bursts(case, run.record, 3))
    entries = on.of(READ)
    items = [Item("RXNEIE = 0: handler entries", off.total, 0),
             Item("RXNEIE = 0: RXNE set by the word", bool(by_flag.events[0].sr & RXNE), True),
             Item("RXNEIE = 0: word read", by_flag.events[0].value, WORDS_05[0]),
             Item("RXNEIE = 1: handler entries", on.total, len(WORDS_05)),
             Item("RXNEIE = 1: words read in the handler", values(on), tuple(WORDS_05)),
             Item("RXNEIE = 1: RXNE at each entry", tuple(bool(e.sr & RXNE) for e in entries), (True,) * len(entries))]
    return items, []


def delta(brr_tx: int) -> float:
    """Deviation of the bit time of the transmitter from the receiver's. RM0008 Tab. 193 is read as
    a tolerance in bit time: the samples of the last bit must fall inside the transmitter's frame
    (§27.3.3), and 3.75 % is 3/8 of a bit in a 10-bit frame."""
    return brr_tx / BRR_9600 - 1


POINTS_06 = [*(f"Δ {100 * delta(brr):+.2f} % (BRR {brr})" for brr in BRR_06),
             "8N2 → 8N1", "7E1 → 7O1", "PA2 not alternate function"]


def class_06(b: Burst) -> str:
    """'ok' (8 words right, no flag), 'flags' (8 words right, with flags), 'data' (a word wrong or
    another number of words) or 'none' (nothing arrived)."""
    got = reads(b)
    count = b.total - WORDS_06 if b.total > MAX_EVENTS else len(got)
    if count == 0:
        return "none"
    if count != WORDS_06 or any(v != WORD_06 for v, _ in got):
        return "data"
    return "flags" if flags_or(got) else "ok"


def detail_06(b: Burst) -> str:
    got = reads(b)
    flags = Counter(n for _, f in got for n, bit in (("PE", PE), ("FE", FE), ("NE", NE), ("ORE", ORE)) if f & bit)
    return (f"{class_06(b)} ({len(got)} reads, {sum(v != WORD_06 for v, _ in got)} wrong"
            + "".join(f", {name} {k}" for name, k in flags.items()) + ")")


# The line, which the UART hub of Renode does not carry: it joins the two USARTs by characters.
# Outside the tolerance the document gives no outcome (§27.3.5), so the board is the oracle of the
# case, every point included; where the document speaks (inside the tolerance, 8N2 → 8N1 by §27.3.3,
# 7E1 → 7O1 by §27.3.7, PA2 by §9.1.4) it gives the same class. Each point is compared by its class.
def c4_06_line_mismatch(renode: Run, on_board: Run) -> Judgement:
    case = "c4_06_line_mismatch"
    items, notes = [], []
    for label, r, b in zip(POINTS_06, bursts(case, renode.record, len(POINTS_06)),
                           bursts(case, on_board.record, len(POINTS_06))):
        items.append(Item(label, class_06(r), class_06(b)))
        notes.append(f"{label}: Renode {detail_06(r)}; board {detail_06(b)}")
    return items, notes


@dataclass(frozen=True)
class Case:
    number: int             # value written to selected_case before boot
    id: str
    title: str
    run_ns: int             # virtual time of each run
    judge: Callable[[Run], Judgement] | None = None                 # document oracle (Renode run)
    against_board: Callable[[Run, Run], Judgement] | None = None    # board oracle (Renode run, board run)
    hubs: tuple[str, ...] = ("uh-a",)


# case directory name → case
CASES: dict[str, Case] = {
    "c4_01_link_enable": Case(1, "C4-01", "link enable", 10 * MS, judge=c4_01_link_enable),
    "c4_02_equal_link": Case(2, "C4-02", "equal link", 30 * MS, judge=c4_02_equal_link),
    "c4_03_frame_format": Case(3, "C4-03", "frame format", 10 * MS, judge=c4_03_frame_format),
    "c4_04_slow_consumer": Case(4, "C4-04", "slow consumer", 5 * MS, judge=c4_04_slow_consumer),
    "c4_05_receive_interrupt": Case(5, "C4-05", "receive interrupt", 5 * MS, judge=c4_05_receive_interrupt),
    # the strict hub (UH-E) only here: before C4-06 both ends always agree
    "c4_06_line_mismatch": Case(6, "C4-06", "line mismatch", 500 * MS, against_board=c4_06_line_mismatch,
                                hubs=("uh-a", "uh-e")),
}


# ───────────────────────────── analysis ─────────────────────────────

def read_runs(directory: Path, log: str) -> list[Run]:
    """The runs of the case. A run that cannot be analyzed or that differs across repetitions stops
    the script: run the case again."""
    reps = sim.read_environment(directory)["reps"]
    runs = []
    for k in range(1, reps + 1):
        run_dir = directory / f"run-{k}"
        try:
            run = sim.read_run(run_dir, log)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"{run_dir}: {exc}; run the case again") from exc
        if run.unexpected_exception:
            raise SystemExit(f"{run_dir}: the firmware did not reach the end; run the case again")
        runs.append(run)
    if len({sim.repetition_signature(run) for run in runs}) != 1:
        raise SystemExit(f"{directory}: the {reps} repetitions in {log} differ")
    return runs


def matches(observed: object, expected: object) -> bool:
    if isinstance(expected, range):
        return observed in expected
    return observed == expected


def shown(expected: object) -> str:
    if isinstance(expected, range):
        return f"≥ {expected.start}" if expected.stop == LATER else f"{expected.start}–{expected.stop - 1}"
    return str(expected)


def verdicts_by_aspect(items: list[Item]) -> dict[str, tuple[str, list[str]]]:
    """For each aspect of the case: its verdict and the lines of its detail."""
    result = {}
    for aspect in dict.fromkeys(item.aspect for item in items):
        judged = [item for item in items if item.aspect == aspect]
        differences = [f"{i.label}: observed {i.observed}, expected {shown(i.expected)}"
                       for i in judged if not matches(i.observed, i.expected)]
        lines = [f"{len(judged) - len(differences)}/{len(judged)} items equal"]
        lines += ["differences:", *(f"  {d}" for d in differences)] if differences else []
        result[aspect] = ("DIVERGES" if differences else "EQUAL", lines)
    return result


def write_result(data: Path) -> None:
    rows, sections, judged = [], [], []

    def report(name: str, oracle: str, judgement: Judgement, header: list[str]) -> None:
        case = CASES[name]
        items, notes = judgement
        title = f"{case.id} — {case.title} (`{name}`)"
        for aspect, (verdict, lines) in verdicts_by_aspect(items).items():
            what = f"{title}{f', {aspect}' if aspect else ''}"
            rows.append(f"| {what} | {oracle} | **{verdict}** |")
            sections.append((f"{what}, {oracle}", verdict, header + lines + notes))

    for name, case in CASES.items():
        if not sim.has_data(data / case.hubs[0] / name):
            continue
        board_runs: list[Run] = []
        if case.against_board:
            board_dir = data / "board" / name
            if not sim.has_data(board_dir):
                raise SystemExit(f"{board_dir}: no board data; run the case with --board")
            board_runs = read_runs(board_dir, "board.log")
        for hub in case.hubs:
            hub_dir = data / hub / name
            if not sim.has_data(hub_dir):
                raise SystemExit(f"{hub_dir}: no data; run the case again")
            runs = read_runs(hub_dir, "renode.log")
            judged.append(hub_dir)
            header = [f"{len(runs)} runs in Renode; end at {runs[0].record_event.time_ns} ns"]
            if case.against_board:
                report(name, f"Renode {hub.upper()} against the board", case.against_board(runs[0], board_runs[0]),
                       [*header, f"{len(board_runs)} runs on the board"])
            elif case.judge:
                report(name, f"document, Renode {hub.upper()}", case.judge(runs[0]), header)
        if case.against_board:
            judged.append(data / "board" / name)
    lines = ["# C4 — Serial link", "", *sim.environment_table(judged, data), "",
             "| Case | Oracle | Verdict |", "|---|---|---|", *rows]
    for heading, verdict, detail in sections:
        lines += ["", f"## {heading}: {verdict}", "", *(f"- {x}" for x in detail)]
    (data / "result.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ───────────────────────────── execution ─────────────────────────────

def run_renode(out: Path, name: str, sym: dict[str, int], strict: bool) -> None:
    case, directory = CASES[name], out / name
    hub = "UH-E (StrictMode)" if strict else "UH-A (default)"
    sim.new_case(directory, FIRMWARE, sym, SYMBOLS, {"reps": REPS, "hub": hub})
    for k in range(1, REPS + 1):
        (directory / f"run-{k}").mkdir()
    variables = {"OUT": str(out), "REPS": str(REPS), "ELF": str(ELF), "RUN_NS": str(case.run_ns),
                 "CASE": name, "NUMBER": str(case.number), "STRICT": str(strict),
                 **{s.upper(): hex(sym[s]) for s in SYMBOLS}}
    sim.run_robot("c4", name, directory / "_robot", variables)


def run_board(out: Path, name: str, sym: dict[str, int]) -> None:
    directory = out / name
    sim.new_case(directory, FIRMWARE, sym, SYMBOLS, {"reps": REPS}, renode=False)
    for k in range(1, REPS + 1):
        run_dir = directory / f"run-{k}"
        run_dir.mkdir()
        board.run(sym, CASES[name].number, run_dir, timeout_ms=30_000)


def select_cases(requested: list[str] | None) -> list[str]:
    if not requested:
        return list(CASES)
    by_id = {case.id: name for name, case in CASES.items()}
    selected = []
    for item in requested:
        name = by_id.get(item, item)
        if name not in CASES:
            raise SystemExit(f"unknown case: {item}")
        if name not in selected:
            selected.append(name)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="*", help="case IDs (e.g. C4-02 or c4_02_equal_link); default: all")
    parser.add_argument("--board", action="store_true", help="also run C4-06 on the board (link L1 mounted)")
    parser.add_argument("--analyze", action="store_true", help="only redo result.md")
    args = parser.parse_args()
    selected = select_cases(args.cases)
    if not args.analyze:
        sym = sim.firmware_symbols(FIRMWARE, build=True)
        for name in selected:
            print(f"{name} …", flush=True)
            for hub in CASES[name].hubs:
                run_renode(DATA / hub, name, sym, hub == "uh-e")
        board_cases = [name for name in selected if CASES[name].against_board]
        if args.board and board_cases:
            board.flash(ELF, DATA / "board" / "flash.log")
            for name in board_cases:
                print(f"board {name} …", flush=True)
                run_board(DATA / "board", name, sym)
    write_result(DATA)


if __name__ == "__main__":
    main()
