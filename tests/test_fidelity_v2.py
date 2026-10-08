"""Testes do pacote scripts/fidelity (sem hardware nem Renode).

    python3 -m unittest discover -s tests -p 'test_fidelity_v2.py'
"""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fidelity import abi, analysis, firmware, gate, oracles, runner  # noqa: E402


def snapshot(rows=(), trace=(), *, state=2, error=0, row_cap=4, trace_cap=2,
             scenario=1, variant=1, reserved=0):
    header = [0] * 32
    header[0:11] = [abi.MAGIC, 2, scenario, variant, state, error, 8000000, 7,
                    row_cap, len(rows), trace_cap]
    counts = [0, 0, 0]
    for e in trace:
        counts[e[0]] += 1
    header[11:14] = counts
    header[26] = reserved
    raw = bytearray(struct.pack("<32I", *header))
    body = bytearray(row_cap * 32)
    for i, r in enumerate(rows):
        struct.pack_into("<8I", body, 32 * i, *r)
    tr = bytearray(3 * trace_cap * 16)
    seen = [0, 0, 0]
    for w, ticks, ev, trial, arg in trace:
        struct.pack_into("<4I", tr, (w * trace_cap + seen[w]) * 16, ticks, ev, trial, arg)
        seen[w] += 1
    return bytes(raw + body + tr)


class AbiTest(unittest.TestCase):
    def test_roundtrip(self):
        raw = snapshot(rows=[(1, 2, 3, 4, 5, 6, 7, 8)], trace=[(1, 100, 2, 1, 9)])
        s = abi.decode(raw)
        self.assertTrue(s.ok)
        self.assertEqual(s.rows, [(1, 2, 3, 4, 5, 6, 7, 8)])
        self.assertEqual(s.trace[0].writer, 1)
        self.assertEqual(s.trace[0].ticks, 100)

    def test_size_mismatch(self):
        with self.assertRaises(abi.SnapshotError):
            abi.decode(snapshot()[:-16])

    def test_nonterminal_rejected(self):
        with self.assertRaises(abi.SnapshotError):
            abi.decode(snapshot(state=1))

    def test_state_error_consistency(self):
        with self.assertRaises(abi.SnapshotError):
            abi.decode(snapshot(state=2, error=0x40000000))
        s = abi.decode(snapshot(state=3, error=0x40000000))
        self.assertEqual(s.header["error_names"], ["TIMEOUT"])

    def test_unused_storage_must_be_zero(self):
        raw = bytearray(snapshot(rows=[(1,) * 8]))
        raw[128 + 32 + 4] = 1          # 2ª linha (não usada)
        with self.assertRaises(abi.SnapshotError):
            abi.decode(bytes(raw))

    def test_reserved_must_be_zero(self):
        with self.assertRaises(abi.SnapshotError):
            abi.decode(snapshot(reserved=1))

    def test_ticks_wrap(self):
        self.assertEqual(abi.ticks_delta(0xFFFFFFF0, 0x10), 0x20)


class OracleTest(unittest.TestCase):
    def test_s1a_simple_kernels(self):
        ctx = [0x20000000, 5, 3, 7, 0x10000000, 0xFFFFFFFF, 3, 0x08000100]
        self.assertEqual(oracles.s1a_signature(2, 1, ctx, 0), 5 + 16 * 3)
        self.assertEqual(oracles.s1a_signature(5, 1, ctx, 0), 0xFFFFFFFF + 0x55555555 & 0xFFFFFFFF)
        self.assertEqual(oracles.s1a_signature(11, 4, ctx, 0), (ctx[0] + 5 + 3 + 7) & 0xFFFFFFFF)
        self.assertEqual(oracles.s1a_signature(9, 1, ctx, 0x11), 0x08000111)

    def test_ror(self):
        self.assertEqual(oracles.ror(0x1, 1), 0x80000000)
        self.assertEqual(oracles.ror(0x12345678, 0), 0x12345678)
        self.assertEqual(oracles.ror(0x12345678, 32), 0x12345678)
        self.assertEqual(oracles.ror(0x12345678, 0x104), oracles.ror(0x12345678, 4))

    def test_s1b_signature_table(self):
        sig = oracles.s1b_signatures()
        self.assertEqual(len(sig), 9 * 7)
        self.assertTrue(all(sig[(t, 7)] == 0 for t in range(9)))

    def test_order_code_roundtrip(self):
        for seq in ([1, 2, 3, 4, 5, 6], [7, 8, 9, 10], [9, 10, 11, 7, 8]):
            self.assertEqual(oracles.decode_order(oracles.order_code(seq)), seq)

    def test_s4a_rules(self):
        self.assertEqual(oracles.s4a_expected(1), [1, 2, 3, 4, 5, 6])   # grupo maior aninha
        self.assertEqual(oracles.s4a_expected(2), [1, 2, 5, 6, 3, 4])   # sub não preempta
        self.assertEqual(oracles.s4a_expected(6), [9, 10, 7, 8])        # grupo vence nº
        self.assertEqual(oracles.s4a_expected(7), [9, 10, 7, 8])        # sub ordena pendentes
        self.assertEqual(oracles.s4a_expected(8), [7, 8, 9, 10])        # empate → menor nº


