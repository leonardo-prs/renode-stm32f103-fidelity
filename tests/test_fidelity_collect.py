"""Pure unit tests: no tools, board, server, emulator or GDB are launched."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/fidelity_collect.py"
SPEC = importlib.util.spec_from_file_location("fidelity_collect", MODULE_PATH)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def snapshot(**changes):
    words = [collector.MAGIC, 1, 1, 2, 0, 8000000, 0, 128, 128, 1,
             123, 0x83, 0, 0, 1, 0] + [0] * 16
    for name, value in changes.items():
        index = int(name[4:]) if name.startswith("word") else collector.HEADER_NAMES.index(name)
        words[index] = value
    return struct.pack("<32I", *words) + bytes(collector.SIZE - 128)


GOOD_LOG = ("FIDELITY_SIZE=10368\nFIDELITY_INITIAL_MAGIC=0x0\n"
            "Hardware assisted breakpoint 1 at 0x08001000\n"
            "FIDELITY_PC=0x8001000 COMPLETE=0x8001001\n"
            "FIDELITY_TERMINAL=2 MAGIC=0x46494431\n")


class FakeProcess:
    def __init__(self, timeout=False, code=0):
        self.pid = 10001
        self.timeout = timeout
        self.code = code
        self.running = True
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self.running else self.code

    def wait(self, timeout=None):
        if self.timeout and not self.terminated:
            raise subprocess.TimeoutExpired("mock-owned-child", timeout)
        self.running = False
        return self.code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
        self.running = False


class DecoderTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(collector.validate_snapshot(snapshot(), "s1")["seed"], 123)

    def test_state_error_is_collectable_not_pass(self):
        self.assertEqual(collector.validate_snapshot(snapshot(state=3, error=5), "s1")["state"], 3)

    def test_bad_header_and_size(self):
        cases = [snapshot()[:-1], snapshot() + b"x", snapshot(magic=0),
                 snapshot(version=2), snapshot(scenario=2), snapshot(state=1),
                 snapshot(state=3), snapshot(error=1), snapshot(result_count=129),
                 snapshot(word16=129), snapshot(trace_capacity=127),
                 snapshot(result_capacity=127), snapshot(trace_enabled=0),
                 snapshot(core_hz=72000000), snapshot(word22=1)]
        for raw in cases:
            with self.subTest(raw=raw[:128]):
                with self.assertRaises(collector.SnapshotError):
                    collector.validate_snapshot(raw, "s1")

    def test_unused_storage(self):
        for offset in (128, 4224, 6272, 8320):
            raw = bytearray(snapshot())
            raw[offset] = 1
            with self.assertRaises(collector.SnapshotError):
                collector.validate_snapshot(raw, "s1")

    def test_drops_preserved_for_analysis(self):
        self.assertEqual(collector.validate_snapshot(snapshot(word19=100), "s1")["trace_drop"], [100, 0, 0])

    def test_unauthorized_halt_missing_breakpoint(self):
        header = collector.validate_snapshot(snapshot(), "s1")
        collector.validate_gdb_log(GOOD_LOG, header)
        for text in (GOOD_LOG.replace("PC=0x8001000", "PC=0x8001004"),
                     GOOD_LOG.replace("Hardware assisted breakpoint", "Breakpoint"),
                     GOOD_LOG.replace("TERMINAL=2", "TERMINAL=1"), ""):
            with self.assertRaises(collector.AcquisitionError):
                collector.validate_gdb_log(text, header)


class CLIAndCommandsTests(unittest.TestCase):
    def args(self, *extra):
        return collector.parse_args(["s3", "--environment", "renode", "--out", "data/final/new", *extra])

    def test_defaults_and_controls(self):
        args = self.args()
        self.assertEqual((args.port, args.mips, args.quantum, args.timeout), (3336, 8, "0.000001", 60))
        self.assertEqual(args.mips_policy, "nominal")
        text = collector.resc_text(self.args("--mips", "100", "--mips-policy", "default100-control",
                                             "--quantum", "0.000000125", "--uart-delay", "off"),
                                   Path('/root/fw.elf'), Path('/root/platform.repl'), Path('/root'))
        self.assertIn('PerformanceInMips 100', text)
        self.assertIn('SetGlobalQuantum "0.000000125"', text)
        self.assertIn('CreateUARTHub "uartLoopback" true', text)
        self.assertIn('AutoUpdateDelay false', text)
        self.assertIn('DelayMultiplier 1', text)
        # Forma validada: @path relativo SEM aspas (quoted falha em silêncio
        # no Renode 1.17 — o script não executa e o GDB server não sobe).
        self.assertIn('@fw.elf', text)
        self.assertIn('@platform.repl', text)
        self.assertNotIn('"fw.elf"', text)
        self.assertNotIn('\nstart\n', text)
        # Paths com espaço não são representáveis sem aspas: recusa explícita.
        with self.assertRaises(collector.AcquisitionError):
            collector.resc_text(self.args(), Path('/a b/fw.elf'),
                                Path('/a b/platform.repl'), Path('/'))

    def test_mips_policy_consistency(self):
        # nominal = datasheet hypothesis only; default100 = Renode default control;
        # calibrated = one global derived value, never 8/100, never per-scenario fitting.
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--mips", "100")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--mips", "8", "--mips-policy", "default100-control")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--mips", "8", "--mips-policy", "calibrated")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--mips", "100", "--mips-policy", "calibrated")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--mips", "0")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--mips", "201")
        calibrated = self.args("--mips", "5", "--mips-policy", "calibrated")
        self.assertEqual((calibrated.mips, calibrated.mips_policy), (5, "calibrated"))

    def test_bad_arguments(self):
        for extra in (("--port", "3333"), ("--port", "65536"),
                      ("--timeout", "nan"), ("--timeout", "inf"),
                      ("--timeout", "0"), ("--timeout", "61"), ("--reuse-openocd",)):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args(*extra)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            collector.parse_args(["s1", "--environment", "hw", "--out", "data/final/x", "--port", "3334"])

    def test_single_continue_exact_entry_and_no_renode_load(self):
        text = collector.gdb_text(self.args(), Path('/ab/snapshot.pending.bin'))
        self.assertEqual(text.count('\ncontinue\n'), 1)
        self.assertIn('hbreak *fidelity_complete\ncontinue', text)
        self.assertNotIn('\nload\n', text)
        self.assertNotIn('monitor reset halt', text)
        self.assertNotIn('step', text)
        hw = collector.parse_args(["s1", "--environment", "hw", "--out", "data/final/x"])
        self.assertIn('monitor reset halt\nload\nmonitor reset halt', collector.gdb_text(hw, Path('dump')))

    def test_dump_path_with_space_refused(self):
        # GDB 16.3.90 fopen() mantém as aspas no nome do dump (ENOENT):
        # paths com espaço não são representáveis — recusa explícita.
        with self.assertRaises(collector.AcquisitionError):
            collector.gdb_text(self.args(), Path('/a b/snapshot.pending.bin'))

    def test_path_control_characters(self):
        with self.assertRaises(collector.AcquisitionError):
            collector.quoted("bad\npath")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        # Project-local test scratch, never an unapproved generic /tmp directory.
        scratch = MODULE_PATH.parents[1] / "data/.collector-test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("renode", "src", "build/s1"):
            (self.root / folder).mkdir(parents=True)
        (self.root / "renode/stm32f103_hsi8.repl").write_text("fixture platform")
        (self.root / "build/s1/firmware.elf").write_bytes(b"fixture ELF")
        (self.root / "src/s1.c").write_text("fixture source")
        self.out = self.root / "data/final/run"
        self.children = []

    def args(self, environment="renode", reuse=False):
        argv = ["s1", "--environment", environment, "--out", str(self.out)]
        if reuse:
            argv.append("--reuse-openocd")
        return collector.parse_args(argv)

    def run_mock(self, args=None, raw=None, log=GOOD_LOG, timeout=False, code=0,
                 occupied=False, readiness_error=False):
        raw = snapshot() if raw is None else raw

        def spawn(argv, **kwargs):
            process = FakeProcess(timeout=timeout if argv[0] == "arm-none-eabi-gdb" else False,
                                  code=code if argv[0] == "arm-none-eabi-gdb" else 0)
            self.children.append(process)
            if argv[0] == "arm-none-eabi-gdb":
                kwargs["stdout"].write(log.encode())
                kwargs["stdout"].flush()
                (self.out / "snapshot.pending.bin").write_bytes(raw)
            return process

        with mock.patch.object(collector, "tool_versions", return_value={}), \
                mock.patch.object(collector, "listening", return_value=occupied), \
                mock.patch.object(collector, "free_port", return_value=45678), \
                mock.patch.object(collector, "openocd_identity", return_value="OpenOCD fixture"), \
                mock.patch.object(collector, "wait_ready", side_effect=collector.AcquisitionError("readiness failed") if readiness_error else None), \
                mock.patch.object(collector.subprocess, "Popen", side_effect=spawn) as popen:
            result = collector.collect(args or self.args(), self.root)
        return result, json.loads((self.out / "manifest.json").read_text()), popen

    def test_complete_owned_server_cleaned(self):
        result, manifest, popen = self.run_mock()
        self.assertEqual(result, 0)
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["functional_status"], "unknown")
        self.assertTrue(manifest["analysis_required"])
        self.assertTrue(self.children[0].terminated)
        self.assertFalse(self.children[1].terminated)
        self.assertEqual((self.out / "snapshot.bin").read_bytes(), snapshot())
        self.assertFalse((self.out / "snapshot.bin").stat().st_mode & 0o222)
        self.assertEqual(popen.call_count, 2)
        self.assertNotIn('shell', popen.call_args.kwargs)
        self.assertEqual(manifest["snapshot"]["sha256"], collector.digest(self.out / "snapshot.bin"))

    def test_nonexisting_output_required_no_stale_overwrite(self):
        self.out.mkdir(parents=True)
        stale = self.out / "snapshot.pending.bin"
        stale.write_bytes(b"old dump")
        with mock.patch.object(collector.subprocess, "Popen") as popen:
            with self.assertRaises(FileExistsError):
                collector.collect(self.args(), self.root)
            popen.assert_not_called()
        self.assertEqual(stale.read_bytes(), b"old dump")

    def test_wrong_size_semantic_fail_not_crash(self):
        result, manifest, _ = self.run_mock(raw=b"stale short dump")
        self.assertEqual(result, 3)
        self.assertEqual(manifest["error"]["kind"], "SnapshotError")
        self.assertEqual(manifest["status"], "error")
        self.assertFalse((self.out / "snapshot.bin").exists())
        self.assertFalse((self.out / "snapshot.pending.bin").exists())

    def test_timeout_owned_children_only_and_error_manifest(self):
        result, manifest, _ = self.run_mock(timeout=True)
        self.assertEqual(result, 1)
        self.assertTrue(manifest["timeout"])
        self.assertTrue(all(child.terminated for child in self.children))
        self.assertFalse((self.out / "snapshot.bin").exists())

    def test_reused_daemon_not_killed_on_timeout(self):
        result, manifest, popen = self.run_mock(args=self.args("hw", True), occupied=True, timeout=True)
        self.assertEqual(result, 1)
        self.assertEqual(popen.call_count, 1)  # GDB only, no daemon ownership
        self.assertEqual(manifest["server"]["ownership"], "reused, never terminated")
        self.assertTrue(self.children[0].terminated)

    def test_reuse_requires_existing_daemon(self):
        result, manifest, popen = self.run_mock(args=self.args("hw", True))
        self.assertEqual(result, 1)
        self.assertIn("requires an existing", manifest["error"]["message"])
        popen.assert_not_called()

    def test_existing_daemon_requires_explicit_reuse(self):
        result, manifest, popen = self.run_mock(args=self.args("hw"), occupied=True)
        self.assertEqual(result, 1)
        self.assertIn("explicit", manifest["error"]["message"])
        popen.assert_not_called()

    def test_owned_startup_failure_cleanup(self):
        result, manifest, _ = self.run_mock(readiness_error=True)
        self.assertEqual(result, 1)
        self.assertEqual(manifest["status"], "error")
        self.assertTrue(self.children[0].terminated)

    def test_gdb_nonzero_and_missing_breakpoint(self):
        result, manifest, _ = self.run_mock(code=1)
        self.assertEqual(result, 1)
        self.assertIn("GDB failed", manifest["error"]["message"])

    def test_state3_complete_not_functional_pass(self):
        result, manifest, _ = self.run_mock(raw=snapshot(state=3, error=9),
                                          log=GOOD_LOG.replace("TERMINAL=2", "TERMINAL=3"))
        self.assertEqual(result, 0)
        self.assertTrue(manifest["acquisition_complete"])
        self.assertEqual(manifest["functional_status"], "unknown")
        self.assertEqual(manifest["snapshot"]["header"]["error"], 9)

    def test_lock_conflict_fails_without_starting_process(self):
        lock = self.root / "data/.locks/port-3333.lock"
        with collector.exclusive_lock(lock):
            result, manifest, popen = self.run_mock(args=self.args("hw", True), occupied=True)
        self.assertEqual(result, 1)
        self.assertIn("locked", manifest["error"]["message"])
        popen.assert_not_called()

    def test_source_hash_excludes_vendor_and_generated_build(self):
        before = collector.source_metadata(self.root)["sha256"]
        (self.root / "vendor").mkdir()
        (self.root / "vendor/giant.c").write_text("not included")
        (self.root / "build/log.txt").write_text("not included")
        self.assertEqual(before, collector.source_metadata(self.root)["sha256"])
        (self.root / "src/s1.c").write_text("changed")
        self.assertNotEqual(before, collector.source_metadata(self.root)["sha256"])


class OwnershipHelperTests(unittest.TestCase):
    def test_kill_escalates_only_given_child(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("owned", 3), 0]
        collector.stop_owned(process)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_completed_child_is_not_signalled(self):
        process = mock.Mock()
        process.poll.return_value = 0
        collector.stop_owned(process)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_unknown_server_handshake_rejected(self):
        sock = mock.MagicMock()
        body = b"OK"
        packet = b"$" + body + b"#" + f"{sum(body) % 256:02x}".encode()
        sock.__enter__.return_value = sock
        sock.recv.return_value = packet
        with mock.patch.object(collector.socket, "create_connection", return_value=sock):
            with self.assertRaises(collector.AcquisitionError):
                collector.openocd_identity(3333)


if __name__ == "__main__":
    unittest.main()
