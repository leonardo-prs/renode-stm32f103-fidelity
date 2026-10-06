#!/usr/bin/env python3
"""Bounded, post-freeze acquisition; never a functional or temporal PASS oracle.

Only this invocation's children may be terminated. Existing HW servers require
explicit consent and a non-mutating OpenOCD version handshake. Runtime behavior
(Renode halt/reset and hardware breakpoint support) still needs phase-3 testing.
"""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
SIZE = 10368
MAGIC = 0x46494431
HEADER_NAMES = (
    "magic version scenario state error core_hz result_count trace_capacity "
    "result_capacity trace_enabled seed rcc_cr rcc_cfgr flash_acr dwt_ctrl prigroup"
).split()


class AcquisitionError(Exception):
    pass


class SnapshotError(AcquisitionError):
    pass


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_manifest(out, manifest):
    temporary = out / "manifest.json.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(out / "manifest.json")


def validate_snapshot(raw, scenario):
    if len(raw) != SIZE:
        raise SnapshotError(f"snapshot size {len(raw)} != {SIZE}")
    words = struct.unpack_from("<32I", raw)
    header = dict(zip(HEADER_NAMES, words[:16]))
    header.update(trace_count=list(words[16:19]), trace_drop=list(words[19:22]),
                  reserved=list(words[22:32]))
    if words[0:3] != (MAGIC, 1, int(scenario[1:])):
        raise SnapshotError("snapshot magic/version/scenario mismatch")
    if header["state"] not in (2, 3):
        raise SnapshotError("snapshot is not frozen terminal state")
    if (header["state"] == 2 and header["error"] != 0) or (
            header["state"] == 3 and header["error"] == 0):
        raise SnapshotError("inconsistent terminal state/error")
    if header["core_hz"] != 8000000:
        raise SnapshotError("unexpected nominal core clock")
    if words[7:10] != (128, 128, 1):
        raise SnapshotError("ABI capacity/trace_enabled mismatch")
    if words[6] > 128 or any(value > 128 for value in words[16:19]):
        raise SnapshotError("snapshot count exceeds capacity")
    if any(words[22:32]):
        raise SnapshotError("reserved header fields are not zero")
    # Unused storage must retain fidelity_init's zeroed ABI representation.
    if any(raw[128 + words[6] * 32:4224]):
        raise SnapshotError("nonzero unused result storage")
    for writer, count in enumerate(words[16:19]):
        start = 4224 + writer * 2048
        if any(raw[start + count * 16:start + 2048]):
            raise SnapshotError("nonzero unused trace storage")
    return header


@contextlib.contextmanager
def exclusive_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AcquisitionError(f"resource locked: {path.name}") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def openocd_identity(port):
    """RSP qRcmd(version): no reset, halt, load or continue during readiness."""
    command = b"qRcmd," + b"version".hex().encode("ascii")
    packet = b"$" + command + b"#" + f"{sum(command) % 256:02x}".encode()
    output = bytearray()
    deadline = time.monotonic() + 3
    with socket.create_connection(("127.0.0.1", port), timeout=1) as sock:
        sock.settimeout(1)
        sock.sendall(packet)
        buffer = b""
        while time.monotonic() < deadline:
            received = sock.recv(4096)
            if not received:
                break
            buffer += received
            while b"$" in buffer and b"#" in buffer[buffer.index(b"$"):]:
                start = buffer.index(b"$")
                end = buffer.index(b"#", start)
                if len(buffer) < end + 3:
                    break
                body = buffer[start + 1:end]
                checksum = buffer[end + 1:end + 3]
                buffer = buffer[end + 3:]
                if checksum.lower() != f"{sum(body) % 256:02x}".encode():
                    raise AcquisitionError("invalid server RSP checksum")
                sock.sendall(b"+")
                if body == b"OK":
                    identity = output.decode("utf-8", errors="replace")
                    if not re.search(r"Open(?:OCD| On-Chip Debugger)", identity, re.I):
                        raise AcquisitionError("3333 is not identified as OpenOCD")
                    return identity.strip()
                if body.startswith(b"O"):
                    output.extend(bytes.fromhex(body[1:].decode("ascii")))
                else:
                    raise AcquisitionError("server refused OpenOCD identity query")
    raise AcquisitionError("OpenOCD identity handshake timed out")


