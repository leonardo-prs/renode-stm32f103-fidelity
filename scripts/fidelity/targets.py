"""Execução de um firmware na bancada (OpenOCD + ST-Link) ou no Renode.

O protocolo de coleta é o MESMO nos dois ambientes; só o servidor GDB muda:

    reset → hbreak main → continue → grava nonce do host em fid_host_nonce
          → hbreak fid_complete → continue → (firmware congela e para)
          → dump binário de fid_snapshot → detach

Nada é lido da SRAM durante a execução: com o alvo rodando, o GDB só espera
o breakpoint. O nonce (aleatório por run) é copiado pelo firmware para o
header em fid_init(), provando que o snapshot coletado foi produzido NESTE
run (a SRAM da placa sobrevive ao reset).

Processos: só encerramos filhos criados aqui (OpenOCD/Renode/GDB), pelo
PID. Porta ocupada = erro explícito; nunca matamos processos de terceiros.
O Renode, em modo `-e`, não termina quando um comando falha — fica parado;
por isso todo passo tem timeout e o log do Renode é guardado no run.
"""
from __future__ import annotations

import os
import re
import secrets
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPL = ROOT / "renode" / "stm32f103_hsi8.repl"
RESC = ROOT / "renode" / "fidelity.resc"
HW_GDB_PORT = 3333
RENODE_PORT_BASE = 3336

# Política temporal da campanha principal (README, "Configuração Renode").
NOMINAL_MIPS = 8
QUANTUM_S = "0.000000125"   # 1 instrução a 8 MIPS (ver README, decisões)


class TargetError(RuntimeError):
    """Falha de infraestrutura (servidor, GDB, timeout). Nunca vira resultado."""


# ───────────────────────────── processos ─────────────────────────────

def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def find_free_port(start: int) -> int:
    for port in range(start, start + 400):
        if port_in_use(port):
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise TargetError(f"nenhuma porta livre a partir de {start}")


def wait_port(port: int, child: subprocess.Popen, timeout_s: float, what: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise TargetError(f"{what} terminou antes de abrir :{port} (código {child.returncode})")
        if port_in_use(port):
            return
        time.sleep(0.1)
    raise TargetError(f"{what} não abriu :{port} em {timeout_s:.0f} s")


def stop_child(child: subprocess.Popen | None) -> None:
    """Encerra um processo FILHO deste coletor (SIGTERM, depois SIGKILL)."""
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def run_gdb(elf: Path, script: str, log: Path, timeout_s: float) -> str:
    script_path = log.with_suffix(".gdb")
    script_path.write_text(script)
    argv = ["arm-none-eabi-gdb", "--nx", "--batch", str(elf), "-x", str(script_path)]
    with log.open("w") as out:
        child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, cwd=ROOT)
        try:
            child.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            stop_child(child)
            raise TargetError(f"GDB excedeu {timeout_s:.0f} s (alvo não chegou a fid_complete?)")
    text = log.read_text(errors="replace")
    if child.returncode != 0:
        raise TargetError(f"GDB saiu com código {child.returncode}: {text[-300:]}")
    return text


def collect_script(port: int, dump: Path, nonce: int, reset: str, extra: str = "") -> str:
    if re.search(r"[\s'\"]", str(dump)):
        raise TargetError(f"caminho de dump com espaço/aspas: {dump}")
    return (
        "set pagination off\nset confirm off\nset remotetimeout 15\n"
        f"target extended-remote 127.0.0.1:{port}\n"
        f"{reset}"
        "hbreak main\ncontinue\n"
        f"set var fid_host_nonce = {nonce}\n"
        "delete\n"
        "hbreak fid_complete\ncontinue\n"
        'printf "FID_PC=0x%x\\n", $pc\n'
        'printf "FID_COMPLETE=0x%x\\n", &fid_complete\n'
        f"dump binary memory {dump} &fid_snapshot ((char*)&fid_snapshot)+sizeof(fid_snapshot)\n"
        f"{extra}"
        "delete\ndetach\nquit 0\n"
    )


