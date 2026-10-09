"""Testes de DESENVOLVIMENTO da infraestrutura (removidos da árvore final;
resultados registrados no README). Rodar: python3 -m unittest -v tests/test_fidelity.py"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fidelity import abi, c1, c2, c3, c4, campaign  # noqa: E402
from fidelity.model import RunEval  # noqa: E402

DEV = ROOT / "data" / "fidelity" / "pilot-clone2" / "renode-nominal"   # dados com o layout atual


def build(cases=(), events=None, case_cap=4, word_cap=16, ring=8, **hdr):
    """Snapshot FID3 sintético. events: {writer: [(ticks, ticket, ev, case, arg)]} na ordem de escrita."""
    events = events or {}
    words, case_rows = [], []
    for cid, status, ws in cases:
        case_rows.append((cid, status, len(words), len(ws)))
        words += ws
    _, words_off, ring_off, total = abi.layout(case_cap, word_cap, 4, ring)
    h = {k: 0 for k in abi.HEADER_FIELDS}
    h.update(magic=abi.MAGIC, abi_version=3, snapshot_bytes=total, firmware_id=0x0301, state=2,
             case_planned=len(cases), case_capacity=case_cap, case_count=len(cases),
             word_capacity=word_cap, word_count=len(words), ring_capacity=ring, writer_count=4,
             dwt_start=0xFFF00000, core_hz=8_000_000)
    n_events = 0
    for w, lst in events.items():
        h[f"ring_head{w}"] = len(lst)
        n_events += len(lst)
    h["ticket_next"] = n_events
    h.update(hdr)
    raw = bytearray(total)
    struct.pack_into(f"<{abi.HEADER_WORDS}I", raw, 0, *(h[k] for k in abi.HEADER_FIELDS))
    for i, row in enumerate(case_rows):
        struct.pack_into("<4I", raw, abi.HEADER_BYTES + 16 * i, *row)
    for i, v in enumerate(words):
        struct.pack_into("<I", raw, words_off + 4 * i, v)
    for w, lst in events.items():
        for idx, (ticks, ticket, ev, case, arg) in enumerate(lst):
            struct.pack_into("<IIHHI", raw, ring_off + 16 * (w * ring + (idx % ring)),
                             ticks, ticket, ev, case, arg)
    return bytes(raw)


class Decoder(unittest.TestCase):
    def test_valid(self):
        raw = build([(1, 1, [7, 8]), (2, 1, [9])], {0: [(0xFFF00010, 0, 3, 1, 1), (0xFFF00020, 2, 4, 1, 1)],
                                                     1: [(0xFFF00015, 1, 0x300, 1, 0)]})
        s = abi.decode(raw)
        self.assertEqual([c.words for c in s.cases], [(7, 8), (9,)])
        self.assertEqual([e.ticket for e in s.all_events()], [0, 1, 2])

    def test_rejects(self):
        good = build([(1, 1, [1])])
        bad = {
            "magic": lambda r: struct.pack_into("<I", r, 0, 0x12345678),
            "versão": lambda r: struct.pack_into("<I", r, 4, 2),
            "tamanho": lambda r: struct.pack_into("<I", r, 8, len(r) + 4),
            "estado": lambda r: struct.pack_into("<I", r, 16, 9),
            "casos > capacidade": lambda r: struct.pack_into("<I", r, 36, 99),
            "palavras fora de ordem": lambda r: struct.pack_into("<I", r, abi.HEADER_BYTES + 8, 5),
            "status de caso": lambda r: struct.pack_into("<I", r, abi.HEADER_BYTES + 4, 7),
        }
        for name, corrupt in bad.items():
            raw = bytearray(good)
            corrupt(raw)
            with self.subTest(name), self.assertRaises(abi.SnapshotError):
                abi.decode(bytes(raw))
        with self.assertRaises(abi.SnapshotError):
            abi.decode(good[:-16])                       # truncado
        with self.assertRaises(abi.SnapshotError):
            abi.decode(good[:100])

    def test_ticket_corruption(self):
        dup = build([], {0: [(1, 0, 1, 0, 0)], 1: [(2, 0, 0x300, 0, 0)]}, ticket_next=2)
        with self.assertRaises(abi.SnapshotError):
            abi.decode(dup)
        dec = build([], {0: [(1, 1, 1, 0, 0), (2, 0, 1, 0, 0)]})
        with self.assertRaises(abi.SnapshotError):
            abi.decode(dec)
        missing = build([], {0: [(1, 0, 1, 0, 0)]}, ticket_next=2)   # ticket emitido sem registro
        with self.assertRaises(abi.SnapshotError):
            abi.decode(missing)

    def test_ring_wrap_detected(self):
        evs = [(0xFFF00000 + 10 * i, i, 0x300, 1, i) for i in range(11)]
        s = abi.decode(build([], {1: evs}, ring=8))
        self.assertEqual(s.lost, [0, 3, 0, 0])
        self.assertEqual([e.arg for e in s.events[1]], list(range(3, 11)))   # mais novos preservados
        with self.assertRaises(abi.SnapshotError):
            abi.timeline(s)

    def test_rollover_and_repeated_events(self):
        # 3 ocorrências do MESMO evento atravessando 2^32.
        evs = {0: [(0xFFFFFFF0, 0, 0x300, 1, 0), (0x00000010, 1, 0x300, 1, 0), (0x00000030, 2, 0x300, 1, 0)]}
        s = abi.decode(build([], evs, dwt_start=0xFFFFFF00))
        t = abi.timeline(s)
        self.assertEqual([t[(0, i)] for i in range(3)], [0xF0, 0x110, 0x130])
        self.assertEqual(len(s.events[0]), 3)

    def test_backwards_time_rejected(self):
        evs = {0: [(0x100, 0, 1, 0, 0), (0x50, 1, 1, 0, 0)]}
        with self.assertRaises(abi.SnapshotError):
            abi.timeline(abi.decode(build([], evs, dwt_start=0)))

    def test_run_checks(self):
        s = abi.decode(build([(1, 1, [1])], run_nonce=5, state=3, error=1 << 3, fault_pc=0x08000100))
        problems = abi.run_checks(s, 0x0301, 6, [1, 2])
        joined = " ".join(problems)
        for word in ("nonce", "FAILED", "planeja", "casos diferentes", "falha no PC"):
            self.assertIn(word, joined)
        ok = abi.decode(build([(1, 1, [1])], run_nonce=6))
        self.assertEqual(abi.run_checks(ok, 0x0301, 6, [1]), [])


@unittest.skipUnless((DEV / "c4").exists(), "requer o piloto pilot-clone2")
class Oracles(unittest.TestCase):
    def snap(self, fw):
        return abi.decode((DEV / fw / "run-001" / "snapshot.bin").read_bytes())

    def test_c1_detects_wrong_output_and_input(self):
        s = self.snap("c1-functional")
        self.assertTrue(all(r.ok for r in c1.check_functional(s)))
        case = s.case(5)                                   # u32_divrem
        w = list(case.words)
        w[2] ^= 1                                          # quociente errado
        s.cases[s.cases.index(case)] = abi.Case(5, "OK", tuple(w))
        bad = [r for r in c1.check_functional(s) if not r.ok]
        self.assertEqual([r.name for r in bad], ["u32_divrem"])
        w[0] ^= 1                                          # entrada fora do plano
        s.cases[4] = abi.Case(5, "OK", tuple(w))
        self.assertFalse([r for r in c1.check_functional(s) if r.name == "u32_divrem"][0].inputs_ok)

    def test_c1_sram_neighbor_corruption(self):
        s = self.snap("c1-functional")
        idx = next(i for i, c in enumerate(s.cases) if c.case_id == 19)   # sram_widths
        w = list(s.cases[idx].words)
        w[0] ^= 0xFF000000                                 # byte vizinho alterado
        s.cases[idx] = abi.Case(19, "OK", tuple(w))
        self.assertFalse([r for r in c1.check_functional(s) if r.name == "sram_widths"][0].ok)

    def test_c3_rejects_reduced_repend_sequence(self):
        s = self.snap("c3")
        ev = c3.evaluate(s)
        self.assertTrue(all(c.ok for c in ev.checks))
        # remove a 2ª entrada/saída de A no caso 0x41 (sequência reduzida)
        a = s.events[1]
        drop = {e.index for e in a if e.case_id == 0x41 and e.arg & 0xFF == 1}
        s.events[1] = [e for e in a if e.index not in drop]
        s.lost = [0, 0, 0, 0]
        ev2 = c3.evaluate(s)
        bad = {c.case for c in ev2.checks if not c.ok}
        self.assertIn("c3/41", bad)

    def test_c2_and_c4_shapes(self):
        for mod, fw in ((c2, "c2"), (c4, "c4")):
            ev = mod.evaluate(self.snap(fw))
            self.assertIsInstance(ev, RunEval)
            self.assertFalse(ev.problems)
            self.assertTrue(ev.metrics)

    def test_c4_parity_word(self):
        self.assertEqual(c4.parity_word(0x05, c4.CR1_PCE), 0x05)            # 2 uns: par → 0
        self.assertEqual(c4.parity_word(0x07, c4.CR1_PCE), 0x87)            # 3 uns: par → 1
        self.assertEqual(c4.parity_word(0x07, c4.CR1_PCE | c4.CR1_PS), 0x07)
        self.assertEqual(c4.parity_word(0x101, c4.CR1_M), 0x101)


class Campaign(unittest.TestCase):
    def test_quantum_for(self):
        self.assertEqual(campaign.quantum_for(8), "0.000000125")
        self.assertEqual(campaign.quantum_for(7), "0.000001000")
        self.assertEqual(campaign.quantum_for(6), "0.000000500")
        self.assertEqual(campaign.quantum_for(5), "0.000000200")

    def test_choose_mips(self):
        hw = {ld: 1000.0 for ld in campaign.CALIBRATION_RULE["training_loads"]}
        rn = {ld: 700.0 for ld in hw}                     # Renode a 8 MIPS 30% mais rápido
        self.assertEqual(campaign.choose_mips(hw, rn)["chosen_mips"], 6)   # 700·8/6 = 933

    def test_lock_and_plan_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            lock = Path(d) / "x.lock"
            with campaign.Lock(lock, "teste"):
                with self.assertRaises(campaign.CampaignError):
                    with campaign.Lock(lock, "teste"):
                        pass
            old = campaign.DATA
            campaign.DATA = Path(d)
            try:
                paths = campaign.Paths("p")
                plan = {"schema": 1, "board": "b", "repetitions": 3, "environments": ["hw"],
                        "renode_nominal": {}, "mode": "final", "calibration": {"rule": {}},
                        "firmwares": {"c3": {"elf_sha256": "a", "planned_cases": [1]}}}
                campaign.freeze_plan(paths, plan, resume=False)
                with self.assertRaises(campaign.CampaignError):
                    campaign.freeze_plan(paths, plan, resume=False)          # já existe
                self.assertEqual(campaign.freeze_plan(paths, plan, resume=True)["board"], "b")
                other = json.loads(json.dumps(plan))
                other["firmwares"]["c3"]["elf_sha256"] = "b"
                with self.assertRaises(campaign.CampaignError):
                    campaign.freeze_plan(paths, other, resume=True)          # ELF mudou
                other = json.loads(json.dumps(plan))
                other["board"] = "outra"
                with self.assertRaises(campaign.CampaignError):
                    campaign.freeze_plan(paths, other, resume=True)          # exemplar mudou
            finally:
                campaign.DATA = old

    def test_max_attempts_bounded(self):
        self.assertEqual(campaign.max_attempts(50), 60)
        self.assertEqual(campaign.max_attempts(10), 13)


class Infrastructure(unittest.TestCase):
    """Falhas de infraestrutura viram TargetError claro e não deixam filhos vivos."""

    def test_busy_port_is_clear_error(self):
        import socket
        from fidelity import targets
        if targets.port_in_use(targets.HW_GDB_PORT):
            self.skipTest(":3333 já em uso (probe ocupado por outra coleta)")
        srv = socket.socket()
        srv.bind(("127.0.0.1", targets.HW_GDB_PORT))
        srv.listen()
        try:
            with tempfile.TemporaryDirectory() as d, self.assertRaises(targets.TargetError) as cm:
                with targets.Bench(Path(d)):
                    pass
            self.assertIn("já está em uso", str(cm.exception))
        finally:
            srv.close()

    def test_openocd_failure_is_clear_error(self):
        from unittest import mock
        from fidelity import targets
        if targets.port_in_use(targets.HW_GDB_PORT):
            self.skipTest(":3333 já em uso")
        real = targets.subprocess.Popen

        def bogus(argv, *a, **k):
            argv = ["interface/nao-existe.cfg" if x == "interface/stlink.cfg" else x for x in argv]
            return real(argv, *a, **k)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(targets.subprocess, "Popen", bogus):
            with self.assertRaises(targets.TargetError):
                with targets.Bench(Path(d)):
                    pass

    def test_renode_timeout_kills_child(self):
        import shutil
        import subprocess
        from fidelity import targets
        elf = ROOT / "build" / "c3" / "firmware.elf"
        if not shutil.which("renode") or not elf.exists():
            self.skipTest("renode/ELF ausentes")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(targets.TargetError):
                targets.run_renode(elf, Path(d), timeout_s=0.5, port_base=3500)
            out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
            self.assertNotIn("$gdb_port=35", out)


class CampaignRetry(unittest.TestCase):
    def test_timeouts_are_recorded_bounded_and_incomplete(self):
        """Run que nunca chega a fid_complete: tentativa guardada como falha de
        infraestrutura, tentativas limitadas, campanha termina com código 3."""
        import argparse
        import dataclasses
        import shutil
        from unittest import mock
        from fidelity import firmwares
        if not shutil.which("renode") or not (ROOT / "build" / "c3" / "firmware.elf").exists():
            self.skipTest("renode/ELF ausentes")
        slow = dataclasses.replace(firmwares.FIRMWARES["c3"], timeout_s=0.3)
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(firmwares.FIRMWARES, {"c3": slow}), \
                mock.patch.dict(campaign.FIRMWARES, {"c3": slow}), \
                mock.patch.object(campaign, "DATA", Path(d)):
            args = argparse.Namespace(name="retry", board="nenhuma", board_note="", reps=2, pilot=True,
                                      firmwares=["c3"], envs=["renode"], resume=False,
                                      calibration=False, instr=False, jobs=2)
            code = campaign.run_campaign(args)
            self.assertEqual(code, campaign.EXIT_INCOMPLETE)
            recs = [json.loads(p.read_text()) for p in (Path(d) / "retry" / "renode-nominal" / "c3").glob("run-*/run.json")]
            self.assertEqual(len(recs), campaign.max_attempts(2))
            self.assertTrue(all(r["status"] == "infra_error" for r in recs))
            self.assertTrue(all("GDB excedeu" in r["problems"][0] for r in recs))


if __name__ == "__main__":
    unittest.main()