def stop_owned(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)


def wait_ready(port, child, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise AcquisitionError("owned server exited before readiness")
        if listening(port):
            return
        time.sleep(0.1)
    raise AcquisitionError("owned server readiness timed out")


def quoted(path):
    text = str(path)
    if any(char in text for char in '\n\r\x00'):
        raise AcquisitionError("control character in path")
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def resc_path(path, root):
    """@-paths em .resc/-e resolvem-se contra o CWD do Renode (root) e a
    forma quoted falha em silêncio no Renode 1.17 (script não executa, GDB
    server não sobe). Usa path relativo SEM aspas (forma validada);
    recusa paths que exigiriam quoting."""
    try:
        text = str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        raise AcquisitionError(f"path fora do root do projeto: {path}")
    if any(char in text for char in '\n\r\x00 "\''):
        raise AcquisitionError("path não representável sem aspas em resc")
    return text


def resc_text(args, elf, repl, root):
    text = (f'mach create "{args.scenario}_fidelity"\nusing sysbus\n'
            f'machine LoadPlatformDescription @{resc_path(repl, root)}\nlogLevel 1\n'
            f'emulation SetGlobalQuantum "{args.quantum}"\n'
            f'sysbus.cpu PerformanceInMips {args.mips}\n'
            f'sysbus LoadELF @{resc_path(elf, root)}\n')
    if args.scenario == "s3":
        text += ('emulation CreateUARTHub "uartLoopback" true\n'
                 'connector Connect sysbus.usart1 uartLoopback\n'
                 f'sysbus.usart1 AutoUpdateDelay {str(args.uart_delay == "on").lower()}\n'
                 'sysbus.usart1 DelayMultiplier 1\n')
    # StartGdbServer default autostart controls emulation on GDB continue;
    # intentionally no pre-GDB start which could execute before the breakpoint.
    return text + f'machine StartGdbServer {args.port}\n'


def gdb_text(args, pending):
    # OpenOCD's monitor reset halt is NOT a portable Renode monitor command.
    # Renode starts a fresh, unstarted machine with LoadELF's entry point.
    # GDB 16.3.90 fopen()s the dump filename INCLUDING any quotes (ENOENT);
    # paths with spaces/quotes cannot be dumped and are refused up front.
    pending_text = str(pending)
    if any(ch in pending_text for ch in '\n\r\x00 "\''):
        raise AcquisitionError("dump path não representável sem aspas no GDB")
    reset = "monitor reset halt\nload\nmonitor reset halt\n" if args.environment == "hw" else ""
    return ("set pagination off\nset confirm off\nset breakpoint pending off\n"
            "set remotetimeout 5\nset tcp connect-timeout 5\n"
            f"target remote 127.0.0.1:{args.port}\n" + reset +
            "if sizeof(fidelity_snapshot) != 10368\n"
            "  echo FIDELITY_BAD_SIZE\\n\n  quit 21\nend\n"
            "printf \"FIDELITY_SIZE=%u\\n\", (unsigned)sizeof(fidelity_snapshot)\n"
            "if (unsigned long)&fidelity_snapshot < 0x20000000 || (unsigned long)&fidelity_snapshot + sizeof(fidelity_snapshot) > 0x20005000\n"
            "  echo FIDELITY_BAD_ADDRESS\\n\n  quit 23\nend\n"
            "printf \"FIDELITY_INITIAL_MAGIC=0x%x\\n\", fidelity_snapshot.header.magic\n"
            "hbreak *fidelity_complete\ncontinue\n"
            "printf \"FIDELITY_PC=0x%lx COMPLETE=0x%lx\\n\", (unsigned long)$pc, (unsigned long)&fidelity_complete\n"
            "if ((unsigned long)$pc & ~1) != ((unsigned long)&fidelity_complete & ~1)\n"
            "  echo FIDELITY_UNAUTHORIZED_HALT\\n\n  quit 22\nend\n"
            "printf \"FIDELITY_TERMINAL=%u MAGIC=0x%x\\n\", fidelity_snapshot.header.state, fidelity_snapshot.header.magic\n"
            f"dump binary memory {pending_text} &fidelity_snapshot ((char*)&fidelity_snapshot)+sizeof(fidelity_snapshot)\n"
            "detach\nquit 0\n")


def validate_gdb_log(text, header):
    pc = re.search(r"FIDELITY_PC=0x([0-9a-fA-F]+) COMPLETE=0x([0-9a-fA-F]+)", text)
    terminal = re.search(r"FIDELITY_TERMINAL=(\d+) MAGIC=0x([0-9a-fA-F]+)", text)
    if ("FIDELITY_SIZE=10368" not in text or
            not re.search(r"Hardware assisted breakpoint", text, re.I) or not pc or
            (int(pc[1], 16) & ~1) != (int(pc[2], 16) & ~1) or not terminal or
            int(terminal[1]) != header["state"] or int(terminal[2], 16) != MAGIC):
        raise AcquisitionError("missing hardware breakpoint/terminal PC/ABI evidence")


def source_metadata(root):
    files = set()
    for directory in ("src", "inc", "lib", "cmake"):
        files.update(path for path in (root / directory).rglob("*") if path.is_file()
                     and path.suffix in (".c", ".h", ".s", ".S", ".cmake", ".in", ".ld"))
    for name in ("CMakeLists.txt", "CMakePresets.json", "flake.nix", "flake.lock"):
        if (root / name).is_file():
            files.add(root / name)
    hashes = {str(path.relative_to(root)): digest(path) for path in sorted(files)}
    combined = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"sha256": combined, "files": hashes,
            "root_realpath": str(root.resolve()), "vendor_policy": "excluded frozen vendor"}


