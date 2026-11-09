"""C2 — interrupts and timer (firmware src/c2/c2.c). Cases run in order: each one relies on the
results of the ones before it. Rules are judged against the document, time against the board.

    python3 scripts/c2.py [--cases C2-01 …] [--board] [--analyze]

Renode: each case in robot/c2.robot. Board (--board): the board-oracle cases, same ELF through
scripts/board.py; no pin is driven and no wire is used. Data: data/c2/renode/<case>/ and
data/c2/board/<case>/, each replaced when that case runs again in that environment; result.md
judges every case found.

  Rules of the NVIC and of an exception (document oracle)
  C2-01 (c2_01_pending_and_enable)        a line requested while disabled stays pending, served once enabled, active during the service
  C2-02 (c2_02_priority_and_tie)          lower priority value first, group then subpriority; on a tie, lower exception number
  C2-03 (c2_03_nested_preemption)         a request in a handler preempts it only with a strictly higher group priority
  C2-04 (c2_04_masks)                     PRIMASK, BASEPRI, BASEPRI_MAX: effect on the NVIC and value read back
  C2-05 (c2_05_wfi_and_primask)           a request wakes WFI with PRIMASK 0 and 1; served only with PRIMASK 0
  C2-06 (c2_06_tail_chaining)             pending lines served in order with no main-flow instruction between them

  Cost of an exception (board oracle)
  C2-07 (c2_07_exception_cost)            ticks of the entry, of the return and of the chaining

  Timers as the source of the request (document oracle)
  C2-08 (c2_08_timer_period)              period of the update interrupt, (PSC + 1)(ARR + 1)
  C2-09 (c2_09_repeated_request)          a request during the service, by software and by a flag left set

  What only the board answers (board oracle): uses the timer as the source
  C2-10 (c2_10_timer_tie)                 TIM2 and TIM3 pending together; a start synchronized by hardware
  C2-11 (c2_11_coalescence)               update events during a mask become one service
  C2-12 (c2_12_timer_count_at_entry)      TIM2_CNT read first in the handler
  C2-13 (c2_13_flag_clear_before_return)  re-entries with the flag cleared k instructions before the return
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

FIRMWARE = "c2"
ELF = sim.ROOT / "build" / FIRMWARE / "firmware.elf"
DATA = sim.ROOT / "data" / "c2"
SYMBOLS = ("selected_case", "record_complete", "unexpected_exception", "record_length", "record",
           "note_service_handler", "timer_service_handler", "service_count", "round_ready")
REPS = 3                    # runs per environment; a difference between them stops the analysis
NS = sim.NS_PER_TICK
MS = 1_000_000

ISPR = 0xE000E200           # NVIC set-pending, first word
TIM2_EXCEPTION, TIM3_EXCEPTION = 44, 45     # IRQ 28 and 29

# Point tables: the same order and sizes are in src/c2/c2.c.
THREE_LINES = (0, 20, 42)                   # first, middle and last line without a source on the platform
PRIORITY_TRIPLES = [(0, 7, 15), (0, 15, 7), (7, 0, 15), (7, 15, 0), (15, 0, 7), (15, 7, 0),     # strict orders
                    (7, 7, 0), (7, 7, 15), (7, 0, 7), (7, 15, 7), (0, 7, 7), (15, 7, 7),        # tie of two lines
                    (8, 8, 8), (0, 0, 0), (15, 15, 15)]                                          # tie of three
GROUPED_TRIPLES = [(5, 5, 4, 6), (5, 5, 5, 4)]      # (PRIGROUP, priorities): same group, then a full tie
TWO_LINES = (0, 42)                         # the ends of the NVIC
PRIORITY_PAIRS = [(1, 0), (8, 7), (15, 14),         # (A, B): B higher by one, at both ends and in the middle
                  (0, 0), (8, 8), (15, 15),         # equal
                  (0, 1), (8, 9), (14, 15)]         # B lower by one
GROUPED_PAIRS = [(5, 5, 4), (5, 8, 7), (4, 3, 2), (4, 8, 7), (7, 8, 7)]     # (PRIGROUP, A, B): inside the group of A, or above it
AFTER_NESTED_REQUEST = 0x100                        # exception | this: the handler after its nested request
PRIMASK_PRIORITIES = (0, 8, 15)             # highest, middle, lowest: PRIMASK holds every priority
BASEPRI_VALUES = (0x00, 0x0F, 0x10, 0x1F, 0x80, 0x8F, 0xF0, 0xFF)   # no mask, below/above the implemented bits
# (priority in BASEPRI, value written). No mask yet: 0 changes nothing, any other value sets it; mask at 8: 0, above it, equal to it, below it
BASEPRI_MAX_POINTS = ((0, 0x00), (0, 0x80), (0, 0x8F),
                      (8, 0x00), (8, 0x70), (8, 0x7F), (8, 0x80), (8, 0x8F), (8, 0x90))
GROUPED_BASEPRI_POINTS = ((4, 0x50), (5, 0x50), (7, 0x50))          # (PRIGROUP, BASEPRI): 3, 2 and no bit of group
WFI_LINE = 20                               # a line without a source, away from the ends of the NVIC
CHAIN_LINES = (0, 20, 35, 42)                       # ascending: the ends of the NVIC, two in each of its first two words
TIMER_PAIRS = ((0, 999), (9, 99), (99, 9),          # (PSC, ARR) of the same product
               (99, 3), (99, 1),                    # ARR small
               (7, 999))                            # another product, ARR large
SERVICES_PER_PAIR = 4                               # 3 periods
LEVEL_ENTRIES = 4                                   # C2-09: the handler clears the flag at this entry
TIE_UNDER_MASK = ("TIM2 started first", "TIM3 started first")
TIE_SYNCHRONIZED = ("TIM2 master", "TIM3 master")
MASK_WINDOWS = (500, 1500, 2500, 3500)              # ticks: 0, 1, 2 and 3 update events during the mask
BOARD_PERIOD = 1000                                 # (PSC + 1)(ARR + 1) ticks on the board (RM0008 §15.3.1)
EVENTS_PER_POINT = 8
ENTRY_CAPACITY = 64
CLEAR_TO_RETURN_TAILS = ("k = 0", "k = 1", "k = 2", "DSB", "read back")     # k = instructions from the clear to the return

# Stimulus by the monitor, in nanoseconds of virtual time.
WFI_SLEEP_NS, WFI_REQUEST_DELAY_NS = (200_000, 400_000), 20_000


class Item(NamedTuple):
    """One judged observation. `expected` is a value or a range of accepted values."""
    label: str
    observed: object
    expected: object
    aspect: str = ""        # a case judged in more than one aspect has one verdict for each


Judgement = tuple[list[Item], list[str]]    # items and the raw values to report beside them


# ───────────────────────────── events used by the cases ─────────────────────────────

class Return(NamedTuple):
    """Return instruction of a handler, from the exception-end hook with count N: it is
    instruction N−1 (relation verified by the instruments case)."""
    instructions: int
    ipsr: int


def entries(run: Run, handler: int) -> list[sim.AddressHook]:
    """Address hook at the first instruction of the handler."""
    return [hook for hook in run.address_hooks if hook.pc == handler]


def returns(run: Run) -> list[Return]:
    return [Return(e.instructions - 1, e.ipsr) for e in run.exception_exits]


def stop(case: str, reason: str) -> NoReturn:
    """A run that cannot be analyzed is not a result."""
    raise SystemExit(f"{case}: {reason}; run the case again")


def checked_record(case: str, run: Run, length: int) -> list[int]:
    if len(run.record) != length:
        stop(case, f"expected {length} record words, got {len(run.record)}")
    return run.record


def service_order(word: int) -> tuple[int, ...]:
    """Services encoded by service_order() in c2.c: up to 3 exceptions (9 bits each), then the total if > 3."""
    total = word >> 27
    return tuple((word >> (9 * k)) & 0x1FF for k in range(min(total, 3))) + ((total,) if total > 3 else ())


def line_request(line: int) -> tuple[str, str]:
    """Where the monitor writes to request IRQ `line`: ISPR word and bit."""
    return hex(ISPR + 4 * (line // 32)), str(1 << (line % 32))


def joined(values) -> str:
    """A list for Robot (--variable carries text; robot/c2.robot splits it at the commas)."""
    return ",".join(map(str, values))


def service_count_address(sym: dict, exception: int) -> int:
    return sym["service_count"] + 4 * exception


# ───────────────────────── rules of the NVIC and of an exception ─────────────────────────

def group_priority(value: int, prigroup: int) -> int:
    """The 8-bit priority without its subpriority bits: groupvalue = 2 << PRIGROUP (ARMv7-M §B1.5.4)."""
    return value - value % (2 << prigroup)


# Per point, before and after the enable: pending, active, services; the exception served; active in the handler.
def c2_01_pending_and_enable(run: Run, sym: dict) -> Judgement:
    record = checked_record("C2-01", run, 8 * 2 * len(THREE_LINES))
    points = [(line, source) for line in THREE_LINES for source in ("STIR", "ISPR")]
    return [Item(f"IRQ {line} requested through {source}", tuple(record[8 * k:8 * k + 8]), (1, 0, 0, 0, 0, 1, 16 + line, 1))
            for k, (line, source) in enumerate(points)], []


def c2_02_priority_and_tie(run: Run, sym: dict) -> Judgement:
    record = checked_record("C2-02", run, len(PRIORITY_TRIPLES) + len(GROUPED_TRIPLES))
    points = [(0, *triple) for triple in PRIORITY_TRIPLES] + GROUPED_TRIPLES
    return [Item(f"PRIGROUP {point[0]}, priorities {point[1:]}", service_order(word),
                 tuple(16 + line for _, line in sorted(zip(point[1:], THREE_LINES))))
            for point, word in zip(points, record)], []


# Handler B returns to the handler of A if it preempted it, else to Thread (Cortex-M3 TRM Tab. 5-6).
def c2_03_nested_preemption(run: Run, sym: dict) -> Judgement:
    record = checked_record("C2-03", run, 2 * (2 * len(PRIORITY_PAIRS) + len(GROUPED_PAIRS)))
    points = [(0, a, b, *pair) for a, b in (TWO_LINES, TWO_LINES[::-1]) for pair in PRIORITY_PAIRS]
    points += [(prigroup, *TWO_LINES, priority_a, priority_b) for prigroup, priority_a, priority_b in GROUPED_PAIRS]
    items = []
    for k, (prigroup, line_a, line_b, priority_a, priority_b) in enumerate(points):
        word, exc_return = record[2 * k:2 * k + 2]
        a, b = 16 + line_a, 16 + line_b
        preempts = (priority_b << 4) < group_priority(priority_a << 4, prigroup)
        order = (a, b, a | AFTER_NESTED_REQUEST) if preempts else (a, a | AFTER_NESTED_REQUEST, b)
        label = f"PRIGROUP {prigroup}, A = IRQ {line_a} at {priority_a}, B = IRQ {line_b} at {priority_b}"
        items.append(Item(label, service_order(word), order))
        items.append(Item(f"{label}: EXC_RETURN of B", hex(exc_return), hex(0xFFFFFFF1 if preempts else 0xFFFFFFF9)))
    return items, []


def served_priorities(mask: int, prigroup: int = 0) -> int:
    """Priorities a mask lets through, as bits: BASEPRI counts through its group bits; 0 masks nothing."""
    boost = group_priority(mask, prigroup)
    return sum(1 << p for p in range(16) if mask == 0 or (p << 4) < boost)


# BASEPRI keeps only its implemented bits (7:4); BASEPRI_MAX only raises the mask. The effect on the
# NVIC is the question of the case; the value read back is a core register read, judged beside it.
def c2_04_masks(run: Run, sym: dict) -> Judgement:
    primask_points = len(PRIMASK_PRIORITIES)
    record = checked_record("C2-04", run, primask_points + len(BASEPRI_VALUES) + len(BASEPRI_MAX_POINTS) + len(GROUPED_BASEPRI_POINTS))
    held_then_served = 0 | 1 << 4 | 1 << 8      # not served under PRIMASK, pending, served once after release
    items = [Item(f"PRIMASK, priority {p}", word, held_then_served, "effect")
             for p, word in zip(PRIMASK_PRIORITIES, record)]
    points = [(f"BASEPRI = {value:#04x}", value & 0xF0, 0) for value in BASEPRI_VALUES]
    for priority, written in BASEPRI_MAX_POINTS:
        current = priority << 4
        mask = written & 0xF0 if written != 0 and (written < current or current == 0) else current
        points.append((f"BASEPRI = {current:#04x}, BASEPRI_MAX = {written:#04x}", mask, 0))
    points += [(f"PRIGROUP {prigroup}, BASEPRI = {value:#04x}", value & 0xF0, prigroup) for prigroup, value in GROUPED_BASEPRI_POINTS]
    for (label, mask, prigroup), word in zip(points, record[primask_points:]):
        items.append(Item(label, word >> 8, served_priorities(mask, prigroup), "effect"))
        items.append(Item(label, word & 0xFF, mask, "value read"))
    return items, []


def stimulus_c2_05(sym: dict) -> dict[str, str]:
    address, value = line_request(WFI_LINE)
    return {"SLEEP_TIMES": joined(WFI_SLEEP_NS), "REQUEST_TIMES": joined(t + WFI_REQUEST_DELAY_NS for t in WFI_SLEEP_NS),
            "LINE_ADDRESS": address, "LINE_VALUE": value,
            "READS": joined(map(hex, (sym["round_ready"], service_count_address(sym, 16 + WFI_LINE))))}


# The services after each wake-up and after PRIMASK is cleared (ARMv7-M §B1.5.19). WFI is a hint that
# the architecture lets complete early, so the time asleep is reported and not judged.
def c2_05_wfi_and_primask(run: Run, sym: dict) -> Judgement:
    pauses = run.monitor_pauses
    if len(pauses) != 4 or [p.words[0] for p in pauses] != [1, 1, 2, 2]:
        stop("C2-05", "the firmware was not ready at a pause")
    record = checked_record("C2-05", run, 3)
    return ([Item("services after the wake-up with PRIMASK = 0", record[0], 1),
             Item("services after the wake-up with PRIMASK = 1", record[1], 1),
             Item("services after clearing PRIMASK", record[2], 2)],
            [f"instructions while asleep: PRIMASK = 0: {pauses[1].instructions - pauses[0].instructions}; "
             f"PRIMASK = 1: {pauses[3].instructions - pauses[2].instructions}"])


# The order of C2-02, chained: no main-flow instruction between the handlers (ARMv7-M §B1.5.12).
def c2_06_tail_chaining(run: Run, sym: dict) -> Judgement:
    served, ends = entries(run, sym["note_service_handler"]), returns(run)
    lines = len(CHAIN_LINES)
    if len(served) != 2 * lines or len(ends) != 2 * lines:
        stop("C2-06", f"{len(served)} entries and {len(ends)} returns for {2 * lines} services")
    order = tuple(16 + line for line in (*reversed(CHAIN_LINES), *CHAIN_LINES))
    items = [Item("service order", tuple(run.record), order)]
    for k in range(2 * lines):
        if k % lines == 0:      # the first entry of a round comes from main
            continue
        previous, ret, entry = served[k - 1], ends[k - 1], served[k]
        if ret.ipsr != previous.ipsr or not previous.instructions < ret.instructions < entry.instructions:
            stop("C2-06", f"transition {k}: the return is not paired with its entry")
        items.append(Item(f"transition {k}: main-flow instructions", entry.instructions - ret.instructions - 1, 0))
    return items, []


# ───────────────────────────── timers as the source ─────────────────────────────

def timer_entries(run: Run, sym: dict, exception: int) -> list[sim.AddressHook]:
    return [hook for hook in entries(run, sym["timer_service_handler"]) if hook.ipsr == exception]


def c2_08_timer_period(run: Run, sym: dict) -> Judgement:
    served = timer_entries(run, sym, TIM2_EXCEPTION)
    if len(served) != len(TIMER_PAIRS) * SERVICES_PER_PAIR:
        stop("C2-08", f"{len(served)} services for {len(TIMER_PAIRS) * SERVICES_PER_PAIR}")
    items, periods = [], []
    for k, (prescaler, auto_reload) in enumerate(TIMER_PAIRS):
        times = [x.time_ns // NS for x in served[SERVICES_PER_PAIR * k:SERVICES_PER_PAIR * (k + 1)]]
        intervals = [b - a for a, b in zip(times, times[1:])]
        periods.append(sorted(set(intervals)))
        items += [Item(f"PSC = {prescaler}, ARR = {auto_reload}, period {n + 1}", value, (prescaler + 1) * (auto_reload + 1))
                  for n, value in enumerate(intervals)]
    return items, [f"observed periods by (PSC, ARR): {periods}"]


# A line pended in its own handler is active and pending and runs once more; a level stays asserted
# while the flag is set: the handler re-enters until it clears the flag, and a clear of the pending
# state does not hold (PM0056 §4.3.9; Cortex-M3 TRM §8.3).
def c2_09_repeated_request(run: Run, sym: dict) -> Judgement:
    record = checked_record("C2-09", run, 8)
    software, level, masked = record[:3], record[3], record[4:]
    return [Item("pending in its own handler", software[0], 1, "by software"),
            Item("active in its own handler", software[1], 1, "by software"),
            Item("services", software[2], 2, "by software"),
            Item(f"entries with the flag left set up to entry {LEVEL_ENTRIES}", level, LEVEL_ENTRIES, "level of the flag"),
            Item("pending with the flag set and masked", masked[0], 1, "level of the flag"),
            Item("pending after a clear with the flag set", masked[1], 1, "level of the flag"),
            Item("pending after clearing the flag and the pending state", masked[2], 0, "level of the flag"),
            Item("services after the release", masked[3], 0, "level of the flag")], []


# ───────────────────────────── observations against the board ─────────────────────────────
# Each returns (aspect → values) and a line of context. The record of the timer cases: their own
# words, then the entry count and (TIM2_CNT, DWT_CYCCNT) per entry. Counts use the period of their
# own environment, so they do not inherit the difference judged in C2-08.

def split_record(case: str, record: list[int], case_words: int) -> tuple[list[int], list[tuple[int, int]]]:
    if len(record) <= case_words:
        stop(case, "the record is shorter than the words of the case")
    count, pairs = record[case_words], record[case_words + 1:]
    if count > ENTRY_CAPACITY or len(pairs) != 2 * count:
        stop(case, f"{count} entries, {len(pairs)} entry words")
    return record[:case_words], [(pairs[2 * i], pairs[2 * i + 1]) for i in range(count)]


def regular_entries(times: list[int]) -> list[int]:
    """Entries without the re-entries: an entry less than half a period after the previous one
    has no new update event."""
    return times[:1] + [b for a, b in zip(times, times[1:]) if b - a >= BOARD_PERIOD // 2]


def most_common_period(times: list[int]) -> int:
    intervals = [b - a for a, b in zip(times, times[1:])]
    if not intervals:
        raise SystemExit("fewer than two regular entries; run the case again")
    return Counter(intervals).most_common(1)[0][0]


def exception_cost(record: list[int]) -> tuple[dict[str, list[int]], str]:
    lines, chained = len(THREE_LINES), len(CHAIN_LINES) - 1
    if len(record) != 2 * lines + chained:
        stop("C2-07", f"expected {2 * lines + chained} record words, got {len(record)}")
    return {"entry": record[:lines], "return": record[lines:2 * lines], "chaining": record[2 * lines:]}, ""


def timer_tie(record: list[int]) -> tuple[dict[str, list[tuple[int, ...]]], str]:
    if len(record) != len(TIE_UNDER_MASK) + len(TIE_SYNCHRONIZED):
        stop("C2-10", f"expected {len(TIE_UNDER_MASK) + len(TIE_SYNCHRONIZED)} record words, got {len(record)}")
    order = [service_order(word) for word in record]
    return {"pending together": order[:len(TIE_UNDER_MASK)], "synchronized start": order[len(TIE_UNDER_MASK):]}, ""


def coalescence_losses(record: list[int]) -> tuple[dict[str, list[int]], str]:
    """Between the entry before the mask and the last entry of the point, both on the event grid,
    elapsed / period events happened; the ones without a service were lost."""
    head, pairs = split_record("C2-11", record, 3 * len(MASK_WINDOWS))
    times = [time for _, time in pairs]
    losses = []
    for k in range(len(MASK_WINDOWS)):
        masked_at, last_entry = head[3 * k], head[3 * k + 2]
        known = times[:last_entry]
        synchronizing, last, period = [t for t in known if t < masked_at][-1], known[-1], known[-1] - known[-2]
        if (last - synchronizing) % period:
            stop("C2-11", f"window {MASK_WINDOWS[k]}: the last entry is off the event grid")
        losses.append((last - synchronizing) // period - sum(1 for t in known if synchronizing < t <= last))
    return {"": losses}, f"period {most_common_period(times[-3:])}"


def timer_count_at_entry(record: list[int]) -> tuple[dict[str, list[int]], str]:
    head, pairs = split_record("C2-12", record, 2 * EVENTS_PER_POINT)
    times = [time for _, time in pairs]
    if len(times) != EVENTS_PER_POINT or len(regular_entries(times)) != len(times):
        stop("C2-12", f"{len(times)} entries for {EVENTS_PER_POINT} events (a re-entry or a miss)")
    for k, time in enumerate(times):
        if not head[2 * k] < time < head[2 * k + 1]:
            stop("C2-12", f"event {k}: the entry is not inside the NOP sled")
    return {"": [count for count, _ in pairs]}, f"period {most_common_period(times)}"


def spurious_reentries(record: list[int]) -> tuple[dict[str, list[int]], str]:
    head, pairs = split_record("C2-13", record, 2 * len(CLEAR_TO_RETURN_TAILS))
    times = [time for _, time in pairs]
    spurious = []
    period = 0
    for p, tail in enumerate(CLEAR_TO_RETURN_TAILS):
        window = times[head[2 * p]:head[2 * p + 1]]
        regular = regular_entries(window)
        if len(regular) != EVENTS_PER_POINT:
            stop("C2-13", f"{tail}: {len(regular)} update events for {EVENTS_PER_POINT}")
        spurious.append(len(window) - len(regular))
        period = most_common_period(regular)
    return {"": spurious}, f"period {period}"


def reentry_boundary(board_values: list[int], renode_values: list[int]) -> str:
    """Over the k points: the k at which a re-entry stops, on the board and in Renode."""
    points = [i for i, tail in enumerate(CLEAR_TO_RETURN_TAILS) if tail.startswith("k = ")]
    on_board = [board_values[i] > 0 for i in points]
    in_renode = [renode_values[i] > 0 for i in points]
    if len(set(on_board)) == 1:
        return "no boundary on the board"
    if on_board == in_renode:
        return "boundary reproduced"
    if len(set(in_renode)) == 1:
        return "boundary absent in the range (" + ("never re-enters" if not in_renode[0] else "always re-enters") + ")"
    return "boundary shifted"


Observation = Callable[[list[int]], tuple[dict, str]]


def within_board_range(renode: dict[str, list[int]], on_board: dict[str, list[int]]) -> Judgement:
    """Timing: each Renode value inside the range the board showed over its points."""
    items, notes = [], []
    for aspect, values in renode.items():
        accepted = range(min(on_board[aspect]), max(on_board[aspect]) + 1)
        items += [Item(f"point {k}", value, accepted, aspect) for k, value in enumerate(values)]
        notes.append(f"{aspect + ': ' if aspect else ''}board {on_board[aspect]}, Renode {values} (ticks)")
    return items, notes


# The same service order, point by point; (44, 45) is TIM2, then TIM3.
def tie_against_board(renode: dict, on_board: dict) -> Judgement:
    items = [Item(label, r, b, "pending together") for label, r, b in zip(TIE_UNDER_MASK, renode["pending together"], on_board["pending together"])]
    items += [Item(label, r, b, "synchronized start") for label, r, b in zip(TIE_SYNCHRONIZED, renode["synchronized start"], on_board["synchronized start"])]
    return items, []


def equal_to_labels(labels: tuple) -> Callable[[dict[str, list[int]], dict[str, list[int]]], Judgement]:
    """Count: the same value, point by point."""
    def compare(renode: dict[str, list[int]], on_board: dict[str, list[int]]) -> Judgement:
        items = [Item(str(label), r, b) for label, r, b in zip(labels, renode[""], on_board[""])]
        return items, [f"board {on_board['']}, Renode {renode['']} by {labels}"]
    return compare


def equal_to_tails(renode: dict[str, list[int]], on_board: dict[str, list[int]]) -> Judgement:
    items, notes = equal_to_labels(CLEAR_TO_RETURN_TAILS)(renode, on_board)
    return items, [reentry_boundary(on_board[""], renode[""]), *notes]


# ───────────────────────────── the cases, in order ─────────────────────────────

def no_stimulus(_sym: dict) -> dict[str, str]:
    return {}


@dataclass(frozen=True)
class DocumentCase:
    """Runs in Renode; the expected values come from the document."""
    number: int             # value written to selected_case before boot
    id: str
    title: str
    run_ns: int             # virtual time of each run
    judge: Callable[[Run, dict], Judgement]
    stimulus: Callable[[dict], dict[str, str]] = no_stimulus    # Robot data besides the symbols


@dataclass(frozen=True)
class BoardCase:
    """The same ELF in Renode and on the board; the board gives the expected values."""
    number: int
    id: str
    title: str
    run_ns: int
    observe: Observation
    compare: Callable[[dict, dict], Judgement]
    stimulus: Callable[[dict], dict[str, str]] = no_stimulus


# case directory name → case
CASES: dict[str, DocumentCase | BoardCase] = {
    "c2_01_pending_and_enable": DocumentCase(1, "C2-01", "pending and enable", 5 * MS, c2_01_pending_and_enable),
    "c2_02_priority_and_tie": DocumentCase(2, "C2-02", "priority and tie", 5 * MS, c2_02_priority_and_tie),
    "c2_03_nested_preemption": DocumentCase(3, "C2-03", "nested preemption", 5 * MS, c2_03_nested_preemption),
    "c2_04_masks": DocumentCase(4, "C2-04", "masks", 10 * MS, c2_04_masks),
    "c2_05_wfi_and_primask": DocumentCase(5, "C2-05", "WFI and PRIMASK", WFI_SLEEP_NS[1] + 2 * WFI_REQUEST_DELAY_NS + 100_000,
                                          c2_05_wfi_and_primask, stimulus_c2_05),
    "c2_06_tail_chaining": DocumentCase(6, "C2-06", "tail-chaining", 5 * MS, c2_06_tail_chaining),
    "c2_07_exception_cost": BoardCase(7, "C2-07", "cost of an exception", 5 * MS, exception_cost, within_board_range),
    "c2_08_timer_period": DocumentCase(8, "C2-08", "timer period", 10 * MS, c2_08_timer_period),
    "c2_09_repeated_request": DocumentCase(9, "C2-09", "request during the service", 5 * MS, c2_09_repeated_request),
    "c2_10_timer_tie": BoardCase(10, "C2-10", "tie between two timers", 5 * MS, timer_tie, tie_against_board),
    "c2_11_coalescence": BoardCase(11, "C2-11", "coalescence during a mask", 10 * MS, coalescence_losses,
                                   equal_to_labels(tuple(f"window {w}" for w in MASK_WINDOWS))),
    "c2_12_timer_count_at_entry": BoardCase(12, "C2-12", "timer count at the entry", 5 * MS, timer_count_at_entry, within_board_range),
    "c2_13_flag_clear_before_return": BoardCase(13, "C2-13", "flag clear before the return", 10 * MS, spurious_reentries, equal_to_tails),
}


# ───────────────────────────── analysis ─────────────────────────────

def read_runs(directory: Path, reps: int, log: str) -> list[Run]:
    """The runs of the case. A run that cannot be analyzed or that differs across repetitions stops
    the script: run the case again."""
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
    return f"{expected.start}–{expected.stop - 1}" if isinstance(expected, range) else str(expected)


def verdicts_by_aspect(items: list[Item]) -> dict[str, tuple[str, list[str]]]:
    """For each aspect of the case: its verdict and the lines of its detail."""
    result = {}
    for aspect in dict.fromkeys(item.aspect for item in items):
        judged = [item for item in items if item.aspect == aspect]
        differences = [f"{i.label}: observed {i.observed}, expected {shown(i.expected)}"
                       for i in judged if not matches(i.observed, i.expected)]
        prefix = f"{aspect}: " if aspect else ""
        lines = [f"{prefix}{len(judged) - len(differences)}/{len(judged)} items equal"]
        lines += [f"{prefix}differences:", *(f"  {d}" for d in differences)] if differences else []
        result[aspect] = ("DIVERGES" if differences else "EQUAL", lines)
    return result


def judge_case(data: Path, name: str, case: DocumentCase | BoardCase) -> tuple[Judgement, list[Path], list[str]]:
    """The judgement of a case, the directories it read and the lines on its runs."""
    renode_dir = data / "renode" / name
    environment = sim.read_environment(renode_dir)
    renode_runs = read_runs(renode_dir, environment["reps"], "renode.log")
    if isinstance(case, DocumentCase):
        end = renode_runs[0].record_event.time_ns
        return (case.judge(renode_runs[0], environment["symbols"]), [renode_dir],
                [f"{environment['reps']} runs in Renode; end at {end} ns"])
    board_dir = data / "board" / name
    if not sim.has_data(board_dir):
        raise SystemExit(f"{board_dir}: no board data; run the case with --board")
    board_reps = sim.read_environment(board_dir)["reps"]
    board_runs = read_runs(board_dir, board_reps, "board.log")
    renode_values, renode_context = case.observe(renode_runs[0].record)
    board_values, board_context = case.observe(board_runs[0].record)
    items, notes = case.compare(renode_values, board_values)
    if board_context or renode_context:
        notes = [*notes, f"board context: {board_context}", f"Renode context: {renode_context}"]
    return (items, notes), [renode_dir, board_dir], [f"{environment['reps']} runs in Renode", f"{board_reps} runs on the board"]


def write_result(data: Path) -> None:
    rows, sections, judged = [], [], []
    for name, case in CASES.items():
        if not sim.has_data(data / "renode" / name):
            continue
        (items, notes), directories, runs = judge_case(data, name, case)
        judged += directories
        heading = f"{case.id} — {case.title} (`{name}`)"
        oracle = "document" if isinstance(case, DocumentCase) else "board"
        aspects = verdicts_by_aspect(items)
        detail = list(runs)
        for aspect, (verdict, lines) in aspects.items():
            rows.append(f"| {case.id} — {case.title}{f', {aspect}' if aspect else ''} (`{name}`) | {oracle} | **{verdict}** |")
            detail += lines
        summary = "; ".join(f"{aspect + ': ' if aspect else ''}{verdict}" for aspect, (verdict, _) in aspects.items())
        sections.append((heading, summary, detail + notes))
    lines = ["# C2 — Interrupts and timer", "", *sim.environment_table(judged, data), "",
             "| Case | Oracle | Verdict |", "|---|---|---|", *rows]
    for heading, summary, detail in sections:
        lines += ["", f"## {heading}: {summary}", "", *(f"- {x}" for x in detail)]
    (data / "result.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ───────────────────────────── execution ─────────────────────────────

def run_renode(out: Path, name: str, case: DocumentCase | BoardCase, sym: dict[str, int]) -> None:
    directory = out / name
    sim.new_case(directory, FIRMWARE, sym, SYMBOLS, {"reps": REPS})
    for k in range(1, REPS + 1):
        (directory / f"run-{k}").mkdir()
    variables = {"OUT": str(out), "REPS": str(REPS), "ELF": str(ELF), "RUN_NS": str(case.run_ns),
                 "CASE": name, "NUMBER": str(case.number),
                 **{s.upper(): hex(sym[s]) for s in SYMBOLS}, **case.stimulus(sym)}
    sim.run_robot("c2", name, directory / "_robot", variables)


def run_board(out: Path, name: str, case: BoardCase, sym: dict[str, int]) -> None:
    directory = out / name
    sim.new_case(directory, FIRMWARE, sym, SYMBOLS, {"reps": REPS}, renode=False)
    for k in range(1, REPS + 1):
        run_dir = directory / f"run-{k}"
        run_dir.mkdir()
        board.run(sym, case.number, run_dir)


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
    parser.add_argument("--cases", nargs="*", help="case IDs (e.g. C2-01 or c2_01_pending_and_enable); default: all")
    parser.add_argument("--board", action="store_true", help="also run the board-oracle cases on the board (no wire used)")
    parser.add_argument("--analyze", action="store_true", help="only redo result.md")
    args = parser.parse_args()
    selected = select_cases(args.cases)
    if not args.analyze:
        sym = sim.firmware_symbols(FIRMWARE, build=True)
        for name in selected:
            print(f"{name} …", flush=True)
            run_renode(DATA / "renode", name, CASES[name], sym)
        board_cases = {name: case for name in selected if isinstance(case := CASES[name], BoardCase)}
        if args.board and board_cases:
            board.flash(ELF, DATA / "board" / "flash.log")
            for name, case in board_cases.items():
                print(f"board {name} …", flush=True)
                run_board(DATA / "board", name, case, sym)
    write_result(DATA)


if __name__ == "__main__":
    main()
