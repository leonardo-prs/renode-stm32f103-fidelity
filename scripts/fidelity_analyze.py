#!/usr/bin/env python3
"""Analyze frozen ABI-v1 captures; never an automatic equivalence oracle.

Usage:
  python3 scripts/fidelity_analyze.py RUNDIR --out OUTDIR
  python3 scripts/fidelity_analyze.py RUNDIR --compare OTHER_RUNDIR --out OUTDIR

RUNDIR holds snapshot.bin + manifest.json from fidelity_collect.py. Outputs:
rows.csv, trace.csv, summary.json and ecdf.csv. Ticks stay primary; ticks/8
microseconds are nominal 8MHz conversions (HW core cycles or RN virtual DWT
ticks), never wall time. Runs are the independent experimental units; trials
inside one snapshot may be correlated. Observed maxima are not WCET.
"""

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

try:
    from . import fidelity_format as fmt
    from .fidelity_perfetto import build_trace, write_trace_csv
except ImportError:
    import fidelity_format as fmt
    from fidelity_perfetto import build_trace, write_trace_csv

# Result contract v1: row = [trial, condition, a, b, c, d, e, f], one row per
# trial. Firmware must implement exactly these condition codes and field names.
RESULT_CONTRACT = {
    1: {"name": "s1_core_mem",
        "conditions": {1: "empty_bracket", 2: "alu_dep", 3: "mul", 4: "div",
                       5: "branch", 6: "sram_rw", 7: "calibration"},
        "fields": ("expected_checksum", "actual_checksum", "iterations",
                   "reserved", "reserved", "reserved")},
    2: {"name": "s2_timer_irq",
        "conditions": {1: "busy_leisurely", 2: "wfi_leisurely",
                       3: "busy_masked_release", 4: "wfi_masked_release",
                       5: "disabled_source"},
        "fields": ("serviced", "expected", "coalesced", "min_gap_ticks",
                   "max_gap_ticks", "flags_end")},
    3: {"name": "s3_usart",
        "conditions": {1: "leisurely_10ms", 2: "burst", 3: "blackout_ore",
                       4: "ore_recovery"},
        "fields": ("tx_bytes", "rx_bytes", "ore_events", "recovery_ok",
                   "checksum_ok", "first_byte_retained")},
    4: {"name": "s4_preemption",
        "conditions": {1: "positive_preempt", 2: "neg_same_group_sub",
                       3: "neg_equal_priority", 4: "swap_preempt",
                       5: "arbitration"},
        "fields": ("order_ok", "low_active_at_henter", "ipsr_at_henter",
                   "msp_delta", "h_pending_after", "reserved")},
}
S1_CALIBRATION_CONDITION = 7
S1_EMPTY_BRACKET_CONDITION = 1
S4_ORDER = (0x400, 0x401, 0x402, 0x403, 0x404, 0x405)
S4_NEGATIVE = (2, 3)
S4_ARBITRATION = 5


