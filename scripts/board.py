"""Run a case firmware on the project board (Blue Pill, ST-Link, OpenOCD) with the same protocol
as in Renode (src/common/case.h).

Each step is one OpenOCD invocation, with no GDB and no server left running. A run writes
board.log with the same EVENT RECORD / EVENT UNEXPECTED_EXCEPTION line as the Renode hooks
(without time: the board has no virtual time), so sim.read_run reads both alike.
"""
from __future__ import annotations

import re
import socket
import subprocess
from pathlib import Path

import sim

PORT = 3333             # bench rule: an OpenOCD already listening here means the board is in use
OPENOCD = ["openocd", "-f", "interface/stlink.cfg", "-f", "target/stm32f1x.cfg",
           "-c", "gdb_port disabled", "-c", "tcl_port disabled", "-c", "telnet_port disabled"]


def openocd(commands: list[str], log: Path, timeout_s: float = 60) -> str:
    """Run one OpenOCD command line ending in shutdown; its output goes to `log`."""
    try:
        sock = socket.create_connection(("127.0.0.1", PORT), timeout=0.5)
        sock.close()
        raise SystemExit(f"port {PORT} is in use: another OpenOCD holds the board")
    except OSError:
        pass                                    # nothing listening (refused or timed out)
    cmd = OPENOCD + [x for c in commands for x in ("-c", c)] + ["-c", "shutdown"]
    try:
        r = subprocess.run(cmd, cwd=sim.ROOT, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"OpenOCD did not finish in {timeout_s} s") from exc
    out = r.stdout + r.stderr
    log.write_text(out)
    if r.returncode != 0:
        raise SystemExit(f"OpenOCD exited with code {r.returncode} (see {log})")
    return out


def memory(out: str) -> dict[int, int]:
    """Words printed by `mdw`/`mdh` (lines `0xADDRESS: word word …`), by address."""
    mem = {}
    for line in out.splitlines():
        m = re.fullmatch(r"0x([0-9a-f]+): ([0-9a-f ]+)", line.strip())
        if m:
            for i, word in enumerate(m[2].split()):
                mem[int(m[1], 16) + 4 * i] = int(word, 16)
    return mem


def flash(elf: Path, log: Path) -> None:
    """Write the ELF to flash and verify it."""
    log.parent.mkdir(parents=True, exist_ok=True)
    if "** Verified OK **" not in openocd([f"program {elf} verify"], log, 120):
        raise SystemExit(f"flash verification failed (see {log})")


def run(sym: dict[str, int], case_number: int, directory: Path, timeout_ms: int = 10_000) -> None:
    """One run of case `case_number` of the flashed firmware: reset, write selected_case, stop at
    record_complete or unexpected_exception and write directory/board.log. Any other end stops
    the script."""
    record, length = sym["record"], sym["record_length"]
    out = openocd(["init", "reset halt", f"mww {sym['selected_case']:#x} {case_number}",
                   f"bp {sym['record_complete']:#x} 2 hw", f"bp {sym['unexpected_exception']:#x} 2 hw", "resume",
                   f"wait_halt {timeout_ms}", "reg pc", f"mdw {length:#x}",
                   f"mdw {record:#x} [expr {{[mrw {length:#x}] > 0 ? [mrw {length:#x}] : 1}}]"],
                  directory / "openocd.log", timeout_ms / 1000 + 30)
    pc = re.search(r"pc \(/32\): 0x([0-9a-f]+)", out)
    if pc is None:
        raise SystemExit(f"no PC after the halt (see {directory / 'openocd.log'})")
    if int(pc[1], 16) == sym["unexpected_exception"]:
        (directory / "board.log").write_text("EVENT UNEXPECTED_EXCEPTION\n")
        return
    if int(pc[1], 16) != sym["record_complete"]:
        raise SystemExit(f"halted at {pc[1]}, not at record_complete (see {directory / 'openocd.log'})")
    mem = memory(out)
    words = [mem[record + 4 * k] for k in range(mem[length])]
    (directory / "board.log").write_text("EVENT RECORD words=" + ",".join(map(str, words)) + "\n")
