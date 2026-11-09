"""Common support for the scripts of every scenario: build, ELF symbols, the data of each case
(data/), environment, Renode run and the events each run writes to its log.

Renode runs through the Robot Framework (robot/*.robot, via `renode-test`): the project machine
(platform, R1 profile of 8 MIPS, 125 ns quantum) and the hooks are in robot/renode.resource. Each
hook writes one `EVENT` line to the run's renode.log; read_run() turns those lines into events.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
NS_PER_TICK = 125       # 1 instruction = 1 HCLK cycle at 8 MHz (R1 profile, see robot/renode.resource)


# ───────────────────────────── events of a run ─────────────────────────────
# Each hook of robot/renode.resource writes one line `EVENT <KIND> name=value ...` to the run's
# renode.log; scripts/board.py writes board.log with the same RECORD or UNEXPECTED_EXCEPTION line.
# Each kind is one class below, and its fields are the names in the line.

class AddressHook(NamedTuple):
    """EVENT ADDRESS: before the instruction at `pc` executes."""
    pc: int
    time_ns: int            # virtual time
    instructions: int       # instructions executed before this one
    r0: int
    r1: int
    xpsr: int

    @property
    def ipsr(self) -> int:
        return self.xpsr & 0x1FF


class Write(NamedTuple):
    """EVENT WRITE: a word write to a watched address."""
    address: int
    value: int
    time_ns: int
    instructions: int
    pc: int                 # the store instruction


class ExceptionEntry(NamedTuple):
    """EVENT EXCEPTION_ENTRY. Its time is only an observation (see the instruments case)."""
    time_ns: int
    instructions: int
    pc: int
    xpsr: int

    @property
    def ipsr(self) -> int:
        return self.xpsr & 0x1FF


class ExceptionExit(NamedTuple):
    """EVENT EXCEPTION_EXIT. Its time is only an observation (see the instruments case)."""
    time_ns: int
    instructions: int
    pc: int
    xpsr: int

    @property
    def ipsr(self) -> int:
        return self.xpsr & 0x1FF


class MonitorPause(NamedTuple):
    """EVENT MONITOR_PAUSE: `words` are the memory words the monitor read."""
    time_ns: int
    instructions: int
    words: tuple[int, ...]


class Record(NamedTuple):
    """EVENT RECORD: the firmware record, read at record_complete. The board has no virtual
    time: there, time_ns and instructions are absent (None)."""
    words: tuple[int, ...]
    time_ns: int | None = None
    instructions: int | None = None


class UnexpectedException(NamedTuple):
    """EVENT UNEXPECTED_EXCEPTION: the firmware reached unexpected_exception."""


EVENT_KINDS = {"ADDRESS": AddressHook, "WRITE": Write, "EXCEPTION_ENTRY": ExceptionEntry,
               "EXCEPTION_EXIT": ExceptionExit, "MONITOR_PAUSE": MonitorPause, "RECORD": Record,
               "UNEXPECTED_EXCEPTION": UnexpectedException}


def parse_event(line: str) -> Any:
    """The event of one log line, or None if the line is not an EVENT line. A value is a number
    (decimal or 0x hexadecimal), or a comma-separated list of numbers for `words`. An unknown
    kind or a missing or unknown field raises."""
    match = re.search(r"\bEVENT ([A-Z_]+)(.*)", line)
    if not match:
        return None
    fields: dict[str, Any] = {}
    for item in match[2].split():
        name, _, text = item.partition("=")
        fields[name] = tuple(int(w, 0) for w in text.split(",") if w) if name == "words" else int(text, 0)
    return EVENT_KINDS[match[1]](**fields)


@dataclass
class Run:
    events: list[Any]                   # in log order
    record_event: Record                # empty if the run ended at unexpected_exception
    unexpected_exception: bool

    def of(self, kind: type) -> list:
        return [e for e in self.events if type(e) is kind]

    @property
    def address_hooks(self) -> list[AddressHook]:
        return self.of(AddressHook)

    @property
    def writes(self) -> list[Write]:
        return self.of(Write)

    @property
    def exception_entries(self) -> list[ExceptionEntry]:
        return self.of(ExceptionEntry)

    @property
    def exception_exits(self) -> list[ExceptionExit]:
        return self.of(ExceptionExit)

    @property
    def monitor_pauses(self) -> list[MonitorPause]:
        return self.of(MonitorPause)

    @property
    def record(self) -> list[int]:
        return list(self.record_event.words)


def read_run(directory: Path, log: str = "renode.log") -> Run:
    """Events of directory/<log> (renode.log, or board.log written by scripts/board.py). A
    missing log, a malformed line, or anything other than exactly one RECORD (or an
    UNEXPECTED_EXCEPTION without a RECORD) raises."""
    events = []
    for line in (directory / log).read_text().splitlines():
        try:
            event = parse_event(line)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{directory}: malformed event line ({error!r}): {line}") from error
        if event is not None:
            events.append(event)
    records = [e for e in events if type(e) is Record]
    unexpected = any(type(e) is UnexpectedException for e in events)
    if len(records) != 1 and not (unexpected and not records):
        raise ValueError(f"{directory}: {len(records)} RECORD events (expected 1)")
    return Run(events, records[0] if records else Record(()), unexpected)


def repetition_signature(run: Run) -> tuple:
    """What must repeat identically: every event, except the time of the exception entry/exit
    hooks (an observation that depends on where the monitor paused, see the instruments case)."""
    return tuple((type(e).__name__, e._replace(time_ns=None) if type(e) in (ExceptionEntry, ExceptionExit) else e)
                 for e in run.events)


# ───────────────────────────── runs and data ─────────────────────────────

def run_robot(suite: str, tag: str, results: Path, variables: dict[str, str]) -> None:
    """Run the tests of `suite` with tag `tag` in renode-test. The Robot result (log.html,
    report, renode-test.log) goes to `results`. Aborts if any test fails (including a hook error)."""
    results.mkdir(parents=True)
    config = results / "renode.config"         # log lines without the host clock time
    config.write_text("[general]\nlog-timestamps-type = None\n")
    cmd = ["renode-test", f"robot/{suite}.robot", "--include", tag, "--results-dir", str(results),
           "--renode-config", str(config)]
    for k, v in variables.items():
        cmd += ["--variable", f"{k}:{v}"]
    with (results / "renode-test.log").open("w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL).returncode
    if rc != 0:
        raise SystemExit(f"{tag}: renode-test exited with code {rc} (see {results / 'renode-test.log'} and "
                         f"{results / 'log.html'})")


def symbols(elf: Path) -> dict[str, int]:
    """Addresses of the ELF symbols (Thumb bit removed)."""
    out = subprocess.run(["arm-none-eabi-nm", str(elf)], check=True, capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) & ~1 for p in (line.split() for line in out.splitlines()) if len(p) == 3}


def build_firmware(firmware: str) -> None:
    """Clean build of one firmware in the single build tree: its objects and outputs are removed
    (the other firmwares stay), then CMake configures build/ and builds only that target."""
    shutil.rmtree(ROOT / "build" / firmware, ignore_errors=True)
    shutil.rmtree(ROOT / "build" / "CMakeFiles" / f"{firmware}.dir", ignore_errors=True)
    subprocess.run(["cmake", "-B", "build", "-G", "Ninja"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["cmake", "--build", "build", "--target", firmware], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)


def firmware_symbols(firmware: str, build: bool) -> dict[str, int]:
    """Symbols of build/<firmware>/firmware.elf, after its clean build if `build`."""
    if build:
        build_firmware(firmware)
    return symbols(ROOT / "build" / firmware / "firmware.elf")


def new_case(directory: Path, firmware: str, sym: dict[str, int], names: tuple[str, ...], extra: dict,
             renode: bool = True) -> None:
    """Start the data of one case in one condition, data/<scenario>[/<condition>]/<case>/: remove
    what an earlier run of the same case and condition left there (only this directory) and write
    its environment.json with the environment, the symbols in `names` and `extra` (repetitions,
    wire...). A case that runs only on the board does not record a Renode version (renode=False)."""
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    env = {**environment(ROOT / "build" / firmware / "firmware.elf", renode),
           "symbols": {s: sym[s] for s in names if s in sym}, **extra}
    write_environment(directory, env)


def read_environment(directory: Path) -> dict:
    return json.loads((directory / "environment.json").read_text())


def write_environment(directory: Path, env: dict) -> None:
    (directory / "environment.json").write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n")


def has_data(directory: Path) -> bool:
    """A case directory written by new_case (the case ran in this condition)."""
    return (directory / "environment.json").exists()


def environment_table(directories: list[Path], data: Path) -> list[str]:
    """Lines of result.md with the environment of each case directory it judges."""
    standard = ("elf", "elf_sha256", "renode", "reps", "symbols")
    lines = ["| Data | ELF | ELF SHA-256 | Renode | reps | other |",
             "|---|---|---|---|---|---|"]
    for d in directories:
        env = read_environment(d)
        other = "; ".join(f"{k}: {v}" for k, v in env.items() if k not in standard)
        lines.append(f"| `{d.relative_to(data)}` | `{env['elf']}` | `{env['elf_sha256']}` | {env.get('renode', '—')} | "
                     f"{env['reps']} | {other} |")
    return lines


def environment(elf: Path, renode: bool = True) -> dict[str, str]:
    """What identifies a run: the ELF and its SHA-256, and Renode if it ran there."""
    env = {"elf": str(elf.relative_to(ROOT)), "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest()}
    if renode:
        env["renode"] = subprocess.run(["renode", "--version"], capture_output=True, text=True).stdout.split("\n")[0].strip()
    return env
