"""Campanha automática: pré-verificação → build → gate → plano congelado →
bancada → Renode nominal → traço de instruções (C1) → calibração (C1,
opcional) → análise.

Estrutura em data/fidelity/<campanha>/:
    plan.json                       plano congelado (hashes, configs, casos)
    campaign.log                    linha do tempo da campanha (UTC do host)
    build/<fw>.log                  saída do build de cada firmware
    hw/session-NN/                  logs do OpenOCD e identificação do exemplar
    hw/<fw>/run-NNN/                um diretório por TENTATIVA (válida ou não)
    renode-nominal/<fw>/run-NNN/
    renode-calibrated/c1-timing/run-NNN/   (só com --calibration)
    instr/{hw,renode}/              traço por stepi do C1-timing
    calibration.json                regra pré-registrada + valor derivado
    analysis/                       tabelas, relatório, figuras, Perfetto

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

from . import abi, instr, targets
from .firmwares import FIRMWARES, Firmware
from .targets import ROOT, TargetError

DATA = ROOT / "data" / "fidelity"
PLAN_SCHEMA = 1
SOURCE_DIRS = ("src", "inc", "lib", "renode", "cmake", "scripts")
SOURCE_FILES = ("CMakeLists.txt", "CMakePresets.json", "flake.nix", "flake.lock")


class CampaignError(RuntimeError):
    """Pré-condição ou incompatibilidade que impede a campanha (exit 1)."""


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ───────────────────────────── diretórios e log ─────────────────────────────

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
        self.fd.write(f"{utc()}\n")
        self.fd.flush()
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
    if any(e.startswith("renode") for e in envs):
        tools.append("renode")
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        raise CampaignError(f"ferramentas ausentes no PATH: {missing} (use o ambiente Nix: "
                            "`nix develop` ou scripts/campaign.sh)")
    if "hw" in envs and targets.port_in_use(targets.HW_GDB_PORT):
        raise CampaignError(f":{targets.HW_GDB_PORT} ocupada (outro OpenOCD/GDB?). Não será "
                            "encerrado: libere a porta e repita.")
    free = shutil.disk_usage(DATA.parent if DATA.parent.exists() else ROOT).free
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
            out = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "desconhecida"


# ───────────────────────────── build e gate ─────────────────────────────

def build(fw: Firmware, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"{fw.name}.log").open("w") as out:
        # --fresh: configuração do zero, para que o ELF (inclusive a informação de
        # debug) dependa só das fontes e não do histórico da árvore build/<fw>.
        for argv in (["cmake", "--preset", fw.name, "--fresh"],
                     ["cmake", "--build", "--preset", fw.name]):
            r = subprocess.run(argv, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
            if r.returncode != 0:
                raise CampaignError(f"build de {fw.name} falhou (ver {log_dir / fw.name}.log)")
    text = (log_dir / f"{fw.name}.log").read_text()
    warnings = [line for line in text.splitlines() if "warning:" in line]
    if warnings:
        raise CampaignError(f"{fw.name}: warnings no build (política: zero): {warnings[:3]}")


USART1_RANGE = (0x40013800, 0x40013C00)


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
    sections = subprocess.run(["arm-none-eabi-size", "-A", str(elf)], capture_output=True,
                              text=True, check=True).stdout
    size = {m[1]: int(m[2]) for m in re.finditer(r"^(\S+)\s+(\d+)\s+(\d+)$", sections, re.M)}
    ram = size.get(".data", 0) + size.get(".bss", 0)
    flash = size.get(".isr_vector", 0) + size.get(".text", 0) + size.get(".rodata", 0) + size.get(".data", 0)
    reserved = size.get("._user_heap_stack", 0)
    if ram + reserved > 20 * 1024:
        raise CampaignError(f"{fw.name}: RAM {ram} B + pilha/heap {reserved} B > 20 KiB")
    # Literais do endereço da USART1 no código (.text/.rodata): só o C4 pode tê-los.
    dump = subprocess.run(["arm-none-eabi-objdump", "-s", "-j", ".text", "-j", ".rodata", str(elf)],
                          capture_output=True, text=True, check=True).stdout
    words = []
    for line in dump.splitlines():
        m = re.match(r"^ ([0-9a-f]{8}) ((?:[0-9a-f]{8} ?){1,4})", line)
        if m:
            words += [int.from_bytes(bytes.fromhex(w), "little") for w in m[2].split()]
    usart_literals = sorted({hex(w) for w in words if USART1_RANGE[0] <= w < USART1_RANGE[1]})
    if fw.name != "c4" and usart_literals:
        raise CampaignError(f"{fw.name}: referência à USART1 {usart_literals} — só o C4 pode "
                            "tocar PA9/PA10 (loopback permanente)")
    disasm = subprocess.run(["arm-none-eabi-objdump", "-d", str(elf)], capture_output=True,
                            text=True, check=True).stdout
    measure = re.search(r"<fid_measure>:\n(.*?)\n\n", disasm, re.S)
    if measure and "push\t{r3, r4, r5, r6, r7, lr}" not in measure[1]:
        raise CampaignError(f"{fw.name}: fid_measure não empilha 6 registros (AAPCS 8 bytes)")
    cc = json.loads((ROOT / "build" / fw.name / "compile_commands.json").read_text())
    flags = sorted({f for e in cc if e["file"].endswith(".c") and "/src/" in e["file"]
                    for f in e["command"].split() if f.startswith(("-O", "-g", "-std", "-mcpu"))})
    return {"elf_sha256": sha256_file(elf), "ram_bytes": ram, "flash_bytes": flash,
            "stack_heap_reserved": reserved, "usart1_literals": usart_literals,
            "compile_flags": flags, "symbols_checked": required}


# ───────────────────────────── plano ─────────────────────────────

def quantum_for(mips: int) -> str:
    """Menor quantum = k instruções com k·1000/mips ns inteiro (TimeInterval em ns)."""
    k = mips // math.gcd(mips, 1000)
    ns = k * 1000 // mips
    return f"{ns / 1e9:.9f}"


def make_plan(args, versions: dict, builds: dict, vendor: dict) -> dict:
    return {
        "schema": PLAN_SCHEMA,
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
        "collector": {"protocol": "reset → hbreak main → nonce → hbreak fid_complete → dump",
                      "debugger_attached_during_run": True, "sram_polling_during_run": False},
        "tools": versions,
        "vendor": vendor,
        "sources": source_digest(),
        "revision": vcs_revision(),
    }


def freeze_plan(paths: Paths, plan: dict, resume: bool) -> dict:
    """Grava o plano ou, na retomada, exige que nada que define o experimento mudou."""
    if paths.plan.exists():
        if not resume:
            raise CampaignError(f"campanha '{paths.name}' já existe; use --resume ou outro --name")
        old = json.loads(paths.plan.read_text())
        keys = ["schema", "board", "repetitions", "environments", "renode_nominal", "mode"]
        diff = [k for k in keys if old.get(k) != plan.get(k)]
        for name, fw in plan["firmwares"].items():
            o = old["firmwares"].get(name)
            if o is None or o["elf_sha256"] != fw["elf_sha256"] or o["planned_cases"] != fw["planned_cases"]:
                diff.append(f"firmware {name}")
        if old["calibration"]["rule"] != plan["calibration"]["rule"]:
            diff.append("regra de calibração")
        if diff:
            raise CampaignError(f"retomada incompatível com o plano congelado: {diff}")
        return old
    if resume:
        raise CampaignError(f"--resume: campanha '{paths.name}' não existe")
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.plan.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
    paths.plan.chmod(0o444)
    return plan


# ───────────────────────────── execução ─────────────────────────────

def next_attempt_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(p.name[4:]) for p in base.glob("run-*") if p.name[4:].isdigit()]
    d = base / f"run-{(max(taken) + 1 if taken else 1):03d}"
    d.mkdir()
    return d


def count_valid(base: Path) -> tuple[int, int]:
    valid = attempts = 0
    for rec in base.glob("run-*/run.json"):
        attempts += 1
        valid += json.loads(rec.read_text()).get("status") == "valid"
    return valid, attempts


def record_run(run_dir: Path, fw: Firmware, env: str, config: dict, collected, error: str | None) -> dict:
    rec = {"firmware": fw.name, "environment": env, "config": config,
           "attempt_dir": run_dir.name, "finished_utc": utc()}
    if collected is None:
        rec.update(status="infra_error", problems=[error or "?"])
    else:
        raw = run_dir / "snapshot.bin"
        rec.update(host_elapsed_s=round(collected.host_elapsed_s, 3), nonce=collected.nonce,
                   snapshot_sha256=hashlib.sha256(collected.snapshot).hexdigest(), **collected.extra)
        try:
            snap = abi.decode(collected.snapshot)
            problems = abi.run_checks(snap, fw.firmware_id, collected.nonce, fw.planned_cases)
            rec["header"] = {k: snap.header[k] for k in (
                "state", "error", "case_count", "word_count", "ticket_next", "dwt_start", "dwt_end",
                "observer_ticks", "log_ticks", "cpuid", "idcode", "flash_kb", "uid0", "uid1", "uid2",
                "rcc_cr", "rcc_cfgr", "flash_acr", "dbgmcu_cr", "aircr", "stack_free")}
            rec["trace_lost"] = snap.lost
        except abi.SnapshotError as exc:
            problems = [f"snapshot inválido: {exc}"]
        rec.update(status="valid" if not problems else "invalid", problems=problems)
        raw.chmod(0o444)
    path = run_dir / "run.json"
    path.write_text(json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False))
    path.chmod(0o444)
    return rec


def max_attempts(reps: int) -> int:
    return reps + max(3, reps // 5)


def run_hw(paths: Paths, plan: dict, fws: list[Firmware], log: Log) -> None:
    session = next_attempt_dir(paths.root / "hw" / "sessions")
    with targets.Bench(session) as bench:
        ident = bench.identify()
        (session / "identify.json").write_text(json.dumps(ident, indent=2))
        log(f"bancada: exemplar informado '{plan['board']}', identificação {ident}")
        for fw in fws:
            base = paths.env_dir("hw", fw.name)
            valid, attempts = count_valid(base)
            if valid >= plan["repetitions"]:
                log(f"hw/{fw.name}: {valid} runs válidos já coletados")
                continue
            bench.flash(fw.elf, session / f"flash-{fw.name}.log")
            log(f"hw/{fw.name}: gravado e verificado (sessão {session.name}); "
                f"coletando {plan['repetitions'] - valid} runs")
            while valid < plan["repetitions"] and attempts < max_attempts(plan["repetitions"]):
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
    slots: queue.Queue = queue.Queue()
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
            except Exception as exc:          # registra e segue: nunca derruba o lote
                error = f"{type(exc).__name__}: {exc}"
            return record_run(run_dir, fw, env, {"performance_in_mips": mips, "quantum_s": quantum},
                              collected, error)
        finally:
            slots.put(port_base)

    for fw in fws:
        base = paths.env_dir(env, fw.name)
        valid, attempts = count_valid(base)
        while valid < plan["repetitions"] and attempts < max_attempts(plan["repetitions"]):
            batch = min(plan["repetitions"] - valid, max_attempts(plan["repetitions"]) - attempts)
            dirs = [next_attempt_dir(base) for _ in range(batch)]
            attempts += batch
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for rec, d in zip(pool.map(lambda d: one(fw, d), dirs), dirs):
                    valid += rec["status"] == "valid"
                    if rec["status"] != "valid":
                        log(f"{env}/{fw.name}/{d.name}: {rec['status']}: {rec['problems'][:2]}")
        log(f"{env}/{fw.name}: {valid} válidos em {attempts} tentativas (MIPS {mips}, quantum {quantum} s)")


def run_instruction_traces(paths: Paths, plan: dict, envs: list[str], log: Log) -> None:
    fw = FIRMWARES["c1-timing"]
    for env in envs:
        out = paths.root / "instr" / ("hw" if env == "hw" else "renode")
        if (out / "instructions.json").exists():
            continue
        log(f"traço de instruções (stepi) do c1-timing em {env} — pode levar dezenas de minutos")
        try:
            if env == "hw":
                instr.trace_hw(fw.elf, out)
            else:
                instr.trace_renode(fw.elf, out)
            log(f"traço {env}: ok")
        except (TargetError, ValueError) as exc:
            log(f"traço {env}: FALHOU ({exc}); nível 'instrução' fica sem evidência")


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


# ───────────────────────────── fluxo principal ─────────────────────────────

EXIT_COMPLETE, EXIT_ERROR, EXIT_INCOMPLETE = 0, 1, 3


def run_campaign(args) -> int:
    """Executa a campanha inteira. Código de saída:
    0 = campanha completa (com ou sem divergências científicas);
    3 = infraestrutura incompleta (runs válidos < planejado, traço ausente...);
    1 = erro que impediu a campanha (pré-condição, build, plano incompatível)."""
    paths = Paths(args.name)
    paths.root.mkdir(parents=True, exist_ok=True)
    log = Log(paths.root / "campaign.log")
    fws = [FIRMWARES[n] for n in args.firmwares]
    with Lock(paths.root / ".lock", f"campanha '{args.name}'"), \
            Lock(DATA / ".hardware.lock" if "hw" in args.envs else paths.root / ".nohw.lock",
                 "a bancada (ST-Link)"):
        log(f"campanha '{args.name}' ({'piloto' if args.pilot else 'final'}), exemplar '{args.board}', "
            f"{args.reps} runs, firmwares {args.firmwares}, ambientes {args.envs}")
        versions = preflight(args.envs, log)
        vendor = vendor_integrity()
        builds = {}
        for fw in fws:
            build(fw, paths.root / "build")
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
        if args.instr and "c1-timing" in args.firmwares:
            run_instruction_traces(paths, plan,
                                   [e for e in ("hw", "renode") if e in args.envs], log)
        if args.calibration and "c1-timing" in args.firmwares:
            calibrate(paths, plan, args.jobs, log)
    from .analysis import analyze
    summary = analyze(paths.root, log)
    complete = summary["complete"]
    if args.instr and "c1-timing" in args.firmwares:
        traced = [e for e in ("hw", "renode") if e in args.envs]
        complete &= all((paths.root / "instr" / e / "instructions.json").exists() for e in traced)
    log(f"análise: {paths.analysis / 'report.md'}; campanha {'COMPLETA' if complete else 'INCOMPLETA'}")
    return EXIT_COMPLETE if complete else EXIT_INCOMPLETE


def calibrate(paths: Paths, plan: dict, jobs: int, log: Log) -> None:
    """Complemento do C1: aplica a regra pré-registrada e roda o Renode calibrado."""
    from statistics import median

    from .analysis import load_runs
    cal_path = paths.root / "calibration.json"
    if not cal_path.exists():
        runs = [r for r in load_runs(paths.root, plan) if r.valid and r.firmware == "c1-timing"]
        warm = {}
        for env in ("hw", "renode-nominal"):
            per_load = {}
            for load in CALIBRATION_RULE["training_loads"] + CALIBRATION_RULE["evaluation_loads"]:
                vals = [m.value for r in runs if r.env == env for m in r.eval.metrics
                        if m.case == f"{load}/{CALIBRATION_RULE['size']}" and m.name == "warm"]
                if vals:
                    per_load[load] = median(vals)
            warm[env] = per_load
        if any(ld not in warm["hw"] or ld not in warm["renode-nominal"]
               for ld in CALIBRATION_RULE["training_loads"]):
            log("calibração: dados de treino insuficientes (placa e Renode nominal); pulada")
            return
        result = choose_mips(warm["hw"], warm["renode-nominal"])
        cal = {"rule": CALIBRATION_RULE, "inputs_median_warm": warm, **result,
               "requested_mips": result["chosen_mips"], "computed_utc": utc()}
        cal_path.write_text(json.dumps(cal, indent=2, ensure_ascii=False))
        cal_path.chmod(0o444)
        log(f"calibração: MIPS escolhido {result['chosen_mips']} (erro médio de treino previsto "
            f"{result['training_mare']:.1%})")
    cal = json.loads(cal_path.read_text())
    run_renode(paths, plan, [FIRMWARES["c1-timing"]], "renode-calibrated", cal["chosen_mips"], jobs, log)
