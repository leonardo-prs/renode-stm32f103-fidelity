#!/usr/bin/env python3
"""Synthetic ABI-v1 fixtures for fidelity_analyze; no hardware or Renode."""

import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fmt = load("fidelity_format")
load("fidelity_perfetto")
analyze = load("fidelity_analyze")

MAGIC = 0x46494431
BASE_HEADER = [MAGIC, 1, 1, 2, 0, 8_000_000, 0, 128, 128, 1,
               123, 0x83, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0] + [0] * 10


def snapshot_bytes(scenario=1, state=2, error=0, results=(), trace_counts=(0, 0, 0),
                   traces=((), (), ()), drops=(0, 0, 0), **header):
    words = list(BASE_HEADER)
    words[2] = scenario
    words[3] = state
    words[4] = error
    words[6] = len(results)
    words[16:19] = list(trace_counts)
    words[19:22] = list(drops)
    for key, value in header.items():
        words[int(key[1:])] = value
    body = bytearray(10368 - 128)
    for index, row in enumerate(results):
        struct.pack_into("<8I", body, index * 32, *row)
    for writer, entries in enumerate(traces):
        for sequence, entry in enumerate(entries):
            offset = 4096 + writer * 2048 + sequence * 16
            struct.pack_into("<4I", body, offset, *entry)
    return struct.pack("<32I", *words[:32]) + bytes(body)


def run_dir(parent, name, raw, manifest):
    path = Path(parent) / name
    path.mkdir()
    (path / "snapshot.bin").write_bytes(raw)
    (path / "manifest.json").write_text(json.dumps(manifest))
    return path


def base_manifest(scenario=1, seed=123):
    return {"scenario": f"s{scenario}", "seed": seed, "environment": "hw",
            "elf": {"sha256": "e"}, "source": {"sha256": "s"},
            "platform": {"sha256": "p"},
            "config": {"mips": 8, "mips_policy": "nominal", "quantum": "0.000001"}}


def entry(ticks, event, trial=0, arg=0):
    return (ticks, event, trial, arg)


class DecoderFixtures(unittest.TestCase):
    def test_valid_wrap_forward_and_backwards_rejected(self):
        boot = entry(0xFFFFFFF0, 1)
        wrapped = entry(16, 0x100, 1)  # forward across wrap
        backwards = entry(0xFFFFFF9C, 0x101, 1)  # 84 ticks behind BOOT
        good = snapshot_bytes(results=[(1, 2, 1, 1, 0, 0, 0, 0)],
                              trace_counts=(2, 0, 0), traces=([boot, wrapped], [], []))
        self.assertEqual(fmt.decode_snapshot(good).header["scenario"], 1)
        bad = snapshot_bytes(results=[(1, 2, 1, 1, 0, 0, 0, 0)],
                             trace_counts=(2, 0, 0), traces=([boot, backwards], [], []))
        with self.assertRaises(fmt.SnapshotError):
            fmt.decode_snapshot(bad)

    def test_half_span_rejected(self):
        entries = [entry(0, 1), entry(1 << 31, 0x100, 1)]
        raw = snapshot_bytes(trace_counts=(2, 0, 0), traces=(entries, [], []))
        with self.assertRaises(fmt.SnapshotError):
            fmt.decode_snapshot(raw)

    def test_bad_magic_version_scenario_size(self):
        for raw in (snapshot_bytes()[:-1], snapshot_bytes() + b"x",
                    snapshot_bytes(**{"w0": 0}), snapshot_bytes(**{"w1": 2}),
                    snapshot_bytes(scenario=5), snapshot_bytes(state=1)):
            with self.assertRaises(fmt.SnapshotError):
                fmt.decode_snapshot(raw)

    def test_equal_tick_tie_disclosed(self):
        entries = [entry(0, 1), entry(100, 0x100, 1), entry(100, 0x200, 1)]
        raw = snapshot_bytes(trace_counts=(2, 1, 0),
                             traces=([entries[0], entries[1]], [entries[2]], []))
        snapshot = fmt.decode_snapshot(raw)
        self.assertTrue(any("equal-tick" in w for w in snapshot.warnings))

    def test_drops_flag_incomplete(self):
        raw = snapshot_bytes(trace_counts=(1, 0, 0),
                             traces=([entry(0, 1)], [], []), drops=(3, 0, 0))
        snapshot = fmt.decode_snapshot(raw)
        self.assertEqual(snapshot.quality()["status"], "incomplete")


class AnalyzeRunTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "data/.collector-test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)

    def analyze(self, raw, manifest=None):
        run = run_dir(self.parent, f"run{len(list(self.parent.iterdir()))}", raw,
                      manifest or base_manifest())
        return analyze.analyze_run(run)

    def test_s1_brackets_and_checksums(self):
        rows = [(1, 1, 7, 7, 0, 0, 0, 0), (2, 7, 9, 9, 100, 0, 0, 0)]
        traces = ([entry(0, 1), entry(10, 0x100, 1), entry(20, 0x101, 1),
                   entry(30, 0x100, 2), entry(230, 0x101, 2)], [], [])
        raw = snapshot_bytes(results=rows, trace_counts=(5, 0, 0), traces=traces)
        _, _, _, summary = self.analyze(raw)
        ids = {f["id"]: f["status"] for f in summary["findings"]}
        self.assertEqual(ids["s1.brackets"], "observed")
        self.assertEqual(ids["s1.functional"], "observed")
        self.assertEqual(ids["s1.empty_bracket"], "observed")
        self.assertEqual(summary["bracket_ticks"]["2"], 200)

    def test_s1_checksum_mismatch_refuted(self):
        rows = [(1, 2, 7, 8, 1, 0, 0, 0)]
        raw = snapshot_bytes(results=rows,
                             trace_counts=(3, 0, 0),
                             traces=([entry(0, 1), entry(1, 0x100, 1), entry(2, 0x101, 1)], [], []))
        _, _, _, summary = self.analyze(raw)
        self.assertIn("refuted", [f["status"] for f in summary["findings"]
                                  if f["id"] == "s1.functional"])

    def test_s4_nested_positive_and_negative(self):
        rows = [(1, 1, 1, 1, 1, 0, 0, 0), (2, 2, 1, 0, 0, 0, 0, 0)]
        # Per-writer publication order must be tick-monotonic (decoder rule);
        # trial 1 chain is LENTER<REQUEST<HENTER<HEXIT<RESUME<LEXIT.
        main = [entry(0, 1), entry(20, 0x401, 1), entry(21, 0x401, 2),
                entry(36, 0x404, 1)]
        low = [entry(10, 0x400, 1), entry(11, 0x400, 2),
               entry(40, 0x405, 1), entry(50, 0x405, 2)]
        high = [entry(25, 0x402, 1), entry(35, 0x403, 1),
                entry(60, 0x402, 2), entry(70, 0x403, 2)]
        raw = snapshot_bytes(scenario=4, results=rows,
                             trace_counts=(4, 4, 4),
                             traces=(main, low, high))
        _, _, _, summary = self.analyze(raw, base_manifest(scenario=4))
        statuses = {f["id"]: f["status"] for f in summary["findings"]}
        self.assertEqual(statuses["s4.trial1.preempt"], "observed")
        self.assertEqual(statuses["s4.trial2.non_preempt"], "observed")

    def test_s4_negative_control_nesting_refuted(self):
        rows = [(1, 2, 1, 1, 0, 0, 0, 0)]
        main = [entry(0, 1), entry(20, 0x401, 1), entry(45, 0x404, 1)]
        low = [entry(10, 0x400, 1), entry(40, 0x405, 1)]
        high = [entry(25, 0x402, 1), entry(35, 0x403, 1)]
        raw = snapshot_bytes(scenario=4, results=rows,
                             trace_counts=(3, 2, 2), traces=(main, low, high))
        _, _, _, summary = self.analyze(raw, base_manifest(scenario=4))
        statuses = {f["id"]: f["status"] for f in summary["findings"]}
        self.assertEqual(statuses["s4.trial1.non_preempt"], "refuted")

    def test_s3_ore_gap_labeled_not_pass(self):
        rows = [(1, 3, 8, 8, 0, 0, 0, 0)]
        traces = ([entry(0, 1), entry(1, 0x300, 1)], [entry(2, 0x301, 1)], [])
        raw = snapshot_bytes(scenario=3, results=rows,
                             trace_counts=(2, 1, 0), traces=traces)
        _, _, _, summary = self.analyze(raw, base_manifest(scenario=3))
        gap = next(f for f in summary["findings"] if f["id"] == "s3.ore_model_gap")
        self.assertIn("model gap", gap["detail"])

    def test_state3_diagnostic_not_success(self):
        # ERROR captures still carry the mandatory MAIN[0] BOOT entry.
        raw = snapshot_bytes(state=3, error=9, trace_counts=(1, 0, 0),
                             traces=([entry(0, 1)], [], []))
        _, _, _, summary = self.analyze(raw)
        self.assertEqual(summary["quality"]["status"], "refuted")


class PairedTests(unittest.TestCase):
    def test_identity_mismatch_refused(self):
        left = base_manifest()
        right = base_manifest()
        right["elf"] = {"sha256": "different"}
        with self.assertRaises(ValueError):
            analyze.pair_runs(left, right)
        right = base_manifest()
        right["config"] = {"mips": 5, "mips_policy": "calibrated"}
        analyze.pair_runs(left, right)  # policy difference is the point, not identity

    def test_compare_rows_zero_guard(self):
        rows_a = [{"trial": 1, "condition": 2, "a": 0, "b": 1, "c": 0,
                   "d": 0, "e": 0, "f": 0}]
        rows_b = [{"trial": 1, "condition": 2, "a": 4, "b": 1, "c": 0,
                   "d": 0, "e": 0, "f": 0}]
        out = analyze.compare_rows(rows_a, rows_b)
        zero = next(r for r in out if r["field"] == "a")
        self.assertIsNone(zero["relative"])
        self.assertEqual(zero["signed"], 4)


if __name__ == "__main__":
    unittest.main()