def nearest_rank(values, p):
    """Nearest-rank quantile; n must justify the requested rank."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(p * len(ordered)) - 1)
    return ordered[index]


def describe(values):
    values = list(values)
    if not values:
        return {"n": 0}
    return {
        "n": len(values), "min": values[0] if len(values) == 1 else min(values),
        "max": values[0] if len(values) == 1 else max(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def ecdf(values):
    ordered = sorted(values)
    n = len(ordered)
    return [(value, (index + 1) / n) for index, value in enumerate(ordered)]


def rows_as_dicts(snapshot):
    contract = RESULT_CONTRACT[snapshot.header["scenario"]]
    names = ("trial", "condition") + contract["fields"]
    return [dict(zip(names, row)) for row in snapshot.results]


def trials_with(snapshot, *events):
    wanted = set(events)
    grouped = {}
    for entry in snapshot.traces:
        if entry.event in wanted:
            grouped.setdefault(entry.trial, []).append(entry)
    return grouped


def finding(identifier, status, detail):
    return {"id": identifier, "status": status, "detail": detail}


def check_s1(snapshot, rows):
    out = []
    brackets = trials_with(snapshot, 0x100, 0x101)
    bad = []
    durations = {}
    for trial, entries in sorted(brackets.items()):
        begins = [e for e in entries if e.event == 0x100]
        ends = [e for e in entries if e.event == 0x101]
        if len(begins) != 1 or len(ends) != 1 or ends[0].ticks < begins[0].ticks:
            bad.append(trial)
            continue
        durations[trial] = ends[0].ticks - begins[0].ticks
    if bad:
        out.append(finding("s1.brackets", "refuted", f"bad BEGIN/END bracket trials={bad}"))
    elif not durations:
        out.append(finding("s1.brackets", "incomplete", "no S1_BEGIN/S1_END events"))
    else:
        out.append(finding("s1.brackets", "observed",
                           f"{len(durations)} bracket(s); durations ticks: {describe(durations.values())}"))
    if rows:
        bad_rows = [r["trial"] for r in rows if r["expected_checksum"] != r["actual_checksum"]]
        # empty_bracket runs no iteration kernel: zero iterations is by design.
        bad_iters = [r["trial"] for r in rows
                     if r["condition"] != S1_EMPTY_BRACKET_CONDITION and r["iterations"] == 0]
        unknown = [r["trial"] for r in rows if r["condition"] not in RESULT_CONTRACT[1]["conditions"]]
        if bad_rows or bad_iters or unknown:
            out.append(finding("s1.functional", "refuted",
                               f"checksum mismatch={bad_rows} zero_iters={bad_iters} unknown_cond={unknown}"))
        else:
            out.append(finding("s1.functional", "observed",
                               f"checksums equal on {len(rows)} row(s)"))
        baseline = [r for r in rows if r["condition"] == 1]
        out.append(finding("s1.empty_bracket", "observed" if baseline else "incomplete",
                           f"{len(baseline)} empty-bracket row(s)"))
    else:
        out.append(finding("s1.functional", "incomplete", "no result rows"))
    return out, durations


def check_s2(snapshot, rows):
    out = []
    enters = trials_with(snapshot, 0x200)
    all_enters = sorted((e for e in snapshot.traces if e.event == 0x200),
                        key=lambda e: (e.ticks, e.sequence))
    gaps = [b.ticks - a.ticks for a, b in zip(all_enters, all_enters[1:])]
    pairs_ok, pairs_bad = 0, []
    for trial, entries in enters.items():
        enters_n = sum(1 for e in entries if e.event == 0x200)
        exits_n = sum(1 for e in snapshot.traces
                      if e.trial == trial and e.event == 0x201)
        if enters_n == exits_n and enters_n > 0:
            pairs_ok += 1
        else:
            pairs_bad.append(trial)
    if pairs_bad:
        out.append(finding("s2.enter_exit", "refuted", f"unbalanced trials={pairs_bad}"))
    else:
        out.append(finding("s2.enter_exit", "observed", f"{pairs_ok} balanced trial(s)"))
    masks = [e for e in snapshot.traces if e.event == 0x202]
    releases = [e for e in snapshot.traces if e.event == 0x203]
    bad_mask = [m.trial for m in masks
                if not any(r.trial == m.trial and r.ticks > m.ticks for r in releases)]
    if bad_mask:
        out.append(finding("s2.mask_release", "refuted", f"unreleased MASK trials={bad_mask}"))
    else:
        out.append(finding("s2.mask_release", "observed",
                           f"{len(masks)} MASK / {len(releases)} RELEASE event(s)"))
    out.append(finding("s2.interarrival", "observed" if gaps else "incomplete",
                       f"ENTER gap ticks: {describe(gaps) if gaps else 'none'}"))
    if rows:
        mismatches = [r["trial"] for r in rows
                      if r["expected"] and r["serviced"] != r["expected"] - r["coalesced"]]
        out.append(finding("s2.serviced", "observed" if not mismatches else "refuted",
                           f"rows={len(rows)} mismatched_trials={mismatches}"))
    else:
        out.append(finding("s2.serviced", "incomplete", "no result rows"))
    return out, gaps


def check_s3(snapshot, rows):
    out = []
    if rows:
        integrity = [r["trial"] for r in rows
                     if r["rx_bytes"] > r["tx_bytes"] or
                     (r["condition"] in (1, 2, 4) and
                      (r["rx_bytes"] != r["tx_bytes"] or r["checksum_ok"] == 0))]
        out.append(finding("s3.payload", "refuted" if integrity else "observed",
                           f"rows={len(rows)} integrity_failures={integrity}"))
        blackout = [r for r in rows if r["condition"] == 3]
        if blackout:
            provoked = all(r["ore_events"] > 0 for r in blackout)
            out.append(finding("s3.ore_model_gap",
                               "observed" if provoked else "model_limitation",
                               "HW expected ORE under blackout; Renode STM32_UART never "
                               f"raises ORE: ore_events={[(r['trial'], r['ore_events']) for r in blackout]} "
                               "(RN zero = known model gap, not a functional pass)"))
        recovery = [r for r in rows if r["condition"] == 4]
        if recovery:
            out.append(finding("s3.ore_recovery",
                               "observed" if all(r["recovery_ok"] and r["first_byte_retained"]
                                                 for r in recovery) else "refuted",
                               "SR->DR recovery with retained old RDR byte"))
    else:
        out.append(finding("s3.payload", "incomplete", "no result rows"))
    tx = [e for e in snapshot.traces if e.event == 0x300]
    rx = [e for e in snapshot.traces if e.event == 0x301]
    out.append(finding("s3.tx_rx_events", "observed" if tx and rx else "incomplete",
                       f"TX={len(tx)} RX={len(rx)} SR/ORE={sum(1 for e in snapshot.traces if e.event == 0x302)}"))
    return out


def check_s4(snapshot, rows):
    out = []
    by_trial = trials_with(snapshot, 0x400, 0x401, 0x402, 0x403, 0x404, 0x405,
                           0x406, 0x407)
    cond_by_trial = {r["trial"]: r["condition"] for r in rows}
    for trial, entries in sorted(by_trial.items()):
        condition = cond_by_trial.get(trial)
        chain = sorted((e for e in entries if e.event in S4_ORDER),
                       key=lambda e: (e.ticks, e.writer, e.sequence))
        verdict = fmt.validate_event_order(chain, S4_ORDER)
        if condition in S4_NEGATIVE:
            lexits = [e for e in chain if e.event == 0x405]
            henters = [e for e in chain if e.event == 0x402]
            nested = bool(lexits and henters and
                          any(h.ticks < lexits[0].ticks for h in henters))
            out.append(finding(f"s4.trial{trial}.non_preempt",
                               "refuted" if nested else "observed",
                               f"condition={condition} nested_during_low={nested}"))
        elif condition == S4_ARBITRATION:
            arb = [e for e in entries if e.event in (0x406, 0x407)]
            status = "observed" if [e.event for e in sorted(arb, key=lambda e: (e.ticks, e.sequence))] == [0x406, 0x407] else "refuted"
            out.append(finding(f"s4.trial{trial}.arbitration", status,
                               "both-pending release order (arbitration, not preemption)"))
        else:
            out.append(finding(f"s4.trial{trial}.preempt", verdict["status"],
                               verdict["reason"]))
    if rows:
        bad_evidence = [r["trial"] for r in rows
                        if r["condition"] in (1, 4) and r["low_active_at_henter"] == 0]
        out.append(finding("s4.low_active_evidence",
                           "refuted" if bad_evidence else "observed",
                           f"trials missing low-active-at-HENTER={bad_evidence}"))
    else:
        out.append(finding("s4.low_active_evidence", "incomplete", "no result rows"))
    return out


def analyze_run(run_dir):
    run_dir = Path(run_dir)
    snapshot = fmt.read_snapshot(run_dir / "snapshot.bin")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    fmt.validate_manifest(snapshot, manifest)
    rows = rows_as_dicts(snapshot)
    scenario = snapshot.header["scenario"]
    checks = {1: check_s1, 2: check_s2, 3: check_s3, 4: check_s4}[scenario]
    findings, extra = checks(snapshot, rows), None
    if scenario in (1, 2):
        findings, extra = findings
    samples = {"bracket_ticks": [], "interarrival_ticks": []}
    if scenario == 1 and extra:
        samples["bracket_ticks"] = sorted(extra.values())
    if scenario == 2 and extra:
        samples["interarrival_ticks"] = sorted(extra)
    config = manifest.get("config", {})
    summary = {
        "run": str(run_dir), "sha256": snapshot.sha256,
        "quality": snapshot.quality(),
        "scenario": RESULT_CONTRACT[scenario]["name"],
        "environment": manifest.get("environment"),
        "mips_policy": config.get("mips_policy"), "mips": config.get("mips"),
        "quantum": config.get("quantum"),
        "tick_domain": ("DWT core cycles; nominal 8MHz"
                        if manifest.get("environment") == "hw"
                        else "DWT virtual timer 8MHz; not CPU cycles"),
        "independent_unit": "run (snapshot); intra-run trials may be correlated",
        "observer_note": "DWT read and logging have context-dependent cost; "
                         "empty-bracket rows quantify it, single subtraction not assumed",
        "findings": findings,
        "condition_stats": {},
    }
    for condition, name in RESULT_CONTRACT[scenario]["conditions"].items():
        selected = [r for r in rows if r["condition"] == condition]
        if selected:
            summary["condition_stats"][name] = {
                field: describe(r[field] for r in selected)
                for field in RESULT_CONTRACT[scenario]["fields"]
            } | {"n_rows": len(selected),
                 "fields": RESULT_CONTRACT[scenario]["fields"]}
    if scenario == 1 and extra:
        summary["bracket_ticks"] = {str(t): d for t, d in extra.items()}
    if scenario == 2 and extra:
        summary["interarrival_ticks"] = describe(extra)
    summary["samples"] = samples
    return snapshot, manifest, rows, summary


def pair_runs(base, other):
    for key in ("elf", "source", "platform"):
        left = base.get(key, {}).get("sha256")
        right = other.get(key, {}).get("sha256")
        if left != right:
            raise ValueError(f"paired manifests differ in {key} identity")
    if base.get("seed") != other.get("seed"):
        raise ValueError("paired manifests differ in seed")
    if base.get("scenario") != other.get("scenario"):
        raise ValueError("paired manifests differ in scenario")


def compare_rows(left_rows, right_rows):
    left = {(r["trial"], r["condition"]): r for r in left_rows}
    right = {(r["trial"], r["condition"]): r for r in right_rows}
    out = []
    for key in sorted(set(left) & set(right)):
        # Compare the value columns actually present (ABI a..f or contract
        # names); label only, no semantics invented here.
        for field in (f for f in left[key] if f not in ("trial", "condition")):
            lval, rval = left[key][field], right[key][field]
            signed = rval - lval
            relative = None if lval == 0 else signed / lval
            out.append({"trial": key[0], "condition": key[1], "field": field,
                        "left": lval, "right": rval, "signed": signed,
                        "absolute": abs(signed), "relative": relative})
    return out


def write_outputs(out_dir, snapshot, rows, summary, comparisons=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    contract = RESULT_CONTRACT[snapshot.header["scenario"]]
    names = ("trial", "condition") + contract["fields"]
    with (out_dir / "rows.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)
    write_trace_csv(snapshot, out_dir / "trace.csv")
    with (out_dir / "ecdf.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "value", "cumulative_probability"))
        for metric, values in summary.get("samples", {}).items():
            for value, probability in ecdf(values):
                writer.writerow((metric, value, probability))
    if comparisons is not None:
        summary["paired_comparison"] = comparisons
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="run directory with snapshot.bin + manifest.json")
    parser.add_argument("--compare", help="second run directory (paired policy/environment)")
    parser.add_argument("--out", required=True)
    opts = parser.parse_args(argv)
    try:
        snapshot, manifest, rows, summary = analyze_run(opts.run)
        comparisons = None
        if opts.compare:
            other_snapshot, other_manifest, other_rows, _ = analyze_run(opts.compare)
            pair_runs(manifest, other_manifest)
            comparisons = {"identity": "ELF/source/platform/seed/scenario matched",
                           "left": str(opts.run), "right": str(opts.compare),
                           "rows": compare_rows(rows, other_rows)}
            summary["right_quality"] = other_snapshot.quality()
        write_outputs(opts.out, snapshot, rows, summary, comparisons)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"fidelity_analyze: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
