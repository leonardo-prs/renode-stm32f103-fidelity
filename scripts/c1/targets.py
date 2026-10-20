"""Execução de um firmware do C1 na bancada (OpenOCD + ST-Link) ou no Renode.

O protocolo de coleta é o MESMO nos dois ambientes; só o servidor GDB muda:

    reset → hbreak main → continue → grava o bloco do host (c1_host)
          → hbreak c1_complete → continue → (firmware para)
          → dump binário de c1_snapshot → detach

Nada é lido da SRAM durante a execução. O nonce aleatório, copiado pelo
firmware para o header, prova que o snapshot coletado foi produzido NESTE
run (a SRAM da placa sobrevive ao reset).

Processos: só encerramos filhos criados aqui (OpenOCD/Renode/GDB), pelo
grupo de processos. Porta ocupada = erro explícito; nunca matamos processos
de terceiros. O Renode, em modo `-e`, não termina quando um comando falha —
fica parado; por isso todo passo tem timeout e o log do Renode fica no run.
"""
from __future__ import annotations

import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .presets import ROOT

RESC = ROOT / "renode" / "c1.resc"
HW_GDB_PORT = 3333
RENODE_PORT_BASE = 3336

# Política temporal (igual à dos demais cenários): 8 MIPS, quantum de 125 ns
# = 1 instrução por quantum (ver material-base, H-T1: com 1 µs a contagem de
# instruções da tlib tem granularidade de bloco traduzido).
NOMINAL_MIPS = 8
QUANTUM_S = "0.000000125"

# Perfis do sistema sob teste no Renode (plataforma + script):
#   renode      plataforma do projeto, exatamente como os cenários C2–C4 a usam;
#   renode-doc  + só o que a documentação determina: alias de boot da flash
#               (RM0008 §3.4), VTOR = 0 no reset (TRM Tab. 8-15), regiões de
#               bit-band (TRM §4.2) e CCR.DIV_0_TRP gravável (PM0056 §4.4.7).
PROFILES = {
    "renode": ROOT / "renode" / "stm32f103_hsi8.repl",
    "renode-doc": ROOT / "renode" / "c1_doc.repl",
}

_PORT_LOCK = threading.Lock()
_PORTS: set[int] = set()


class TargetError(RuntimeError):
    """Falha de infraestrutura (servidor, GDB, timeout). Nunca vira resultado."""


# ───────────────────────────── processos ─────────────────────────────

def port_in_use(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def find_free_port(start: int) -> int:
    for port in range(start, min(start + 400, 65536)):
        if port not in _PORTS and not port_in_use(port):
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
    """Encerra somente o grupo próprio criado com start_new_session=True."""
    if child is None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=5)
    except ProcessLookupError:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=5)


def run_command(argv: list[str], *, timeout_s: float = 30, check: bool = True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE) -> subprocess.CompletedProcess:
    child = None
    try:
        child = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr, text=True,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        out, err = child.communicate(timeout=timeout_s)
        result = subprocess.CompletedProcess(argv, child.returncode, out, err)
        if check and result.returncode:
            raise TargetError(f"{argv[0]} saiu com código {result.returncode}: {(err or out or '')[-300:]}")
        return result
    except subprocess.TimeoutExpired as exc:
        raise TargetError(f"{argv[0]} excedeu {timeout_s:g} s") from exc
    except OSError as exc:
        raise TargetError(f"não foi possível executar {argv[0]}: {exc}") from exc
    finally:
        stop_child(child)
        if child is not None:
            for stream in (child.stdout, child.stderr):
                if stream is not None:
                    stream.close()


def run_gdb(elf: Path, script: str, log: Path, timeout_s: float) -> str:
    script_path = log.with_suffix(".gdb")
    script_path.write_text(script)
    argv = ["arm-none-eabi-gdb", "--nx", "--batch", str(elf), "-x", str(script_path)]
    with log.open("w") as out:
        result = run_command(argv, stdout=out, stderr=subprocess.STDOUT,
                             timeout_s=timeout_s, check=False)
    text = log.read_text(errors="replace")
    if result.returncode != 0:
        raise TargetError(f"GDB saiu com código {result.returncode}: {text[-300:]}")
    return text


# ───────────────────────────── protocolo de coleta ─────────────────────────────

@dataclass(frozen=True)
class HostBlock:
    """O que o host escreve em c1_host ao parar em main."""
    batch: int = 0
    iters: int = 0
    flags: int = 0
    nonce: int = field(default_factory=lambda: secrets.randbits(32))