def tool_versions():
    result = {}
    for tool in ("arm-none-eabi-gcc", "arm-none-eabi-gdb", "renode", "openocd"):
        try:
            done = subprocess.run([tool, "--version"], capture_output=True, text=True,
                                  timeout=3, check=False)
            result[tool] = {"returncode": done.returncode,
                            "output": (done.stdout + done.stderr)[:4096]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[tool] = {"unavailable": type(exc).__name__}
    return result


def collect(args, root=ROOT):
    out = Path(args.out).absolute()
    final = (root / "data/final").resolve()
    if not out.resolve().is_relative_to(final) or out.resolve() == final:
        raise AcquisitionError("--out must be a new run directory beneath data/final")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()  # deliberately no exist_ok: immutable run identity, no stale dumps
    started = time.monotonic()
    manifest = {"schema_version": 1, "run_id": str(uuid.uuid4()), "status": "started",
                "started_utc": utc(), "scenario": args.scenario,
                "environment": args.environment, "functional_status": "unknown",
                "analysis_required": True, "config": vars(args).copy(),
                "host": {"uname": list(os.uname())},
                "clock_domains": {"dwt_nominal_hz": 8000000,
                                  "renode_dwt": "virtual-time-derived ticks, not CPU cycles",
                                  "host_elapsed": "monotonic seconds, not target time"},
                "sampling": "one run, one GDB connection, no measurement polling",
                "seed_source": "firmware snapshot", "method": "hardware breakpoint post-freeze",
                "physical_wiring": ("confirmed PA9→PA10" if args.confirmed_wiring else
                                    "unconfirmed/assumed PA9→PA10"),
                "runtime_validation": "phase-3 required: Renode reset/halt and hbreak support"}
    atomic_manifest(out, manifest)
    children = []
    pending = out / "snapshot.pending.bin"
    try:
        with contextlib.ExitStack() as stack:
            # Hold HW exclusivity through cleanup and final manifest publication.
            lock = root / "data/.locks" / f"port-{args.port}.lock"
            stack.enter_context(exclusive_lock(lock))
            try:
                elf = Path(args.elf or root / f"build/{args.scenario}/firmware.elf").resolve(strict=True)
                repl = (root / "renode/stm32f103_hsi8.repl").resolve(strict=True)
                manifest["elf"] = {"path": str(elf), "sha256": digest(elf)}
                manifest["source"] = source_metadata(root)
                manifest["platform"] = {"path": str(repl), "sha256": digest(repl)}
                manifest["tool_versions"] = tool_versions()
                manifest["collector"] = {"sha256": digest(Path(__file__).resolve())}
                commands = gdb_text(args, pending)
                (out / "commands.gdb").write_text(commands, encoding="utf-8")
                if args.environment == "hw":
                    occupied = listening(args.port)
                    if args.reuse_openocd:
                        if not occupied:
                            raise AcquisitionError("--reuse-openocd requires an existing daemon")
                        manifest["server"] = {"ownership": "reused, never terminated",
                                              "identity": openocd_identity(args.port)}
                    else:
                        if occupied:
                            raise AcquisitionError("3333 occupied; explicit --reuse-openocd required")
                        config = ('source [find interface/stlink.cfg]\ntransport select hla_swd\n'
                                  'source [find target/stm32f1x.cfg]\ngdb_port 3333\n'
                                  'tcl_port disabled\ntelnet_port disabled\nbindto 127.0.0.1\n')
                        (out / "openocd.cfg").write_text(config, encoding="utf-8")
                        argv = ["openocd", "-f", str(out / "openocd.cfg")]
                else:
                    if listening(args.port):
                        raise AcquisitionError("Renode GDB port already occupied")
                    monitor = free_port()
                    text = resc_text(args, elf, repl, root)
                    (out / "run.resc").write_text(text, encoding="utf-8")
                    argv = ["renode", "--disable-xwt", "-P", str(monitor),
                            "-e", f"s @{resc_path(out / 'run.resc', root)}"]
                    manifest["monitor_port"] = monitor
                if args.environment == "renode" or not args.reuse_openocd:
                    log = stack.enter_context((out / f"{args.environment}-server.log").open("wb"))
                    child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, cwd=root)
                    children.append(child)
                    manifest["server"] = {"ownership": "owned child", "pid": child.pid, "argv": argv}
                    wait_ready(args.port, child)
                    if args.environment == "hw":
                        manifest["server"]["identity"] = openocd_identity(args.port)
                manifest["config_sha256"] = hashlib.sha256(json.dumps(manifest["config"], sort_keys=True).encode()).hexdigest()
                manifest["artifact_sha256"] = {path.name: digest(path) for path in out.iterdir()
                                                if path.suffix in (".resc", ".gdb", ".cfg")}
                atomic_manifest(out, manifest)
                argv = ["arm-none-eabi-gdb", "--nx", "--batch", str(elf), "-x", str(out / "commands.gdb")]
                manifest["gdb_argv"] = argv
                with (out / "gdb.log").open("wb") as log:
                    child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, cwd=root)
                    children.append(child)
                    try:
                        code = child.wait(timeout=args.timeout)
                    except subprocess.TimeoutExpired as exc:
                        manifest["timeout"] = True
                        raise AcquisitionError("GDB run timed out") from exc
                if code:
                    raise AcquisitionError(f"GDB failed with exit {code}")
                raw = pending.read_bytes()
                header = validate_snapshot(raw, args.scenario)
                validate_gdb_log((out / "gdb.log").read_text(errors="replace"), header)
                gdb_output = (out / "gdb.log").read_text(errors="replace")
                initial = re.search(r"FIDELITY_INITIAL_MAGIC=0x([0-9a-fA-F]+)", gdb_output)
                if not initial:
                    raise AcquisitionError("missing initial ABI observation")
                manifest["initial_magic"] = int(initial[1], 16)
                manifest["initial_magic_policy"] = "pre-start RAM may be zero, stale or uninitialized; terminal signature must match ABI"
                # Detect changed ELF/source/platform rather than claiming paired identity.
                if (digest(elf) != manifest["elf"]["sha256"] or
                        source_metadata(root)["sha256"] != manifest["source"]["sha256"] or
                        digest(repl) != manifest["platform"]["sha256"]):
                    raise AcquisitionError("inputs changed during acquisition")
                pending.rename(out / "snapshot.bin")
                (out / "snapshot.bin").chmod(0o444)
                manifest.update(status="complete", acquisition_complete=True,
                                snapshot={"bytes": SIZE, "sha256": digest(out / "snapshot.bin"),
                                          "header": header}, seed=header["seed"],
                                trace_quality="pending semantic analysis (including drops)")
                return_code = 0
            except (Exception, KeyboardInterrupt) as exc:
                manifest.update(status="error", acquisition_complete=False,
                                error={"kind": type(exc).__name__, "message": str(exc)},
                                timeout=manifest.get("timeout", False))
                return_code = 3 if isinstance(exc, SnapshotError) else 1
            finally:
                for child in reversed(children):
                    try:
                        stop_owned(child)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        manifest.setdefault("cleanup_errors", []).append(str(exc))
                        manifest.update(status="error", acquisition_complete=False)
                        return_code = 1
                pending.unlink(missing_ok=True)
                if manifest["status"] == "error" and (out / "snapshot.bin").exists():
                    (out / "snapshot.bin").rename(out / "snapshot.incomplete.bin")
                manifest.update(finished_utc=utc(), host_elapsed_seconds=time.monotonic() - started)
                atomic_manifest(out, manifest)
    except (Exception, KeyboardInterrupt) as exc:
        manifest.update(status="error", acquisition_complete=False,
                        error={"kind": type(exc).__name__, "message": str(exc)},
                        finished_utc=utc(), host_elapsed_seconds=time.monotonic() - started)
        atomic_manifest(out, manifest)
        return 1
    return return_code


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("scenario", choices=("s1", "s2", "s3", "s4"))
    result.add_argument("--environment", required=True, choices=("hw", "renode"))
    result.add_argument("--out", required=True, help="nonexisting directory beneath data/final")
    result.add_argument("--elf")
    result.add_argument("--mips", type=int, default=8,
                        help="PerformanceInMips; policy below constrains the allowed value")
    result.add_argument("--mips-policy", choices=("nominal", "calibrated", "default100-control"),
                        default="nominal",
                        help="nominal=8 datasheet hypothesis; calibrated=single global value "
                             "derived from the designated S1 calibration kernel (held-out "
                             "validated); default100-control=Renode default sensitivity control")
    result.add_argument("--quantum", choices=("0.000001", "0.000000125"), default="0.000001")
    result.add_argument("--uart-delay", choices=("on", "off"), default="on")
    result.add_argument("--port", type=int)
    result.add_argument("--timeout", type=float, default=60)
    result.add_argument("--reuse-openocd", action="store_true")
    result.add_argument("--confirmed-wiring", action="store_true", help="operator confirms PA9→PA10 loopback")
    return result


def parse_args(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    args.port = args.port if args.port is not None else (3333 if args.environment == "hw" else 3336)
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 60:
        cli.error("timeout must be finite, >0 and <=60 seconds")
    if not 1 <= args.mips <= 200:
        cli.error("mips must be 1..200")
    if args.mips_policy == "nominal" and args.mips != 8:
        cli.error("--mips-policy nominal is the datasheet hypothesis: --mips must be 8")
    if args.mips_policy == "default100-control" and args.mips != 100:
        cli.error("--mips-policy default100-control is the Renode default: --mips must be 100")
    if args.mips_policy == "calibrated" and args.mips in (8, 100):
        cli.error("--mips-policy calibrated requires an explicit derived value distinct from 8/100")
    if args.environment == "hw" and args.port != 3333:
        cli.error("hardware port must be 3333")
    if args.environment == "renode" and not 3334 <= args.port <= 65535:
        cli.error("Renode port must be 3334..65535")
    if args.environment != "hw" and args.reuse_openocd:
        cli.error("--reuse-openocd only applies to hardware")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        return collect(args)
    except (OSError, AcquisitionError) as exc:
        print(f"acquisition refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
