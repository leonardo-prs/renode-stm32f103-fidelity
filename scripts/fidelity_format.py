"""Bounded ABI-v1 decoder. read_snapshot(path) accepts only frozen captures.

Ticks are relative to MAIN's BOOT, not wall time. Equal ticks on different
writers do not establish causality. No firmware-specific result semantics live
here; ERROR captures remain readable for diagnostics.
"""

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import struct

MAGIC = 0x46494431
VERSION = 1
CORE_HZ = 8_000_000
CAPACITY = 128
SNAPSHOT_SIZE = 10368
HALF_WRAP = 1 << 31
MAX_DURATION_TICKS = 60 * CORE_HZ
WRITERS = ("MAIN", "IRQ_A", "IRQ_B")
HEADER_FIELDS = (
    "magic", "version", "scenario", "state", "error", "core_hz",
    "result_count", "trace_capacity", "result_capacity", "trace_enabled",
    "seed", "rcc_cr", "rcc_cfgr", "flash_acr", "dwt_ctrl", "prigroup",
)
EVENT_NAMES = {
    1: "BOOT", 2: "PHASE", 3: "ERROR",
    0x100: "S1_BEGIN", 0x101: "S1_END",
    0x200: "S2_ENTER", 0x201: "S2_EXIT", 0x202: "S2_MASK",
    0x203: "S2_RELEASE", 0x300: "S3_TX", 0x301: "S3_RX", 0x302: "S3_SR",
    0x400: "S4_LENTER", 0x401: "S4_REQUEST", 0x402: "S4_HENTER",
    0x403: "S4_HEXIT", 0x404: "S4_RESUME", 0x405: "S4_LEXIT",
    0x406: "S4_ARB_ENTER", 0x407: "S4_ARB_EXIT",
}


class SnapshotError(ValueError):
    """Malformed, unfrozen, or temporally ambiguous snapshot."""


@dataclass(frozen=True)
class TraceEntry:
    writer: int
    sequence: int
    raw_ticks: int
    ticks: int
    event: int
    trial: int
    arg: int

    @property
    def name(self):
        return EVENT_NAMES.get(self.event, f"UNKNOWN_{self.event:#x}")


@dataclass(frozen=True)
class Snapshot:
    header: dict
    results: tuple
    traces: tuple
    warnings: tuple
    sha256: str

    def trace_at(self, writer, sequence):
        """Reject references to uninitialized slots, even inside capacity."""
        if not 0 <= writer < 3 or not 0 <= sequence < self.header["trace_count"][writer]:
            raise SnapshotError("trace reference outside published count")
        return next(e for e in self.traces if e.writer == writer and e.sequence == sequence)

    def quality(self):
        failed = self.header["state"] == 3 or self.header["error"] != 0
        incomplete = any(self.header["trace_drop"])
        return {
            "status": "refuted" if failed else "incomplete" if incomplete else "captured",
            "frozen": True, "error": self.header["error"],
            "trace_complete": not incomplete,
            "functional_status": "requires_result_contract",
            "warnings": list(self.warnings),
            "global_equal_tick_order": "not_causal_proof",
        }