def check_stopped_at_complete(text: str) -> None:
    pc = re.search(r"FID_PC=0x([0-9a-f]+)", text)
    done = re.search(r"FID_COMPLETE=0x([0-9a-f]+)", text)
    if not pc or not done:
        raise TargetError("GDB não reportou o PC final")
    if (int(pc[1], 16) & ~1) != (int(done[1], 16) & ~1):
        raise TargetError(f"alvo parou em 0x{int(pc[1], 16):x}, não em fid_complete")


@dataclass
class Collected:
    snapshot: bytes
    nonce: int
    host_elapsed_s: float
    extra: dict


# ───────────────────────────── bancada ─────────────────────────────

class Bench:
    """OpenOCD próprio na :3333 durante um lote; cada run = reset + coleta."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.child: subprocess.Popen | None = None

    def __enter__(self) -> "Bench":
        if port_in_use(HW_GDB_PORT):
            raise TargetError(f":{HW_GDB_PORT} já está em uso por outro processo "
                              "(OpenOCD de terceiros?) — não será encerrado; libere a porta")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log = (self.log_dir / "openocd.log").open("a")
        self.child = subprocess.Popen(
            ["openocd", "-f", "interface/stlink.cfg", "-f", "target/stm32f1x.cfg",
             "-c", "bindto 127.0.0.1", "-c", f"gdb_port {HW_GDB_PORT}",
             "-c", "telnet_port disabled", "-c", "tcl_port disabled"],
            stdout=self._log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=ROOT)
        wait_port(HW_GDB_PORT, self.child, 20, "OpenOCD")
        return self

    def __exit__(self, *exc) -> None:
        stop_child(self.child)
        self._log.close()

    def identify(self) -> dict:
        """Metadados do exemplar (diagnóstico, não autenticação)."""
        text = run_gdb(ROOT / "build" / "c1-functional" / "firmware.elf", (
            "set pagination off\n"
            f"target extended-remote 127.0.0.1:{HW_GDB_PORT}\n"
            "monitor reset halt\n"
            'printf "CPUID=0x%08x\\n", *(unsigned int*)0xE000ED00\n'
            'printf "IDCODE=0x%08x\\n", *(unsigned int*)0xE0042000\n'
            'printf "FLASH_KB=%u\\n", *(unsigned short*)0x1FFFF7E0\n'
            'printf "UID=%08x%08x%08x\\n", *(unsigned int*)0x1FFFF7F0, '
            '*(unsigned int*)0x1FFFF7EC, *(unsigned int*)0x1FFFF7E8\n'
            "detach\nquit 0\n"), self.log_dir / "identify.log", 30)
        info = dict(re.findall(r"^(CPUID|IDCODE|FLASH_KB|UID)=(\S+)$", text, re.M))
        version = re.search(r"STLINK (V\S+)", (self.log_dir / "openocd.log").read_text(errors="replace"))
        voltage = re.search(r"Target voltage: ([\d.]+)", (self.log_dir / "openocd.log").read_text(errors="replace"))
        info["stlink"] = version[1] if version else "?"
        info["target_voltage"] = voltage[1] if voltage else "?"
        return info

    def flash(self, elf: Path, log: Path) -> None:
        text = run_gdb(elf, (
            "set pagination off\nset confirm off\n"
            f"target extended-remote 127.0.0.1:{HW_GDB_PORT}\n"
            "monitor reset halt\nload\ncompare-sections\nmonitor reset halt\n"
            "detach\nquit 0\n"), log, 120)
        if "MIS-MATCHED" in text or " matched" not in text:
            raise TargetError(f"verificação da gravação falhou (ver {log.name})")

    def run(self, elf: Path, run_dir: Path, timeout_s: float) -> Collected:
        nonce = secrets.randbits(32)
        dump = run_dir / "snapshot.bin"
        t0 = time.monotonic()
        try:
            text = run_gdb(elf, collect_script(HW_GDB_PORT, dump, nonce, "monitor reset halt\n"),
                           run_dir / "gdb.log", timeout_s)
            check_stopped_at_complete(text)
        except TargetError:
            self.recover(elf, run_dir)
            raise
        return Collected(dump.read_bytes(), nonce, time.monotonic() - t0, {})

    def recover(self, elf: Path, run_dir: Path) -> None:
        """Deixa o alvo parado em reset para o próximo run (não apaga nada)."""
        try:
            run_gdb(elf, f"target extended-remote 127.0.0.1:{HW_GDB_PORT}\n"
                    "monitor reset halt\ndetach\nquit 0\n", run_dir / "recover.log", 30)
        except TargetError:
            pass


# ───────────────────────────── Renode ─────────────────────────────

def renode_command(elf: Path, gdb_port: int, mips: int, quantum_s: str = QUANTUM_S) -> list[str]:
    rel = elf.relative_to(ROOT)
    setup = (f"$elf=@{rel}; $gdb_port={gdb_port}; $mips={mips}; "
             f'$quantum="{quantum_s}"; i @{RESC.relative_to(ROOT)}')
    # --port -1: sem monitor/telnet (com --port N o Renode só executa o -e
    # quando um cliente telnet conecta).
    return ["renode", "--disable-xwt", "--plain", "--port", "-1", "-e", setup]


class RenodeSession:
    """Processo Renode próprio (novo) com servidor GDB numa porta livre >= 3336."""

    def __init__(self, elf: Path, run_dir: Path, mips: int = NOMINAL_MIPS,
                 quantum_s: str = QUANTUM_S, port_base: int = RENODE_PORT_BASE):
        self.elf, self.run_dir, self.mips, self.quantum_s = elf, run_dir, mips, quantum_s
        self.port = find_free_port(port_base)
        self.child: subprocess.Popen | None = None

    def __enter__(self) -> "RenodeSession":
        self._log = (self.run_dir / "renode.log").open("w")
        self.child = subprocess.Popen(
            renode_command(self.elf, self.port, self.mips, self.quantum_s), stdout=self._log,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=ROOT)
        try:
            wait_port(self.port, self.child, 90, "Renode")
        except TargetError:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc) -> None:
        stop_child(self.child)
        self._log.close()

    def unmapped_accesses(self) -> list[str]:
        text = (self.run_dir / "renode.log").read_text(errors="replace")
        return sorted(set(re.findall(r"from non existing peripheral at (0x[0-9A-Fa-f]+)", text)))


def run_renode(elf: Path, run_dir: Path, timeout_s: float, mips: int = NOMINAL_MIPS,
               quantum_s: str = QUANTUM_S, port_base: int = RENODE_PORT_BASE) -> Collected:
    """Processo Renode NOVO por run: estado inicial limpo garantido."""
    nonce = secrets.randbits(32)
    dump = run_dir / "snapshot.bin"
    t0 = time.monotonic()
    with RenodeSession(elf, run_dir, mips, quantum_s, port_base) as session:
        text = run_gdb(elf, collect_script(
            session.port, dump, nonce, "",
            extra=("monitor sysbus.cpu ExecutedInstructions\n"
                   "monitor sysbus.cpu PerformanceInMips\n"
                   "monitor machine GetTimeSourceInfo\n")),
            run_dir / "gdb.log", timeout_s)
        check_stopped_at_complete(text)
    extra = {"unmapped_accesses": session.unmapped_accesses()}
    m = re.search(r"^(0x[0-9A-Fa-f]+)\s*\n(0x[0-9A-Fa-f]+)\s*$", text, re.M)
    if m:
        extra["executed_instructions"] = int(m[1], 16)
        extra["performance_in_mips_effective"] = int(m[2], 16)
    v = re.search(r"Elapsed Virtual Time: (\d+):(\d+):([\d.]+)", text)
    if v:
        extra["virtual_time_s"] = int(v[1]) * 3600 + int(v[2]) * 60 + float(v[3])
    return Collected(dump.read_bytes(), nonce, time.monotonic() - t0, extra)


def tool_versions() -> dict:
    """Versões das ferramentas (texto da 1ª linha de --version)."""
    out = {}
    for tool, args in (("arm-none-eabi-gcc", ["--version"]), ("arm-none-eabi-gdb", ["--version"]),
                       ("openocd", ["--version"]), ("renode", ["--version"]),
                       ("trace_processor_shell", ["--version"])):
        try:
            r = subprocess.run([tool, *args], capture_output=True, text=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            lines = (r.stdout + r.stderr).strip().splitlines()
            out[tool] = lines[0] if lines else "?"
        except (OSError, subprocess.TimeoutExpired) as exc:
            out[tool] = f"indisponível ({type(exc).__name__})"
    out["python"] = os.sys.version.split()[0]
    return out
