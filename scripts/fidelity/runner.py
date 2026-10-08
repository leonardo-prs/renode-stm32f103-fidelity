"""Execução de firmwares finais na bancada (OpenOCD) e no Renode — mesmo ELF.

Protocolo idêntico nos dois ambientes (só o servidor GDB muda):
    reset → hbreak fidelity_complete → continue → (firmware congela o
    snapshot e para) → dump binário de `fidelity_snapshot` → validação ABI.
Nenhuma amostragem durante a medição: o GDB só observa depois do freeze.

Processos: só se encerram filhos deste processo (OpenOCD/Renode/GDB próprios),
por PID. Porta ocupada por terceiro = erro explícito, nunca kill global.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import abi
from .firmware import ROOT, Firmware

HW_PORT = 3333
REPL = ROOT / "renode" / "stm32f103_hsi8.repl"
SOURCE_DIRS = ("src", "inc", "lib", "renode", "cmake", "scripts/fidelity")
SOURCE_FILES = ("CMakeLists.txt", "CMakePresets.json", "flake.lock")


class RunError(RuntimeError):
    pass


# ───────────────────────────── configurações ─────────────────────────────

@dataclass(frozen=True)
class HWConfig:
    env: str = "hw"

    @property
    def tag(self) -> str:
        return "hw"


@dataclass(frozen=True)
class RenodeConfig:
    mips: float = 8.0
    quantum: str = "0.000001"      # segundos virtuais (string exata p/ o monitor)
    uart_delay: bool = True        # STM32_UART AutoUpdateDelay (só S3)
    env: str = "renode"

    @property
    def tag(self) -> str:
        q = {"0.000001": "1us", "0.000000125": "125ns"}.get(self.quantum, self.quantum)
        m = f"{self.mips:g}".replace(".", "p")
        return f"rn-m{m}-q{q}" + ("" if self.uart_delay else "-nodelay")


# ───────────────────────────── utilidades ─────────────────────────────

def utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest() -> dict:
    files = []
    for d in SOURCE_DIRS:
        files += [p for p in (ROOT / d).rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix not in (".pyc",)]
    files += [ROOT / f for f in SOURCE_FILES if (ROOT / f).is_file()]
    hashes = {str(p.relative_to(ROOT)): sha256(p) for p in sorted(files)}
    combined = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"sha256": combined, "files": len(hashes)}


def vcs_revision() -> str:
    try:
        out = subprocess.run(
            ["jj", "log", "-r", "@", "--no-graph", "--ignore-working-copy",
             "-T", 'change_id.short() ++ " " ++ commit_id.short()'],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def free_port(start: int = 3336) -> int:
    for port in range(start, start + 200):
        if listening(port):
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise RunError("nenhuma porta livre >= 3336")


def wait_port(port: int, child: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RunError(f"servidor saiu antes de abrir :{port} (código {child.returncode})")
        if listening(port):
            return
        time.sleep(0.1)
    raise RunError(f"timeout esperando :{port}")


def stop(child: subprocess.Popen | None) -> None:
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def gdb(elf: Path, script: str, log: Path, timeout: float) -> str:
    script_path = log.with_suffix(".gdb")
    script_path.write_text(script)
    argv = ["arm-none-eabi-gdb", "--nx", "--batch", str(elf), "-x", str(script_path)]
    with log.open("w") as out:
        child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT, cwd=ROOT)
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop(child)
            raise RunError(f"GDB excedeu {timeout:.0f} s (firmware não chegou a fidelity_complete?)")
    text = log.read_text(errors="replace")
    if child.returncode != 0:
        raise RunError(f"GDB saiu com {child.returncode}: {text[-400:]}")
    return text


def capture_script(port: int, dump: Path, extra_pre: str = "", extra_post: str = "") -> str:
    # Caminho do dump sem aspas (o GDB 16 trata aspas como parte do nome).
    if re.search(r"[\s'\"]", str(dump)):
        raise RunError(f"caminho de dump com espaço/aspas: {dump}")
    return (
        "set pagination off\nset confirm off\nset remotetimeout 10\n"
        f"target extended-remote 127.0.0.1:{port}\n"
        f"{extra_pre}"
        "hbreak fidelity_complete\n"
        "continue\n"
        'printf "FID_PC=0x%x\\n", $pc\n'
        'printf "FID_COMPLETE=0x%x\\n", &fidelity_complete\n'
        'printf "FID_SIZE=%u\\n", sizeof(fidelity_snapshot)\n'
        f"dump binary memory {dump} &fidelity_snapshot ((char*)&fidelity_snapshot)+sizeof(fidelity_snapshot)\n"
        f"{extra_post}"
        "detach\nquit 0\n"
    )


def check_halt(text: str) -> None:
    pc = re.search(r"FID_PC=0x([0-9a-f]+)", text)
    done = re.search(r"FID_COMPLETE=0x([0-9a-f]+)", text)
    if not pc or not done or (int(pc[1], 16) & ~1) != (int(done[1], 16) & ~1):
        raise RunError("alvo não parou em fidelity_complete")


# ───────────────────────────── execução ─────────────────────────────

@dataclass
class RunResult:
    path: Path
    ok: bool
    error: str = ""


def _finish_run(run_dir: Path, manifest: dict, raw_path: Path) -> RunResult:
    try:
        snap = abi.decode(raw_path.read_bytes())
        raw_path.chmod(0o444)
        manifest.update(status="complete", snapshot_sha256=sha256(raw_path),
                        header={k: v for k, v in snap.header.items()})
        result = RunResult(run_dir, True)
    except (OSError, abi.SnapshotError) as exc:
        manifest.update(status="error", error=f"{type(exc).__name__}: {exc}")
        result = RunResult(run_dir, False, str(exc))
    manifest["finished_utc"] = utc()
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return result


def _base_manifest(fw: Firmware, cfg, run_dir: Path, batch: dict) -> dict:
    return {"schema": 2, "firmware": fw.name, "scenario": fw.scenario, "variant": fw.variant,
            "environment": cfg.env, "config": asdict(cfg), "tag": cfg.tag,
            "started_utc": utc(), **batch}


def batch_identity(fw: Firmware) -> dict:
    if not fw.elf.is_file():
        raise RunError(f"ELF ausente: {fw.elf} (rode o build do preset {fw.name})")
    return {"elf": str(fw.elf.relative_to(ROOT)), "elf_sha256": sha256(fw.elf),
            "source": source_digest(), "revision": vcs_revision(),
            "platform_sha256": sha256(REPL)}


class HWBench:
    """OpenOCD próprio por lote; firmware gravado UMA vez e conferido."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.child: subprocess.Popen | None = None

    def __enter__(self) -> "HWBench":
        if listening(HW_PORT):
            raise RunError(f":{HW_PORT} ocupada por outro processo (não é deste coletor)")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log = (self.log_dir / "openocd.log").open("w")
        self.child = subprocess.Popen(
            ["openocd", "-f", "interface/stlink.cfg", "-f", "target/stm32f1x.cfg",
             "-c", "bindto 127.0.0.1", "-c", f"gdb_port {HW_PORT}",
             "-c", "telnet_port disabled", "-c", "tcl_port disabled"],
            stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
        wait_port(HW_PORT, self.child, 15)
        return self

    def __exit__(self, *exc) -> None:
        stop(self.child)

    def flash(self, fw: Firmware) -> None:
        text = gdb(fw.elf, (
            "set pagination off\nset confirm off\n"
            f"target extended-remote 127.0.0.1:{HW_PORT}\n"
            "monitor reset halt\nload\ncompare-sections\nmonitor reset halt\n"
            "detach\nquit 0\n"), self.log_dir / f"flash-{fw.name}.log", 120)
        if "MIS-MATCHED" in text or " matched" not in text:
            raise RunError(f"verificação da gravação falhou (ver flash-{fw.name}.log)")

    def run(self, fw: Firmware, run_dir: Path, batch: dict, free_run: bool = False) -> RunResult:
        cfg = HWConfig()
        run_dir.mkdir(parents=True)
        manifest = _base_manifest(fw, cfg, run_dir, batch)
        manifest["debugger_during_run"] = "detached, polling off" if free_run else "attached (hbreak)"
        raw = run_dir / "snapshot.bin"
        try:
            t0 = time.monotonic()
            if free_run:
                # Sem SWD durante a execução: polling desligado, alvo solto.
                gdb(fw.elf, (f"target extended-remote 127.0.0.1:{HW_PORT}\n"
                             "monitor poll off\nmonitor reset run\ndetach\nquit 0\n"),
                    run_dir / "start.log", 30)
                time.sleep(fw.timeout_s if fw.timeout_s < 5 else 5)
                text = gdb(fw.elf, (
                    "set pagination off\n"
                    f"target extended-remote 127.0.0.1:{HW_PORT}\nmonitor halt\n"
                    'printf "FID_PC=0x%x\\n", $pc\n'
                    'printf "FID_COMPLETE=0x%x\\n", &fidelity_complete\n'
                    f"dump binary memory {raw} &fidelity_snapshot ((char*)&fidelity_snapshot)+sizeof(fidelity_snapshot)\n"
                    "monitor poll on\ndetach\nquit 0\n"), run_dir / "gdb.log", 30)
                # O laço de fidelity_complete tem 2 instruções: aceitar o PC dentro dele.
                pc = int(re.search(r"FID_PC=0x([0-9a-f]+)", text)[1], 16)
                done = int(re.search(r"FID_COMPLETE=0x([0-9a-f]+)", text)[1], 16) & ~1
                if not done <= pc < done + 16:
                    raise RunError(f"free-run: PC 0x{pc:x} fora de fidelity_complete")
            else:
                text = gdb(fw.elf, capture_script(HW_PORT, raw, extra_pre="monitor reset halt\n"),
                           run_dir / "gdb.log", fw.timeout_s + 20)
                check_halt(text)
            manifest["host_elapsed_s"] = round(time.monotonic() - t0, 3)
        except RunError as exc:
            manifest.update(status="error", error=str(exc), finished_utc=utc())
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
            # Recupera o alvo para o próximo run (reset limpo).
            try:
                gdb(fw.elf, f"target extended-remote 127.0.0.1:{HW_PORT}\nmonitor reset halt\n"
                    "detach\nquit 0\n", run_dir / "recover.log", 30)
            except RunError:
                pass
            return RunResult(run_dir, False, str(exc))
        return _finish_run(run_dir, manifest, raw)


def renode_resc(fw: Firmware, cfg: RenodeConfig, port: int) -> str:
    rel = lambda p: str(Path(p).relative_to(ROOT))  # noqa: E731 — @paths sem aspas
    text = (f'mach create "{fw.name}"\n'
            f"machine LoadPlatformDescription @{rel(REPL)}\n"
            "logLevel 3\n"
            f'emulation SetGlobalQuantum "{cfg.quantum}"\n'
            f"sysbus.cpu PerformanceInMips {cfg.mips:g}\n")
    if fw.uart_loopback:
        text += ('emulation CreateUARTHub "loop" true\n'
                 "connector Connect sysbus.usart1 loop\n"
                 f"sysbus.usart1 AutoUpdateDelay {str(cfg.uart_delay).lower()}\n"
                 "sysbus.usart1 DelayMultiplier 1\n")
    text += f"sysbus LoadELF @{rel(fw.elf)}\nmachine StartGdbServer {port}\n"
    return text


def run_renode(fw: Firmware, cfg: RenodeConfig, run_dir: Path, batch: dict) -> RunResult:
    run_dir.mkdir(parents=True)
    manifest = _base_manifest(fw, cfg, run_dir, batch)
    raw = run_dir / "snapshot.bin"
    port = free_port()
    monitor = free_port(port + 1)
    resc = run_dir / "run.resc"
    resc.write_text(renode_resc(fw, cfg, port))
    child = None
    try:
        with (run_dir / "renode.log").open("w") as log:
            child = subprocess.Popen(
                ["renode", "--disable-xwt", "--port", str(monitor),
                 "-e", f"i @{resc.relative_to(ROOT)}"],
                stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
            wait_port(port, child, 60)
            t0 = time.monotonic()
            text = gdb(fw.elf, capture_script(
                port, raw,
                extra_post=('monitor sysbus.cpu ExecutedInstructions\n'
                            'monitor machine GetTimeSourceInfo\n')),
                run_dir / "gdb.log", fw.timeout_s + 30)
            manifest["host_elapsed_s"] = round(time.monotonic() - t0, 3)
            check_halt(text)
            m = re.search(r"^(0x[0-9A-Fa-f]+)\s*$", text, re.M)
            if m:
                manifest["renode_executed_instructions"] = int(m[1], 16)
            v = re.search(r"Elapsed Virtual Time: (\d+):(\d+):([\d.]+)", text)
            if v:
                manifest["renode_virtual_s"] = (int(v[1]) * 3600 + int(v[2]) * 60
                                                + float(v[3]))
    except RunError as exc:
        manifest.update(status="error", error=str(exc), finished_utc=utc())
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
        return RunResult(run_dir, False, str(exc))
    finally:
        stop(child)
    return _finish_run(run_dir, manifest, raw)


def campaign_dir(campaign: str, fw: Firmware, tag: str) -> Path:
    return ROOT / "data" / "fidelity" / campaign / fw.name / tag


def next_run_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(p.name[4:]) for p in base.glob("run-*") if p.name[4:].isdigit()]
    return base / f"run-{(max(taken) + 1 if taken else 1):03d}"


def tool_versions() -> dict:
    out = {}
    for tool in ("arm-none-eabi-gcc", "arm-none-eabi-gdb", "openocd", "renode"):
        path = shutil.which(tool)
        out[tool] = path or "absent"
    return out


def record_batch(base: Path, info: dict) -> None:
    base.mkdir(parents=True, exist_ok=True)
    with (base / "batches.jsonl").open("a") as f:
        f.write(json.dumps(info, sort_keys=True) + "\n")