def collect_script(port: int, dump: Path, host: HostBlock, reset: str, extra: str = "") -> str:
    if re.search(r"[\s'\"]", str(dump)):
        raise TargetError(f"caminho de dump com espaço/aspas: {dump}")
    return (
        "set pagination off\nset confirm off\nset remotetimeout 15\n"
        f"target extended-remote 127.0.0.1:{port}\n"
        f"{reset}"
        "hbreak main\ncontinue\n"
        f"set var c1_host.nonce = {host.nonce}\n"
        f"set var c1_host.batch = {host.batch}\n"
        f"set var c1_host.iters = {host.iters}\n"
        f"set var c1_host.flags = {host.flags}\n"
        "set var c1_host.magic = 0x54534F48\n"
        "delete\n"
        "hbreak c1_complete\ncontinue\n"
        'printf "C1_PC=0x%x\\n", $pc\n'
        'printf "C1_COMPLETE=0x%x\\n", &c1_complete\n'
        f"dump binary memory {dump} &c1_snapshot ((char*)&c1_snapshot)+sizeof(c1_snapshot)\n"
        f"{extra}"
        "delete\ndetach\nquit 0\n"
    )


def check_stopped_at_complete(text: str) -> None:
    pc = re.search(r"C1_PC=0x([0-9a-f]+)", text)
    done = re.search(r"C1_COMPLETE=0x([0-9a-f]+)", text)
    if not pc or not done:
        raise TargetError("GDB não reportou o PC final")
    if (int(pc[1], 16) & ~1) != (int(done[1], 16) & ~1):
        raise TargetError(f"alvo parou em 0x{int(pc[1], 16):x}, não em c1_complete")


@dataclass
class Collected:
    snapshot: bytes
    host: HostBlock
    host_elapsed_s: float
    extra: dict


# ───────────────────────────── bancada ─────────────────────────────

IDENTITY_KEYS = ("CPUID", "IDCODE", "FLASH_KB", "UID", "ROM_JEP106")


