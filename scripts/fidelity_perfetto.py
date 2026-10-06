"""Export validated ABI-v1 traces, no external dependencies.

Usage: python scripts/fidelity_perfetto.py snapshot.bin --manifest run.json
       --out trace.json [--csv trace.csv]
X spans describe C instrumentation, not architectural exception cost.
"""

import argparse
import csv
import json
from pathlib import Path

try:
    from .fidelity_format import WRITERS, read_snapshot
except ImportError:
    from fidelity_format import WRITERS, read_snapshot

SPAN_PAIRS = {0x100: 0x101, 0x200: 0x201, 0x400: 0x405,
              0x402: 0x403, 0x406: 0x407}
END_EVENTS = set(SPAN_PAIRS.values())


def clock_domain(manifest):
    backend = manifest.get("backend", manifest.get("environment",
                        manifest.get("platform")))
    if isinstance(backend, dict):
        backend = backend.get("backend", backend.get("environment"))
    if backend in ("hardware", "hw"):
        return "DWT core cycles; nominal 8MHz"
    if backend == "renode":
        return "DWT virtual timer 8MHz"
    raise ValueError("manifest backend must explicitly be hardware/hw or renode")


def match_spans(snapshot):
    """Pair only same writer/trial, using writer publication order, with nesting.

    Invalid matching emits explicit failures, never a fabricated span. Dropped
    captures are diagnostic only even when an individual span looks matched.
    """
    spans, failures = [], []
    for writer in range(3):
        stack = []
        for e in sorted((e for e in snapshot.traces if e.writer == writer),
                        key=lambda e: e.sequence):
            if e.event in SPAN_PAIRS:
                if any(begin.trial != e.trial for begin in stack):
                    failures.append(f"{WRITERS[writer]} overlapping trials at {e.sequence}")
                    stack.clear()
                if any(begin.event == e.event for begin in stack):
                    failures.append(f"{WRITERS[writer]} duplicate open span at {e.sequence}")
                    stack.clear()
                stack.append(e)
            elif e.event in END_EVENTS:
                if not stack or SPAN_PAIRS[stack[-1].event] != e.event or stack[-1].trial != e.trial:
                    failures.append(f"{WRITERS[writer]} unmatched/misnested end at {e.sequence}")
                    stack.clear()
                else:
                    spans.append((stack.pop(), e))
        failures.extend(f"{WRITERS[writer]} unmatched begin at {e.sequence}" for e in stack)
    return spans, failures


def trace_rows(snapshot):
    return [{"writer": WRITERS[e.writer], "sequence": e.sequence,
             "ticks": e.ticks, "raw_ticks": e.raw_ticks, "event": e.event,
             "name": e.name, "trial": e.trial, "arg": e.arg}
            for e in snapshot.traces]


def write_trace_csv(snapshot, path):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("writer", "sequence", "ticks",
                                "raw_ticks", "event", "name", "trial", "arg"))
        writer.writeheader()
        writer.writerows(trace_rows(snapshot))


def build_trace(snapshot, manifest):
    domain = clock_domain(manifest)
    spans, failures = match_spans(snapshot)
    quality = snapshot.quality()
    quality["span_failures"] = failures
    quality["span_status"] = ("refuted" if failures else "diagnostic_only"
                              if quality["status"] != "captured" else "observed")
    events = [{"ph": "M", "name": "process_name", "pid": 1,
               "args": {"name": domain}},
              {"ph": "M", "name": "clock_domain", "pid": 1,
               "args": {"domain": domain, "conversion": "ticks / 8 nominal microseconds",
                        "origin": "MAIN BOOT", "tie_order": "not causal proof",
                        "mips": manifest.get("mips", manifest.get("config", {}).get("mips")),
                        "quantum": manifest.get("quantum", manifest.get("config", {}).get("quantum"))}},
              {"ph": "M", "name": "capture_quality", "pid": 1, "args": quality}]
    for writer, name in enumerate(WRITERS):
        events.append({"ph": "M", "name": "thread_name", "pid": 1, "tid": writer,
                       "args": {"name": name + " (physical writer; C instrumentation)"}})
    def args(e):
        return {"event": e.event, "trial": e.trial, "arg": e.arg,
                "ticks": e.ticks, "raw_ticks": e.raw_ticks, "sequence": e.sequence,
                "tick_domain": domain}
    for e in snapshot.traces:
        events.append({"ph": "i", "s": "t", "pid": 1, "tid": e.writer,
                       "name": e.name, "ts": e.ticks / 8, "args": args(e)})
    for begin, end in spans:
        extra = args(begin)
        extra.update(end_ticks=end.ticks, end_raw_ticks=end.raw_ticks,
                     instrumented_span="C boundaries, excludes architectural return",
                     certified=False, diagnostic_only=quality["status"] != "captured" or bool(failures))
        events.append({"ph": "X", "pid": 1, "tid": begin.writer,
                       "name": begin.name + " (C instrumented span)",
                       "ts": begin.ticks / 8, "dur": (end.ticks - begin.ticks) / 8,
                       "args": extra})
    return {"traceEvents": events, "displayTimeUnit": "us",
            "metadata": {"clock_domain": domain, "quality": quality}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--csv")
    opts = parser.parse_args(argv)
    try:
        snapshot = read_snapshot(opts.snapshot)
        manifest = json.loads(Path(opts.manifest).read_text())
        trace = build_trace(snapshot, manifest)
        Path(opts.out).write_text(json.dumps(trace, indent=2) + "\n")
        if opts.csv:
            write_trace_csv(snapshot, opts.csv)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"fidelity_perfetto: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