def decode_snapshot(data):
    """Decode exactly 10368 bytes; validate counts before accessing any rows."""
    if len(data) != SNAPSHOT_SIZE:
        raise SnapshotError(f"snapshot length {len(data)} != {SNAPSHOT_SIZE}")
    words = struct.unpack("<2592I", data)
    h = dict(zip(HEADER_FIELDS, words[:16]))
    h.update(trace_count=list(words[16:19]), trace_drop=list(words[19:22]),
             reserved=list(words[22:32]))
    for key, value in (("magic", MAGIC), ("version", VERSION),
                       ("core_hz", CORE_HZ), ("trace_capacity", CAPACITY),
                       ("result_capacity", CAPACITY), ("trace_enabled", 1)):
        if h[key] != value:
            raise SnapshotError(f"invalid {key}: {h[key]}")
    if h["scenario"] not in (1, 2, 3, 4):
        raise SnapshotError("invalid scenario")
    if h["state"] not in (2, 3):
        raise SnapshotError("snapshot is not frozen DONE/ERROR")
    if h["result_count"] > CAPACITY or any(n > CAPACITY for n in h["trace_count"]):
        raise SnapshotError("published count exceeds capacity")
    results = tuple(tuple(words[32 + 8*i:40 + 8*i]) for i in range(h["result_count"]))
    raw = []
    for writer, count in enumerate(h["trace_count"]):
        for seq in range(count):
            offset = 1056 + (writer * CAPACITY + seq) * 4
            ticks, event, trial, arg = words[offset:offset+4]
            if event not in EVENT_NAMES:
                raise SnapshotError(f"unknown/uninitialized event {event:#x}")
            raw.append((writer, seq, ticks, event, trial, arg))
    boots = [e for e in raw if e[3] == 1]
    if len(boots) != 1 or boots[0][:2] != (0, 0):
        raise SnapshotError("exactly one MAIN[0] BOOT required")
    base = boots[0][2]
    entries = []
    for writer in range(3):
        last_raw, elapsed = base, 0
        for w, seq, ticks, event, trial, arg in (r for r in raw if r[0] == writer):
            delta = (ticks - last_raw) & 0xffffffff
            if delta >= HALF_WRAP:
                raise SnapshotError("backwards/ambiguous writer timestamp")
            elapsed += delta
            if elapsed >= HALF_WRAP or elapsed >= MAX_DURATION_TICKS:
                raise SnapshotError("timeline span violates half-wrap or <60s bound")
            entries.append(TraceEntry(w, seq, ticks, elapsed, event, trial, arg))
            last_raw = ticks
    entries.sort(key=lambda e: (e.ticks, e.writer, e.sequence))
    warnings = []
    if any(h["trace_drop"]):
        warnings.append("trace drops: spans/order invariants cannot be certified")
    groups = {}
    for e in entries:
        groups.setdefault(e.ticks, set()).add(e.writer)
    if any(len(writers) > 1 for writers in groups.values()):
        warnings.append("equal-tick cross-writer order is ambiguous; sorting is presentation only")
    if h["state"] == 3 or h["error"]:
        warnings.append("ERROR capture: diagnostic only, not functional success")
    return Snapshot(h, results, tuple(entries), tuple(warnings), hashlib.sha256(data).hexdigest())


def read_snapshot(path):
    return decode_snapshot(Path(path).read_bytes())


def scenario_number(value):
    if isinstance(value, str) and value in ("s1", "s2", "s3", "s4"):
        return int(value[1:])
    if type(value) is int and value in (1, 2, 3, 4):
        return value
    raise ValueError("invalid manifest scenario")


def validate_manifest(snapshot, manifest):
    """Bind capture to declared inputs. Missing identity is never paired proof."""
    if scenario_number(manifest.get("scenario")) != snapshot.header["scenario"]:
        raise ValueError("manifest scenario does not match snapshot")
    if manifest.get("seed") != snapshot.header["seed"]:
        raise ValueError("manifest seed does not match snapshot")
    declared = manifest.get("snapshot", {})
    if "sha256" in declared and declared["sha256"] != snapshot.sha256:
        raise ValueError("snapshot SHA-256 does not match manifest")
    if "bytes" in declared and declared["bytes"] != SNAPSHOT_SIZE:
        raise ValueError("manifest snapshot size mismatch")
    if "header" in declared:
        for key, value in declared["header"].items():
            if key in snapshot.header and value != snapshot.header[key]:
                raise ValueError(f"manifest snapshot header mismatch: {key}")
    if "config_sha256" in manifest:
        actual = hashlib.sha256(json.dumps(manifest.get("config", {}), sort_keys=True).encode()).hexdigest()
        if manifest["config_sha256"] != actual:
            raise ValueError("manifest configuration hash mismatch")


def validate_event_order(events, expected):
    """Check an exact sequence without inventing cross-writer tie causality.

    Caller must filter to the relevant trial/protocol first. Publication order
    proves order within a writer, strictly increasing ticks across writers.
    Trace completeness is a separate prerequisite enforced by the analyzer.
    """
    events = list(events)
    if [e.event for e in events] != list(expected):
        return {"status": "refuted", "reason": "event sequence differs"}
    ambiguous = False
    for left, right in zip(events, events[1:]):
        if right.ticks < left.ticks:
            return {"status": "refuted", "reason": "backwards order"}
        if left.writer == right.writer:
            if right.sequence <= left.sequence:
                return {"status": "refuted", "reason": "backwards publication order"}
        elif left.ticks == right.ticks:
            ambiguous = True
    return {"status": "ambiguous" if ambiguous else "observed",
            "reason": "cross-writer timestamp tie" if ambiguous else "trace order only"}