class Bench:
    """OpenOCD próprio na :3333 durante uma sessão; cada run = reset + coleta."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.child: subprocess.Popen | None = None
        self._log = None

    def __enter__(self) -> "Bench":
        if port_in_use(HW_GDB_PORT):
            raise TargetError(f":{HW_GDB_PORT} já está em uso por outro processo "
                              "(OpenOCD de terceiros?) — não será encerrado; libere a porta")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log = (self.log_dir / "openocd.log").open("a")
        try:
            self.child = subprocess.Popen(
                ["openocd", "-f", "interface/stlink.cfg", "-f", "target/stm32f1x.cfg",
                 "-c", "bindto 127.0.0.1", "-c", f"gdb_port {HW_GDB_PORT}",
                 "-c", "telnet_port disabled", "-c", "tcl_port disabled"],
                stdout=self._log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                cwd=ROOT, start_new_session=True)
            wait_port(HW_GDB_PORT, self.child, 20, "OpenOCD")
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc) -> None:
        stop_child(self.child)
        if self._log is not None:
            self._log.close()

    def identify(self, elf: Path) -> dict:
        """Identidade do exemplar lida pelo DEPURADOR (o IDCODE lido pelo
        software fora de depuração devolve 0, ES096 §2.2.2)."""
        text = run_gdb(elf, (
            "set pagination off\n"
            f"target extended-remote 127.0.0.1:{HW_GDB_PORT}\n"
            "monitor reset halt\n"
            'printf "CPUID=0x%08x\\n", *(unsigned int*)0xE000ED00\n'
            'printf "IDCODE=0x%08x\\n", *(unsigned int*)0xE0042000\n'
            'printf "FLASH_KB=%u\\n", *(unsigned short*)0x1FFFF7E0\n'
            'printf "UID=%08x%08x%08x\\n", *(unsigned int*)0x1FFFF7E8, '
            '*(unsigned int*)0x1FFFF7EC, *(unsigned int*)0x1FFFF7F0\n'
            # ROM table do Cortex-M3 (0xE00FF000): PIDR4..PIDR0 dão o JEP106.
            'printf "ROM_JEP106=0x%x\\n", ((*(unsigned int*)0xE00FFFE8 & 0x7) << 4) | '
            '((*(unsigned int*)0xE00FFFE4 >> 4) & 0xF)\n'
            "detach\nquit 0\n"), self.log_dir / "identify.log", 30)
        info = dict(re.findall(r"^(CPUID|IDCODE|FLASH_KB|UID|ROM_JEP106)=(\S+)$", text, re.M))
        if set(info) != set(IDENTITY_KEYS):
            raise TargetError("identificação incompleta do exemplar (ver identify.log)")
        log = (self.log_dir / "openocd.log").read_text(errors="replace")
        version = re.search(r"STLINK (V\S+)", log)
        voltage = re.search(r"Target voltage: ([\d.]+)", log)
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

    def run(self, elf: Path, run_dir: Path, host: HostBlock, timeout_s: float) -> Collected:
        dump = run_dir / "snapshot.bin"
        t0 = time.monotonic()
        try:
            text = run_gdb(elf, collect_script(HW_GDB_PORT, dump, host, "monitor reset halt\n"),
                           run_dir / "gdb.log", timeout_s)
            check_stopped_at_complete(text)
        except TargetError:
            self.recover(elf, run_dir)
            raise
        try:
            snapshot = dump.read_bytes()
        except OSError as exc:
            raise TargetError(f"snapshot não coletado: {exc}") from exc
        return Collected(snapshot, host, time.monotonic() - t0, {})

    def recover(self, elf: Path, run_dir: Path) -> None:
        """Deixa o alvo parado em reset para o próximo run (não apaga nada)."""
        try:
            run_gdb(elf, f"target extended-remote 127.0.0.1:{HW_GDB_PORT}\n"
                    "monitor reset halt\ndetach\nquit 0\n", run_dir / "recover.log", 30)
        except TargetError:
            pass


# ───────────────────────────── Renode ─────────────────────────────

def renode_command(elf: Path, gdb_port: int, profile: str) -> list[str]:
    setup = (f"$elf=@{elf.relative_to(ROOT)}; $gdb_port={gdb_port}; "
             f"$platform=@{PROFILES[profile].relative_to(ROOT)}; $mips={NOMINAL_MIPS}; "
             f'$quantum="{QUANTUM_S}"; i @{RESC.relative_to(ROOT)}')
    # --port -1: sem monitor/telnet (com --port N o Renode só executa o -e
    # quando um cliente telnet conecta).
    return ["renode", "--disable-xwt", "--plain", "--port", "-1", "-e", setup]


class RenodeSession:
    """Processo Renode NOVO com servidor GDB numa porta livre >= 3336."""

    def __init__(self, elf: Path, run_dir: Path, profile: str = "renode",
                 port_base: int = RENODE_PORT_BASE):
        if profile not in PROFILES:
            raise TargetError(f"perfil Renode desconhecido: {profile}")
        self.elf, self.run_dir, self.profile, self.port_base = elf, run_dir, profile, port_base
        self.port: int | None = None
        self.child: subprocess.Popen | None = None
        self._log = None

    def __enter__(self) -> "RenodeSession":
        try:
            with _PORT_LOCK:
                self.port = find_free_port(self.port_base)
                _PORTS.add(self.port)
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._log = (self.run_dir / "renode.log").open("w")
            self.child = subprocess.Popen(
                renode_command(self.elf, self.port, self.profile), stdout=self._log,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=ROOT,
                start_new_session=True)
            wait_port(self.port, self.child, 90, "Renode")
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *exc) -> None:
        try:
            stop_child(self.child)
        finally:
            if self._log is not None:
                self._log.close()
            with _PORT_LOCK:
                _PORTS.discard(self.port)

    def log_text(self) -> str:
        return (self.run_dir / "renode.log").read_text(errors="replace")


def renode_notes(text: str) -> dict:
    """Avisos do Renode relevantes para a interpretação (não para o veredito)."""
    unmapped = sorted(set(re.findall(r"non existing peripheral at (0x[0-9A-Fa-f]+)", text)))
    return {"unmapped_accesses": unmapped,
            "div0_filtered": "FilterCcrDiv0Write is set" in text}


def run_renode(elf: Path, run_dir: Path, host: HostBlock, timeout_s: float,
               profile: str = "renode", port_base: int = RENODE_PORT_BASE) -> Collected:
    """Processo Renode NOVO por run: estado inicial limpo garantido."""
    dump = run_dir / "snapshot.bin"
    t0 = time.monotonic()
    with RenodeSession(elf, run_dir, profile, port_base) as session:
        text = run_gdb(elf, collect_script(
            session.port, dump, host, "",
            extra=("monitor sysbus.cpu ExecutedInstructions\n"
                   "monitor sysbus.cpu PerformanceInMips\n")),
            run_dir / "gdb.log", timeout_s)
        check_stopped_at_complete(text)
    extra = renode_notes(session.log_text())
    m = re.search(r"^(0x[0-9A-Fa-f]+)\s*\n(0x[0-9A-Fa-f]+)\s*$", text, re.M)
    if m:
        extra["executed_instructions"] = int(m[1], 16)
        extra["performance_in_mips"] = int(m[2], 16)
    if extra.get("performance_in_mips") != NOMINAL_MIPS:
        raise TargetError("Renode não confirmou o MIPS nominal (ver gdb.log)")
    try:
        snapshot = dump.read_bytes()
    except OSError as exc:
        raise TargetError(f"snapshot não coletado: {exc}") from exc
    return Collected(snapshot, host, time.monotonic() - t0, extra)


def tool_versions() -> dict:
    out = {}
    for tool in ("arm-none-eabi-gcc", "arm-none-eabi-gdb", "arm-none-eabi-objdump", "cmake",
                 "ninja", "openocd", "renode"):
        try:
            r = run_command([tool, "--version"], timeout_s=20)
            lines = (r.stdout + r.stderr).strip().splitlines()
            out[tool] = lines[0] if lines else "?"
        except TargetError as exc:
            out[tool] = f"indisponível ({type(exc).__name__})"
    out["python"] = sys.version.split()[0]
    return out