class AnalysisTest(unittest.TestCase):
    def test_s4b_class(self):
        code = oracles.order_code([3, 4, 1, 2])
        self.assertEqual(analysis.s4b_class(code), "late-arrival/arbitragem")
        self.assertEqual(analysis.s4b_class(code | (1 << 24)), "preempção")
        self.assertEqual(analysis.s4b_class(oracles.order_code([1, 2, 3, 4])), "sequencial")
        self.assertEqual(analysis.s4b_class(oracles.order_code([1, 2])), "H não entrou")

    def test_determinism(self):
        mk = lambda rows: analysis.Run(Path("."), {}, abi.decode(snapshot(rows=rows)))  # noqa: E731
        a, b = mk([(1,) * 8]), mk([(2,) * 8])
        self.assertTrue(analysis.determinism([a, a])["identical"])
        self.assertFalse(analysis.determinism([a, b])["identical"])

    def test_order_tags(self):
        self.assertEqual(analysis.order_tags(["rn-m100-q1us", "hw", "rn-m8-q1us"]),
                         ["hw", "rn-m8-q1us", "rn-m100-q1us"])


class RunnerTest(unittest.TestCase):
    def test_tags(self):
        self.assertEqual(runner.RenodeConfig().tag, "rn-m8-q1us")
        self.assertEqual(runner.RenodeConfig(mips=100).tag, "rn-m100-q1us")
        self.assertEqual(runner.RenodeConfig(quantum="0.000000125").tag, "rn-m8-q125ns")
        self.assertEqual(runner.RenodeConfig(uart_delay=False).tag, "rn-m8-q1us-nodelay")

    def test_resc_uart_only_for_loopback(self):
        cfg = runner.RenodeConfig()
        self.assertIn("CreateUARTHub", runner.renode_resc(firmware.get("s3a"), cfg, 3400))
        self.assertNotIn("CreateUARTHub", runner.renode_resc(firmware.get("s2a"), cfg, 3400))
        self.assertIn("PerformanceInMips 8\n", runner.renode_resc(firmware.get("s1a"), cfg, 3400))

    def test_dump_path_without_spaces(self):
        with self.assertRaises(runner.RunError):
            runner.capture_script(3333, Path("/tmp/a b/x.bin"))

    def test_registry_unique_ids(self):
        ids = {(f.scenario, f.variant) for f in firmware.FIRMWARES.values()}
        self.assertEqual(len(ids), len(firmware.FIRMWARES))


class GateParserTest(unittest.TestCase):
    TEXT = """
08000600 <k>:
 8000600:	b5f0      	push	{r4, r5, r6, r7, lr}
 8000602:	1892      	adds	r2, r2, r2
 8000604:	3801      	subs	r0, #1
 8000606:	d1fc      	bne.n	8000602 <k+0x2>
 8000608:	bdf0      	pop	{r4, r5, r6, r7, pc}
 800060a:	40013800 	.word	0x40013800
"""

    def test_insns_skip_data(self):
        ops = [op for _, op, _ in gate.insns(self.TEXT)]
        self.assertEqual(ops, ["push", "adds", "subs", "bne.n", "pop"])


if __name__ == "__main__":
    unittest.main()
