"""Campanha automática: pré-verificação → build → gate → plano congelado →
bancada → Renode nominal → traço de instruções (C1) → calibração (C1,
opcional) → análise.

Estrutura em data/fidelity/<campanha>/:
    plan.json                       plano congelado (hashes, configs, casos)
    campaign.log                    linha do tempo da campanha (UTC do host)
    build/run-NNN/<fw>.log          saída do build de cada firmware
    hw/sessions/run-NNN/            logs do OpenOCD e identificação do exemplar
    hw/<fw>/run-NNN/                um diretório por TENTATIVA (válida ou não)
    renode-nominal/<fw>/run-NNN/
    renode-calibrated/c1-timing/run-NNN/   (só com --calibration)
    instr/{hw,renode}/              traço por stepi do C1-timing
    calibration.json                regra pré-registrada + valor derivado
    analysis/                       tabelas, relatório, figuras, Perfetto

O que garante que um número pertence ao experimento declarado:
  - plan.json congela ELFs (SHA-256), ABI, exemplar, repetições e
    configuração do Renode; a retomada recusa qualquer diferença nesses itens;
  - cada run.json registra o SHA-256 do ELF executado e o do snapshot, e o
    snapshot traz o nonce aleatório gravado pelo host naquele run;
  - na retomada, a identificação física (CPUID/IDCODE/F_SIZE/UID) tem de ser
    a mesma da primeira sessão.
Uma tentativa nunca é apagada: falhas de infraestrutura e snapshots
inválidos ficam registrados com o motivo e entram na contabilidade.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import math
import queue
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from . import abi, instr, targets
from .firmwares import FIRMWARES, Firmware
from .targets import ROOT, TargetError

DATA = ROOT / "data" / "fidelity"
PLAN_SCHEMA = 2
SOURCE_DIRS = ("src", "inc", "lib", "renode", "cmake", "scripts")
SOURCE_FILES = ("CMakeLists.txt", "CMakePresets.json", "flake.nix", "flake.lock")


class CampaignError(RuntimeError):
    """Pré-condição ou incompatibilidade que impede a campanha (exit 1)."""


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path: Path, value: dict) -> None:
    """Grava um registro e o deixa somente-leitura (evidência finalizada)."""
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))
    path.chmod(0o444)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


# ───────────────────────────── diretórios, log e locks ─────────────────────────────

@dataclass
class Paths:
    name: str

    @property
    def root(self) -> Path:
        return DATA / self.name

    def env_dir(self, env: str, fw: str) -> Path:
        return self.root / env / fw

    @property
    def plan(self) -> Path:
        return self.root / "plan.json"

    @property
    def analysis(self) -> Path:
        return self.root / "analysis"


class Log:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.Lock()

    def __call__(self, msg: str) -> None:
        line = f"{utc()}  {msg}"
        with self.lock:
            print(line, flush=True)
            with self.path.open("a") as f:
                f.write(line + "\n")


class Lock:
    """Lock exclusivo por arquivo (fcntl): impede duas campanhas no mesmo HW."""

    def __init__(self, path: Path, what: str):
        self.path, self.what = path, what

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = self.path.open("w")
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fd.close()
            raise CampaignError(f"{self.what} já em uso por outro processo ({self.path})")
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.close()


# ───────────────────────────── pré-verificação ─────────────────────────────

def preflight(envs: list[str], log: Log) -> dict:
    tools = ["cmake", "ninja", "arm-none-eabi-gcc", "arm-none-eabi-gdb", "arm-none-eabi-nm",
             "arm-none-eabi-objdump", "arm-none-eabi-size"]
    if "hw" in envs:
        tools.append("openocd")
    if "renode" in envs:
        tools.append("renode")
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        raise CampaignError(f"ferramentas ausentes no PATH: {missing} (use o ambiente Nix: "
                            "`nix develop` ou scripts/campaign.sh)")
    free = shutil.disk_usage(ROOT).free
    if free < 2 * 1024**3:
        raise CampaignError(f"pouco espaço em disco: {free / 1024**3:.1f} GiB (< 2 GiB)")
    versions = targets.tool_versions()
    log(f"pré-verificação ok; ferramentas: {versions}")
    return versions


def vendor_integrity() -> dict:
    """Confere vendor/ contra a tabela SHA-256 de vendor/README.md."""
    text = (ROOT / "vendor" / "README.md").read_text()
    entries = re.findall(r"^([0-9a-f]{64})\s+\./(\S+)$", text, re.M)
    if not entries:
        raise CampaignError("vendor/README.md sem tabela SHA-256")
    bad = [p for h, p in entries if not (ROOT / "vendor" / p).is_file()
           or sha256_file(ROOT / "vendor" / p) != h]
    if bad:
        raise CampaignError(f"vendor/ alterado (congelado!): {bad[:5]}")
    return {"files": len(entries), "ok": True}


def source_digest() -> dict:
    files = []
    for d in SOURCE_DIRS:
        files += [p for p in (ROOT / d).rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    files += [ROOT / f for f in SOURCE_FILES if (ROOT / f).is_file()]
    per_file = {str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)}
    return {"sha256": hashlib.sha256(json.dumps(per_file, sort_keys=True).encode()).hexdigest(),
            "files": len(per_file)}


def vcs_revision() -> str:
    for argv in (["jj", "log", "-r", "@", "--no-graph", "--ignore-working-copy", "-T",
                  'change_id.short() ++ " " ++ commit_id.short()'],
                 ["git", "rev-parse", "--short", "HEAD"]):
        try:
            out = targets.run_command(argv, timeout_s=10, check=False)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except TargetError:
            continue
    return "desconhecida"


# ───────────────────────────── build e gate ─────────────────────────────

def build(fw: Firmware, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{fw.name}.log"
    with log.open("w") as out:
        # --fresh: configuração do zero, para que o ELF (inclusive a informação de
        # debug) dependa só das fontes e não do histórico da árvore build/<fw>.
        for argv in (["cmake", "--preset", fw.name, "--fresh"],
                     ["cmake", "--build", "--preset", fw.name]):
            try:
                targets.run_command(argv, stdout=out, stderr=subprocess.STDOUT, timeout_s=180)
            except TargetError as exc:
                raise CampaignError(f"build de {fw.name} falhou (ver {log}): {exc}") from exc
    warnings = [line for line in log.read_text().splitlines() if "warning:" in line]
    if warnings:
        raise CampaignError(f"{fw.name}: warnings no build (política: zero): {warnings[:3]}")


USART1_RANGE = (0x40013800, 0x40013C00)
UNALIGNED_HELPERS = (("unaligned_read_word", "ldr"), ("unaligned_read_half", "ldrh"),
                     ("unaligned_write_word", "str"), ("unaligned_write_half", "strh"))


def gate(fw: Firmware) -> dict:
    """Verificações estáticas do ELF. Só afirma o que de fato verifica."""
    elf = fw.elf
    sym = instr.symbols(elf)
    required = ["main", "fid_snapshot", "fid_complete", "fid_host_nonce", "fid_init"]
    if fw.name == "c1-timing":
        required += ["fid_measure", "fid_measure_call", "fid_measure_back"]
    missing = [s for s in required if s not in sym]
    if missing:
        raise CampaignError(f"{fw.name}: símbolos ausentes no ELF: {missing}")

    # Memória: o linker já recusa estourar 64 KiB/20 KiB; aqui só registramos.
    sections = targets.run_command(["arm-none-eabi-size", "-A", str(elf)]).stdout
    size = {m[1]: int(m[2]) for m in re.finditer(r"^(\S+)\s+(\d+)\s+(\d+)$", sections, re.M)}
    ram = size.get(".data", 0) + size.get(".bss", 0)
    flash = sum(size.get(s, 0) for s in (".isr_vector", ".text", ".rodata", ".data"))
    reserved = size.get("._user_heap_stack", 0)
    if ram + reserved > 20 * 1024:
        raise CampaignError(f"{fw.name}: RAM {ram} B + pilha/heap {reserved} B > 20 KiB")

    # Literais do endereço da USART1 no código: só o C4 pode tê-los (fio PA9→PA10).
    dump = targets.run_command(["arm-none-eabi-objdump", "-s", "-j", ".text", "-j", ".rodata",
                                str(elf)]).stdout
    words = []
    for line in dump.splitlines():
        m = re.match(r"^ ([0-9a-f]{8}) ((?:[0-9a-f]{8} ?){1,4})", line)
        if m:
            words += [int.from_bytes(bytes.fromhex(w), "little") for w in m[2].split()]
    usart_literals = sorted({hex(w) for w in words if USART1_RANGE[0] <= w < USART1_RANGE[1]})
    if fw.name != "c4" and usart_literals:
        raise CampaignError(f"{fw.name}: referência à USART1 {usart_literals} — só o C4 pode "
                            "tocar PA9/PA10 (loopback permanente)")

    disasm = targets.run_command(["arm-none-eabi-objdump", "-d", "--no-show-raw-insn", str(elf)]).stdout
    measure = re.search(r"<fid_measure>:\n(.*?)\n\n", disasm, re.S)
    if measure and "push\t{r3, r4, r5, r6, r7, lr}" not in measure[1]:
        raise CampaignError(f"{fw.name}: fid_measure não empilha 6 registros (AAPCS 8 bytes)")
    # C1: o caso desalinhado só vale se o GCC emitiu de fato LDR/LDRH/STR/STRH.
    if fw.name == "c1-functional":
        for name, opcode in UNALIGNED_HELPERS:
            body = re.search(r"<" + name + r">:\n(.*?)(?:\n\n|$)", disasm, re.S)
            ops = re.findall(r"^\s*[0-9a-f]+:\s+(\S+)", body[1], re.M) if body else []
            if ops != [opcode, "bx"]:
                raise CampaignError(f"{fw.name}: {name} não emite {opcode} único: {ops}")

    cc = json.loads((ROOT / "build" / fw.name / "compile_commands.json").read_text())
    flags = sorted({f for e in cc if e["file"].endswith(".c") and "/src/" in e["file"]
                    for f in e["command"].split() if f.startswith(("-O", "-g", "-std", "-mcpu"))})
    return {"elf_sha256": sha256_file(elf), "ram_bytes": ram, "flash_bytes": flash,
            "stack_heap_reserved": reserved, "usart1_literals": usart_literals,
            "compile_flags": flags}


# ───────────────────────────── plano ─────────────────────────────

def quantum_for(mips: int) -> str:
    """Menor quantum = k instruções com k·1000/mips ns inteiro (TimeInterval em ns)."""
    k = mips // math.gcd(mips, 1000)
    ns = k * 1000 // mips
    return f"{ns / 1e9:.9f}"


def make_plan(args, versions: dict, builds: dict, vendor: dict) -> dict:
    return {
        "schema": PLAN_SCHEMA,
        "abi_version": abi.ABI_VERSION,
        "campaign": args.name,
        "created_utc": utc(),
        "mode": "piloto" if args.pilot else "final",
        "board": args.board,
        "board_note": args.board_note,
        "repetitions": args.reps,
        "firmwares": {n: {"id": f"0x{FIRMWARES[n].firmware_id:04x}", "scenario": FIRMWARES[n].scenario,
                          "question": FIRMWARES[n].question,
                          "planned_cases": FIRMWARES[n].planned_cases, **builds[n]}
                      for n in args.firmwares},
        "environments": args.envs,
        "renode_nominal": {"performance_in_mips": targets.NOMINAL_MIPS, "quantum_s": targets.QUANTUM_S,
                           "platform_sha256": sha256_file(targets.REPL),
                           "script_sha256": sha256_file(targets.RESC),
                           "uart_auto_update_delay": False, "fresh_process_per_run": True},
        "calibration": {"enabled": bool(args.calibration), "rule": CALIBRATION_RULE},
        "instructions": {"enabled": bool(args.instr and "c1-timing" in args.firmwares)},
        "collector": {"protocol": "reset → hbreak main → nonce → hbreak fid_complete → dump",
                      "debugger_attached_during_run": True, "sram_polling_during_run": False,
                      "reset_is_power_cycle": False},
        "tools": versions,
        "vendor": vendor,
        "sources": source_digest(),
        "revision": vcs_revision(),
    }


# O que define o experimento. Ferramentas, fontes e revisão ficam registradas
# no plano, mas mudar a análise (ou a documentação) não invalida a coleta: os
# dados pertencem aos ELFs congelados.
FROZEN_KEYS = ("schema", "abi_version", "mode", "board", "repetitions", "environments",
               "renode_nominal", "calibration", "instructions")


def freeze_plan(paths: Paths, plan: dict, resume: bool) -> dict:
    """Grava o plano ou, na retomada, exige que nada que define o experimento mudou."""
    if paths.plan.exists():
        if not resume:
            raise CampaignError(f"campanha '{paths.name}' já existe; use --resume ou outro --name")
        old = read_json(paths.plan)
        diff = [k for k in FROZEN_KEYS if old.get(k) != plan.get(k)]
        if set(old["firmwares"]) != set(plan["firmwares"]):
            diff.append("conjunto de firmwares")
        for name, fw in plan["firmwares"].items():
            o = old["firmwares"].get(name, {})
            if o.get("elf_sha256") != fw["elf_sha256"] or o.get("planned_cases") != fw["planned_cases"]:
                diff.append(f"firmware {name} (ELF ou casos)")
        if diff:
            raise CampaignError(f"retomada incompatível com o plano congelado: {diff}")
        return old
    if resume:
        raise CampaignError(f"--resume: campanha '{paths.name}' não existe")
    paths.root.mkdir(parents=True, exist_ok=True)
    save_json(paths.plan, plan)
    return plan


# ───────────────────────────── execução ─────────────────────────────

def next_attempt_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(p.name[4:]) for p in base.glob("run-*") if p.name[4:].isdigit()]
    d = base / f"run-{(max(taken) + 1 if taken else 1):03d}"
    d.mkdir()
    return d


def count_valid(base: Path, elf_sha256: str) -> tuple[int, int]:
    """(runs válidos do ELF congelado, tentativas) já gravados em `base`."""
    valid = attempts = 0
    for run_dir in sorted(base.glob("run-*")):
        attempts += 1
        rec_path = run_dir / "run.json"
        if not rec_path.exists():        # interrompido antes de gravar: conta só como tentativa
            continue
        rec = read_json(rec_path)
        valid += rec.get("status") == "valid" and rec.get("elf_sha256") == elf_sha256
    return valid, attempts


def record_run(run_dir: Path, fw: Firmware, env: str, config: dict, collected, error: str | None) -> dict:
    """Decodifica, valida e grava run.json (somente-leitura) de uma tentativa."""
    rec = {"firmware": fw.name, "environment": env, "config": config,
           "attempt_dir": run_dir.name, "finished_utc": utc(),
           "elf_sha256": sha256_file(fw.elf), "abi_version": abi.ABI_VERSION}
    if collected is None:
        rec.update(status="infra_error", problems=[error or "?"])
    else:
        raw = run_dir / "snapshot.bin"
        raw.write_bytes(collected.snapshot)
        raw.chmod(0o444)
        rec.update(host_elapsed_s=round(collected.host_elapsed_s, 3), nonce=collected.nonce,
                   snapshot_sha256=hashlib.sha256(collected.snapshot).hexdigest(), **collected.extra)
        try:
            snap = abi.decode(collected.snapshot)
            problems = fw.validate(snap, collected.nonce)
            rec["header"] = {k: snap.header[k] for k in (
                "state", "error", "case_count", "word_count", "ticket_next", "dwt_start", "dwt_end",
                "observer_ticks", "log_ticks", "cpuid", "idcode", "flash_kb", "uid0", "uid1", "uid2",
                "rcc_cr", "rcc_cfgr", "flash_acr", "dbgmcu_cr", "aircr", "stack_free")}
            rec["trace_lost"] = snap.lost
        except abi.SnapshotError as exc:
            problems = [f"snapshot inválido: {exc}"]
        rec.update(status="valid" if not problems else "invalid", problems=problems)
    save_json(run_dir / "run.json", rec)
    return rec


def max_attempts(reps: int) -> int:
    return reps + max(3, reps // 5)


def identity_key(ident: dict) -> tuple:
    return tuple(ident.get(k) for k in ("CPUID", "IDCODE", "FLASH_KB", "UID"))


def first_board_identity(paths: Paths) -> dict | None:
    records = sorted((paths.root / "hw" / "sessions").glob("run-*/identify.json"))
    return read_json(records[0]) if records else None


def run_hw(paths: Paths, plan: dict, fws: list[Firmware], log: Log) -> None:
    reps = plan["repetitions"]
    pending = [fw for fw in fws if count_valid(paths.env_dir("hw", fw.name),
                                               plan["firmwares"][fw.name]["elf_sha256"])[0] < reps]
    if not pending:
        log("bancada: todos os runs planejados já coletados")
        return
    session = next_attempt_dir(paths.root / "hw" / "sessions")
    with targets.Bench(session) as bench:
        ident = bench.identify(pending[0].elf)
        first = first_board_identity(paths)
        save_json(session / "identify.json", ident)
        if first is not None and identity_key(first) != identity_key(ident):
            raise CampaignError("retomada recusada: a identificação física do exemplar mudou")
        log(f"bancada: exemplar informado '{plan['board']}', identificação {ident}")
        for fw in pending:
            base = paths.env_dir("hw", fw.name)
            valid, attempts = count_valid(base, plan["firmwares"][fw.name]["elf_sha256"])
            bench.flash(fw.elf, session / f"flash-{fw.name}.log")
            log(f"hw/{fw.name}: gravado e verificado (sessão {session.name}); "
                f"coletando {reps - valid} runs")
            while valid < reps and attempts < max_attempts(reps):
                run_dir = next_attempt_dir(base)
                attempts += 1
                collected, error = None, None
                try:
                    collected = bench.run(fw.elf, run_dir, fw.timeout_s)
                except TargetError as exc:
                    error = str(exc)
                rec = record_run(run_dir, fw, "hw", {"session": session.name}, collected, error)
                valid += rec["status"] == "valid"
                if rec["status"] != "valid":
                    log(f"hw/{fw.name}/{run_dir.name}: {rec['status']}: {rec['problems'][:2]}")
            log(f"hw/{fw.name}: {valid} válidos em {attempts} tentativas")


def run_renode(paths: Paths, plan: dict, fws: list[Firmware], env: str, mips: int,
               jobs: int, log: Log) -> None:
    quantum = targets.QUANTUM_S if mips == targets.NOMINAL_MIPS else quantum_for(mips)
    config = {"performance_in_mips": mips, "quantum_s": quantum}
    reps = plan["repetitions"]
    slots: queue.Queue = queue.Queue()          # faixas de porta distintas por processo paralelo
    for k in range(jobs):
        slots.put(targets.RENODE_PORT_BASE + 20 * k)

    def one(fw: Firmware, run_dir: Path) -> dict:
        port_base = slots.get()
        try:
            collected, error = None, None
            try:
                collected = targets.run_renode(fw.elf, run_dir, fw.timeout_s, mips=mips,
                                               quantum_s=quantum, port_base=port_base)
            except TargetError as exc:
                error = str(exc)
            return record_run(run_dir, fw, env, config, collected, error)
        finally:
            slots.put(port_base)

    for fw in fws:
        base = paths.env_dir(env, fw.name)
        valid, attempts = count_valid(base, plan["firmwares"][fw.name]["elf_sha256"])
        while valid < reps and attempts < max_attempts(reps):
            batch = min(reps - valid, max_attempts(reps) - attempts)
            dirs = [next_attempt_dir(base) for _ in range(batch)]
            attempts += batch
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for rec, d in zip(pool.map(lambda d: one(fw, d), dirs), dirs):
                    valid += rec["status"] == "valid"
                    if rec["status"] != "valid":
                        log(f"{env}/{fw.name}/{d.name}: {rec['status']}: {rec['problems'][:2]}")
        log(f"{env}/{fw.name}: {valid} válidos em {attempts} tentativas (MIPS {mips}, quantum {quantum} s)")


def run_instruction_traces(paths: Paths, plan: dict, envs: list[str], log: Log) -> None:
    """Traço por stepi do C1-timing, uma vez por ambiente (refeito se o ELF mudou)."""
    fw = FIRMWARES["c1-timing"]
    elf_sha = plan["firmwares"]["c1-timing"]["elf_sha256"]
    for env in envs:
        out = paths.root / "instr" / env
        meta_path = out / "trace.json"
        if meta_path.exists() and read_json(meta_path).get("elf_sha256") == elf_sha:
            continue
        log(f"traço de instruções (stepi) do c1-timing em {env} — pode levar dezenas de minutos")
        attempt = next_attempt_dir(out)
        try:
            if env == "hw":
                instr.trace_hw(fw.elf, attempt, expected_identity=first_board_identity(paths))
            else:
                instr.trace_renode(fw.elf, attempt)
        except (TargetError, ValueError) as exc:
            log(f"traço {env}: FALHOU ({exc}); nível 'instrução' fica sem evidência")
            continue
        # O resultado vigente fica em instr/<env>/; as tentativas, em run-NNN/.
        (out / "instructions.json").unlink(missing_ok=True)
        shutil.copy(attempt / "instructions.json", out / "instructions.json")
        meta_path.unlink(missing_ok=True)
        save_json(meta_path, {"environment": env, "attempt_dir": attempt.name,
                              "elf_sha256": elf_sha, "finished_utc": utc()})
        log(f"traço {env}: ok")


# ───────────────────────────── calibração (C1) ─────────────────────────────

CALIBRATION_RULE = {
    "firmware": "c1-timing",
    "training_loads": ["alu", "sram_copy", "flash_sum", "branch"],
    "evaluation_loads": ["mul", "div_small", "div_large", "crc"],
    "size": 256,
    "statistic": "mediana entre runs do valor 'warm' (mediana das repetições 1..3)",
    "objective": "minimizar o erro relativo absoluto MÉDIO (pesos iguais) do tempo Renode "
                 "previsto vs. placa nas cargas de treino",
    "prediction": "ticks_Renode(m) = ticks_Renode(8) · 8 / m (tempo = instruções / MIPS)",
    "search": "inteiros 1..16 (PerformanceInMips é uint na 1.17.0)",
    "verification": "runs reais do Renode com o m escolhido (renode-calibrated)",
    "scope": "somente C1; nunca aplicado a C2–C4",
}


def choose_mips(hw_warm: dict, rn_warm: dict) -> dict:
    """Aplica CALIBRATION_RULE às medianas (ticks) por carga no tamanho 256."""
    rule = CALIBRATION_RULE
    best = None
    table = []
    for m in range(1, 17):
        errs = [abs(rn_warm[ld] * targets.NOMINAL_MIPS / m - hw_warm[ld]) / hw_warm[ld]
                for ld in rule["training_loads"]]
        mare = sum(errs) / len(errs)
        table.append({"mips": m, "training_mare": mare})
        if best is None or mare < best["training_mare"]:
            best = {"mips": m, "training_mare": mare}
    return {"chosen_mips": best["mips"], "training_mare": best["training_mare"], "search": table}


def warm_medians(paths: Paths, env: str) -> dict:
    """Mediana entre runs válidos do tempo 'warm' de cada carga no tamanho da regra."""
    fw = FIRMWARES["c1-timing"]
    loads = CALIBRATION_RULE["training_loads"] + CALIBRATION_RULE["evaluation_loads"]
    values = {ld: [] for ld in loads}
    for rec_path in sorted(paths.env_dir(env, fw.name).glob("run-*/run.json")):
        if read_json(rec_path).get("status") != "valid":
            continue
        ev = fw.evaluate(abi.decode((rec_path.parent / "snapshot.bin").read_bytes()))
        for m in ev.metrics:
            load, _, size = m.case.partition("/")
            if m.name == "warm" and load in values and size == str(CALIBRATION_RULE["size"]):
                values[load].append(m.value)
    return {ld: median(v) for ld, v in values.items() if v}


def calibrate(paths: Paths, plan: dict, jobs: int, log: Log) -> None:
    """Complemento do C1: aplica a regra pré-registrada e roda o Renode calibrado."""
    cal_path = paths.root / "calibration.json"
    if not cal_path.exists():
        warm = {env: warm_medians(paths, env) for env in ("hw", "renode-nominal")}
        if any(ld not in warm[env] for env in warm for ld in CALIBRATION_RULE["training_loads"]):
            log("calibração: faltam dados de treino (placa e Renode nominal); complemento pulado")
            return
        result = choose_mips(warm["hw"], warm["renode-nominal"])
        save_json(cal_path, {"rule": CALIBRATION_RULE, "inputs_median_warm": warm, **result,
                             "requested_mips": result["chosen_mips"], "computed_utc": utc()})
        log(f"calibração: MIPS escolhido {result['chosen_mips']} (erro médio de treino previsto "
            f"{result['training_mare']:.1%})")
    cal = read_json(cal_path)
    run_renode(paths, plan, [FIRMWARES["c1-timing"]], "renode-calibrated", cal["chosen_mips"], jobs, log)


# ───────────────────────────── fluxo principal ─────────────────────────────

EXIT_COMPLETE, EXIT_ERROR, EXIT_INCOMPLETE = 0, 1, 3


def run_campaign(args) -> int:
    """Executa a campanha inteira. Código de saída:
    0 = campanha completa (com ou sem divergências científicas);
    3 = infraestrutura incompleta (runs válidos < planejado, traço ausente...);
    1 = erro que impediu a campanha (pré-condição, build, plano incompatível)."""
    paths = Paths(args.name)
    paths.root.mkdir(parents=True, exist_ok=True)
    fws = [FIRMWARES[n] for n in args.firmwares]
    with Lock(paths.root / ".lock", f"campanha '{args.name}'"), \
            Lock(DATA / ".build.lock", "os ELFs em build/ (outra campanha compilando)"), \
            Lock(DATA / ".hardware.lock" if "hw" in args.envs else paths.root / ".nohw.lock",
                 "a bancada (ST-Link)"):
        log = Log(paths.root / "campaign.log")
        log(f"campanha '{args.name}' ({'piloto' if args.pilot else 'final'}), exemplar '{args.board}', "
            f"{args.reps} runs, firmwares {args.firmwares}, ambientes {args.envs}")
        versions = preflight(args.envs, log)
        vendor = vendor_integrity()
        builds = {}
        build_dir = next_attempt_dir(paths.root / "build")
        for fw in fws:
            build(fw, build_dir)
            builds[fw.name] = gate(fw)
            log(f"build+gate {fw.name}: ELF {builds[fw.name]['elf_sha256'][:12]}…, "
                f"RAM {builds[fw.name]['ram_bytes']} B")
        plan = freeze_plan(paths, make_plan(args, versions, builds, vendor), args.resume)
        if "hw" in args.envs:
            try:
                run_hw(paths, plan, fws, log)
            except TargetError as exc:
                log(f"BANCADA INDISPONÍVEL: {exc} — etapa da placa incompleta; seguindo com o resto")
        if "renode" in args.envs:
            run_renode(paths, plan, fws, "renode-nominal", targets.NOMINAL_MIPS, args.jobs, log)
        if plan["instructions"]["enabled"]:
            run_instruction_traces(paths, plan, list(args.envs), log)
        if plan["calibration"]["enabled"]:
            calibrate(paths, plan, args.jobs, log)
        summary = analyze_campaign(paths, log)
    log(f"análise: {paths.analysis / 'report.md'}; campanha "
        f"{'COMPLETA' if summary['complete'] else 'INCOMPLETA'}")
    return EXIT_COMPLETE if summary["complete"] else EXIT_INCOMPLETE


def analyze_campaign(paths: Paths, log=print) -> dict:
    from .analysis import analyze
    return analyze(paths.root, log)
