"""Campanha do C1: pré-verificação → build → gate → plano congelado → placa
→ Renode (dois perfis) → traço por stepi → análise.

Estrutura em data/c1/<campanha>/:
    plan.json                          plano congelado (ELFs, catálogos, lotes,
                                       repetições, perfis do Renode, exemplar)
    campaign.log                       linha do tempo (UTC do host)
    build/                             saída do build de cada preset
    hw/sessions/run-NNN/               OpenOCD e identificação do exemplar
    <ambiente>/<preset>/bNN/run-NNN/   um diretório por TENTATIVA (válida ou não)
    trace/<ambiente>/<preset>/bNN/     traço por stepi (nível de instrução)
    analysis/                          resultados, tabelas, figuras, relatório

Modos (material-base, cap. Repetições):
    pilot  só os lotes N1; 30 execuções por lote e ambiente; no c1-cycle,
           30 iterações quentes por execução (mais a fria);
    final  todos os lotes; 5 execuções; iterações quentes do c1-cycle
           decididas pela regra pré-registrada a partir de um piloto
           (--pilot-from), ou 1 se não houver piloto.

O que garante que um número pertence ao experimento declarado: o plano
congela os SHA-256 dos ELFs e os hashes dos catálogos (a retomada recusa
qualquer diferença); cada run.json registra o SHA-256 do ELF executado e do
snapshot, e o snapshot traz o nonce aleatório escrito pelo host naquele
run. Uma tentativa nunca é apagada.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import queue
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import abi, disasm, gen, targets, trace
from .cycle import R_MAX
from .presets import PRESETS, ROOT
from .targets import TargetError

DATA = ROOT / "data" / "c1"
PLAN_SCHEMA = 1
ENVS = ("hw", "renode", "renode-doc")
PRESET_ORDER = ("c1-layout", "c1-func", "c1-cycle")
SOURCE_DIRS = ("src/c1", "renode", "cmake", "scripts/c1")
SOURCE_FILES = ("CMakeLists.txt", "CMakePresets.json", "flake.nix", "flake.lock")
EXIT_COMPLETE, EXIT_ERROR, EXIT_INCOMPLETE = 0, 1, 3


class CampaignError(RuntimeError):
    """Pré-condição ou incompatibilidade que impede a campanha (exit 1)."""


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path: Path, value) -> None:
    """Grava um registro e o deixa somente-leitura (evidência finalizada)."""
    path.write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False, default=str))
    path.chmod(0o444)


def read_json(path: Path):
    return json.loads(Path(path).read_text())


class Log:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.lock = path, threading.Lock()

    def __call__(self, msg: str) -> None:
        line = f"{utc()}  {msg}"
        with self.lock:
            print(line, flush=True)
            with self.path.open("a") as f:
                f.write(line + "\n")


class Lock:
    """Lock exclusivo por arquivo: impede duas campanhas no mesmo ST-Link/árvore."""

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


# ───────────────────────────── pré-verificação, build, gate ─────────────────────────────

def preflight(envs, log: Log) -> dict:
    tools = ["cmake", "ninja", "arm-none-eabi-gcc", "arm-none-eabi-gdb", "arm-none-eabi-nm",
             "arm-none-eabi-objdump"]
    if "hw" in envs:
        tools.append("openocd")
    if any(e.startswith("renode") for e in envs):
        tools.append("renode")
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        raise CampaignError(f"ferramentas ausentes no PATH: {missing} (use `nix develop` ou "
                            "scripts/c1.sh)")
    if shutil.disk_usage(ROOT).free < 2 * 1024**3:
        raise CampaignError("pouco espaço em disco (< 2 GiB)")
    versions = targets.tool_versions()
    log(f"pré-verificação ok; ferramentas: {versions}")
    return versions


def vendor_integrity() -> dict:
    text = (ROOT / "vendor" / "README.md").read_text()
    entries = re.findall(r"^([0-9a-f]{64})\s+\./(\S+)$", text, re.M)
    bad = [p for h, p in entries if not (ROOT / "vendor" / p).is_file()
           or sha256_file(ROOT / "vendor" / p) != h]
    if not entries or bad:
        raise CampaignError(f"vendor/ alterado ou sem tabela SHA-256: {bad[:5]}")
    return {"files": len(entries), "ok": True}


def source_digest() -> dict:
    files = []
    for d in SOURCE_DIRS:
        files += [p for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [ROOT / f for f in SOURCE_FILES if (ROOT / f).is_file()]
    per_file = {str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(files)}
    return {"sha256": hashlib.sha256(json.dumps(per_file, sort_keys=True).encode()).hexdigest(),
            "files": len(per_file)}


def vcs_revision() -> str:
    try:
        out = targets.run_command(["jj", "log", "-r", "@-", "--no-graph", "--ignore-working-copy",
                                   "-T", 'change_id.short() ++ " " ++ commit_id.short()'],
                                  timeout_s=10, check=False)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except TargetError:
        pass
    return "desconhecida"


def build(preset: str, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{preset}.log"
    with log.open("w") as out:
        # --fresh: configuração do zero; o ELF depende só das fontes.
        for argv in (["cmake", "--preset", preset, "--fresh"], ["cmake", "--build", "--preset", preset]):
            r = targets.run_command(argv, stdout=out, stderr=subprocess.STDOUT, timeout_s=300,
                                    check=False)
            if r.returncode:
                raise CampaignError(f"build de {preset} falhou (ver {log})")
    warnings = [line for line in log.read_text().splitlines() if "warning:" in line]
    if warnings:
        raise CampaignError(f"{preset}: warnings no build (política: zero): {warnings[:3]}")


USART1 = (0x4001_3800, 0x4001_3C00)
LOADED = (".isr_vector", ".text", ".rodata", ".data", ".ramfunc")


def usart_literals(elf: Path, sections: list[str]) -> list[str]:
    """Palavras no intervalo da USART1 nas seções carregadas e pares MOVW/MOVT
    que montam um endereço nele."""
    cmd = ["arm-none-eabi-objdump", "-s"]
    for s in sections:
        cmd += ["-j", s]
    words = []
    for line in targets.run_command(cmd + [str(elf)]).stdout.splitlines():
        m = re.match(r"^ ([0-9a-f]{8}) ((?:[0-9a-f]{8} ?){1,4})", line)
        if m:
            words += [int.from_bytes(bytes.fromhex(w), "little") for w in m[2].split()]
    found = {hex(w) for w in words if USART1[0] <= w < USART1[1]}
    low: dict[str, int] = {}
    for addr, d in sorted(disasm.disassemble(elf).items()):
        m = re.match(r"(r\d+|ip|lr|sl|fp), #(0x[0-9a-f]+|\d+)$", d.operands)
        if not m:
            continue
        imm = int(m[2], 0)
        if d.mnemonic.startswith("movw"):
            low[m[1]] = imm
        elif d.mnemonic.startswith("movt") and m[1] in low:
            full = (imm << 16) | low.pop(m[1])
            if USART1[0] <= full < USART1[1]:
                found.add(f"{full:#x} (movw/movt em {addr:#x})")
    return sorted(found)


def gate(preset: str) -> dict:
    """Verificações estáticas do ELF: disassembly × catálogo, USART1, memória."""
    elf = PRESETS[preset].elf
    problems = disasm.gate(preset, elf)
    if problems:
        raise CampaignError(f"{preset}: gate de disassembly recusou o ELF: {problems[:4]}")
    size = targets.run_command(["arm-none-eabi-size", "-A", str(elf)]).stdout
    sec = {m[1]: int(m[2]) for m in re.finditer(r"^(\S+)\s+(\d+)\s+(\d+)$", size, re.M)}
    # Fio PA9→PA10 permanente: só o C4 pode referenciar a USART1 — nem por
    # literal (em qualquer seção carregada da flash) nem por MOVW/MOVT.
    usart = usart_literals(elf, [s for s in LOADED if sec.get(s)])
    if usart:
        raise CampaignError(f"{preset}: endereço da USART1 {usart} (só o C4 toca PA9/PA10)")
    g = gen.generate(preset)
    return {"elf_sha256": sha256_file(elf), "catalog_hash": f"0x{g.catalog_hash:08x}",
            "flash_bytes": sum(sec.get(s, 0) for s in (".isr_vector", ".text", ".rodata", ".data",
                                                       ".ramfunc")),
            "ram_bytes": sum(sec.get(s, 0) for s in (".ram_vectors", ".data", ".ramfunc", ".bss",
                                                     ".noinit", ".psp")),
            "gate_points": len(disasm.func_points(g.forms)) if preset == "c1-func" else None}


# ───────────────────────────── plano ─────────────────────────────

def batch_ids(preset: str, mode: str) -> list[int]:
    g = gen.generate(preset)
    return [i for i, b in enumerate(g.batches) if mode == "final" or b.level == "N1"]


def kalibera_decision(pilot: str | None) -> dict:
    """Regra pré-registrada (material-base, cap. Repetições)."""
    if pilot is None:
        return {"from_pilot": None, "rule": 1, "iters": 1, "executions": 5,
                "why": "sem piloto: regra 1 por padrão (o relatório marca a ausência do piloto)"}
    path = DATA / pilot / "analysis" / "kalibera.json"
    if not path.exists():
        raise CampaignError(f"piloto '{pilot}' sem analysis/kalibera.json (rode o piloto e analise)")
    k = read_json(path)
    return {"from_pilot": pilot, **k["campaign_decision"]}


def make_plan(args, versions, builds, vendor, identity) -> dict:
    mode = args.mode
    decision = kalibera_decision(args.pilot_from) if mode == "final" else {
        "rule": "piloto", "iters": 30, "executions": 30, "from_pilot": None,
        "why": "piloto: 30 execuções × 30 iterações (Kalibera & Jones §9.1)"}
    reps = {"c1-layout": decision["executions"] if mode == "final" else 30,
            "c1-func": decision["executions"] if mode == "final" else 30,
            "c1-cycle": decision["executions"]}
    if args.reps:
        reps = dict.fromkeys(reps, args.reps)
    return {
        "schema": PLAN_SCHEMA, "abi_version": abi.ABI_VERSION, "campaign": args.name,
        "created_utc": utc(), "mode": mode, "board": args.board, "board_note": args.board_note,
        "identity": identity, "environments": list(args.envs),
        "repetitions": reps, "cycle_iters": decision["iters"] if args.iters is None else args.iters,
        "kalibera": decision,
        "presets": {p: {**builds[p], "batches": batch_ids(p, mode)} for p in PRESET_ORDER},
        "renode": {"version": versions.get("renode"), "mips": targets.NOMINAL_MIPS,
                   "quantum_s": targets.QUANTUM_S, "script_sha256": sha256_file(targets.RESC),
                   "profiles": {k: {"repl": str(v.relative_to(ROOT)), "sha256": sha256_file(v)}
                                for k, v in targets.PROFILES.items()},
                   "fresh_process_per_run": True},
        "trace": {"enabled": bool(args.trace)},
        "collector": {"protocol": "reset → hbreak *main → bloco do host → hbreak c1_complete → dump",
                      "sram_access_during_run": False},
        "tools": versions, "vendor": vendor, "sources": source_digest(), "revision": vcs_revision(),
    }


FROZEN = ("schema", "abi_version", "mode", "board", "environments", "repetitions", "cycle_iters",
          "renode", "trace")


def freeze_plan(root: Path, plan: dict, resume: bool) -> dict:
    path = root / "plan.json"
    if path.exists():
        if not resume:
            raise CampaignError(f"campanha '{root.name}' já existe; use --resume ou outro --name")
        old = read_json(path)
        diff = [k for k in FROZEN if old.get(k) != plan.get(k)]
        for p, info in plan["presets"].items():
            o = old["presets"].get(p, {})
            if (o.get("elf_sha256"), o.get("catalog_hash"), o.get("batches")) != \
                    (info["elf_sha256"], info["catalog_hash"], info["batches"]):
                diff.append(f"preset {p} (ELF, catálogo ou lotes)")
        if diff:
            raise CampaignError(f"retomada incompatível com o plano congelado: {diff}")
        return old
    if resume:
        raise CampaignError(f"--resume: campanha '{root.name}' não existe")
    root.mkdir(parents=True, exist_ok=True)
    save_json(path, plan)
    return plan


# ───────────────────────────── runs ─────────────────────────────

def run_dir_base(root: Path, env: str, preset: str, batch: int) -> Path:
    return root / env / preset / f"b{batch:02d}"


def next_attempt(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(p.name[4:]) for p in base.glob("run-*") if p.name[4:].isdigit()]
    d = base / f"run-{(max(taken) + 1 if taken else 1):03d}"
    d.mkdir()
    return d


def count(base: Path, elf_sha: str) -> tuple[int, int]:
    """(observações válidas do ELF congelado, tentativas)."""
    valid = attempts = 0
    for d in sorted(base.glob("run-*")):
        attempts += 1
        rec = d / "run.json"
        if rec.exists():
            r = read_json(rec)
            valid += r.get("status") in ("valid", "simulator_abort") and r.get("elf_sha256") == elf_sha
    return valid, attempts


def host_for(preset: str, batch: int, iters: int) -> targets.HostBlock:
    return targets.HostBlock(batch=batch, iters=iters if preset == "c1-cycle" else 0,
                             reboot=preset == "c1-layout" and batch == 1)


def timeout_for(preset: str, batch: int) -> float:
    if preset == "c1-layout" and batch == 1:
        return 45        # o perfil renode fica preso em 0x0 depois do reset
    return 180 if preset == "c1-cycle" else 90


def record(run_dir: Path, preset: str, env: str, batch: int, collected, error, abort=None) -> dict:
    p = PRESETS[preset]
    g = gen.generate(preset)
    rec = {"preset": preset, "environment": env, "batch": batch, "attempt": run_dir.name,
           "finished_utc": utc(), "elf_sha256": sha256_file(p.elf)}
    if abort is not None:
        rec.update(status="simulator_abort", problems=[str(abort)], abort_pc=abort.pc)
    elif collected is None:
        rec.update(status="infra_error", problems=[error or "?"])
    else:
        raw = run_dir / "snapshot.bin"
        raw.write_bytes(collected.snapshot)
        raw.chmod(0o444)
        rec.update(nonce=collected.host.nonce, host_elapsed_s=round(collected.host_elapsed_s, 3),
                   snapshot_sha256=hashlib.sha256(collected.snapshot).hexdigest(), **collected.extra)
        try:
            snap = abi.decode(collected.snapshot)
            problems = abi.run_checks(snap, p.preset_id, g.catalog_hash, collected.host.nonce,
                                      collected.host.batch)
        except abi.SnapshotError as exc:
            problems = [f"snapshot inválido: {exc}"]
        rec.update(status="valid" if not problems else "invalid", problems=problems)
    save_json(run_dir / "run.json", rec)
    return rec


def max_attempts(reps: int) -> int:
    return reps + max(3, reps // 5)


def run_hw(root: Path, plan: dict, log: Log) -> None:
    session = next_attempt(root / "hw" / "sessions")
    with targets.Bench(session) as bench:
        ident = bench.identify(PRESETS["c1-func"].elf)
        save_json(session / "identify.json", ident)
        key = tuple(ident[k] for k in targets.IDENTITY_KEYS)
        if key != tuple(plan["identity"][k] for k in targets.IDENTITY_KEYS):
            raise CampaignError(f"o exemplar conectado não é o do plano: {ident}")
        for preset in PRESET_ORDER:
            p, info = PRESETS[preset], plan["presets"][preset]
            reps = plan["repetitions"][preset]
            pending = [b for b in info["batches"]
                       if count(run_dir_base(root, "hw", preset, b), info["elf_sha256"])[0] < reps]
            if not pending:
                continue
            bench.flash(p.elf, session / f"flash-{preset}.log")
            log(f"hw/{preset}: gravado e verificado; {len(pending)} lotes × {reps} execuções")
            for k in range(reps):                      # execução k de cada lote, em sequência
                for b in pending:
                    base = run_dir_base(root, "hw", preset, b)
                    valid, attempts = count(base, info["elf_sha256"])
                    while valid <= k and valid < reps and attempts < max_attempts(reps):
                        d = next_attempt(base)
                        attempts += 1
                        col, err = None, None
                        try:
                            col = bench.run(p.elf, d, host_for(preset, b, plan["cycle_iters"]),
                                            timeout_for(preset, b))
                        except TargetError as exc:
                            err = str(exc)
                        rec = record(d, preset, "hw", b, col, err)
                        valid += rec["status"] == "valid"
                        if rec["status"] != "valid":
                            log(f"hw/{preset}/b{b:02d}/{d.name}: {rec['status']}: {rec['problems'][:2]}")
            log(f"hw/{preset}: concluído")


def run_renode(root: Path, plan: dict, env: str, jobs: int, log: Log) -> None:
    slots: queue.Queue = queue.Queue()
    for k in range(jobs):
        slots.put(targets.RENODE_PORT_BASE + 20 * k)

    def one(preset: str, b: int, d: Path) -> dict:
        port = slots.get()
        try:
            col, err, abort = None, None, None
            try:
                col = targets.run_renode(PRESETS[preset].elf, d, host_for(preset, b, plan["cycle_iters"]),
                                         timeout_for(preset, b), profile=env, port_base=port)
            except targets.SimulatorAbort as exc:
                abort = exc
            except TargetError as exc:
                err = str(exc)
            return record(d, preset, env, b, col, err, abort)
        finally:
            slots.put(port)

    for preset in PRESET_ORDER:
        info, reps = plan["presets"][preset], plan["repetitions"][preset]
        while True:
            work = []
            for b in info["batches"]:
                base = run_dir_base(root, env, preset, b)
                valid, attempts = count(base, info["elf_sha256"])
                n = min(reps - valid, max_attempts(reps) - attempts)
                work += [(b, next_attempt(base)) for _ in range(max(0, n))]
            if not work:
                break
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for rec in pool.map(lambda w: one(preset, *w), work):
                    if rec["status"] not in ("valid", "simulator_abort"):
                        log(f"{env}/{preset}/b{rec['batch']:02d}/{rec['attempt']}: {rec['status']}: "
                            f"{rec['problems'][:2]}")
        log(f"{env}/{preset}: concluído")


def aborts_only(root: Path, env: str, preset: str, batch: int) -> bool:
    """Lote em que todo run do ambiente terminou com o simulador abortado: o
    traço não acrescenta nada (e o GDB ficaria esperando a máquina parada)."""
    recs = [read_json(p) for p in (root / env / preset / f"b{batch:02d}").glob("run-*/run.json")]
    return bool(recs) and all(r["status"] == "simulator_abort" for r in recs)


def run_traces(root: Path, plan: dict, envs, log: Log) -> None:
    """Traço por stepi, uma vez por ambiente, lote e preset (c1-func, c1-cycle)."""
    for env in envs:
        for preset in ("c1-func", "c1-cycle"):
            info = plan["presets"][preset]
            todo = [b for b in info["batches"]
                    if not (root / "trace" / env / preset / f"b{b:02d}" / "trace.json").exists()
                    and not aborts_only(root, env, preset, b)]
            if not todo:
                continue
            log(f"traço {env}/{preset}: {len(todo)} lotes (stepi)")
            bench = None
            try:
                if env == "hw":
                    try:
                        bench = targets.Bench(next_attempt(root / "hw" / "sessions")).__enter__()
                        bench.flash(PRESETS[preset].elf, bench.log_dir / f"flash-{preset}.log")
                    except TargetError as exc:
                        log(f"BANCADA INDISPONÍVEL no traço {preset}: {exc} — traço da placa incompleto")
                        continue
                for b in todo:
                    out = root / "trace" / env / preset / f"b{b:02d}"
                    host = targets.HostBlock(batch=b, flags=abi.HOST_TRACE)
                    try:
                        if env == "hw":
                            calls = trace.trace_hw(bench, PRESETS[preset].elf, out, host, 3600)
                        else:
                            calls = trace.trace_renode(PRESETS[preset].elf, out, host, env, 900)
                    except TargetError as exc:
                        out.mkdir(parents=True, exist_ok=True)
                        save_json(out / f"trace-error-{utc().replace(':', '')}.json",
                                  {"error": str(exc), "utc": utc()})
                        log(f"traço {env}/{preset}/b{b:02d}: sem evidência ({exc})")
                        continue
                    save_json(out / "trace.json", {"elf_sha256": info["elf_sha256"], "calls": calls})
            finally:
                if bench is not None:
                    bench.__exit__()


# ───────────────────────────── fluxo principal ─────────────────────────────

def run_campaign(args) -> int:
    root = DATA / args.name
    root.mkdir(parents=True, exist_ok=True)
    if args.iters is not None and not 0 <= args.iters <= R_MAX:
        raise CampaignError(f"--iters {args.iters}: o firmware aceita 0..{R_MAX} (C1_R_MAX)")
    with Lock(root / ".lock", f"campanha '{args.name}'"), \
            Lock(DATA / ".build.lock", "a árvore build/"), \
            Lock(DATA / ".hardware.lock", "a bancada (ST-Link)"):
        log = Log(root / "campaign.log")
        log(f"campanha '{args.name}' ({args.mode}), exemplar '{args.board}', ambientes {args.envs}")
        versions = preflight(args.envs, log)
        vendor = vendor_integrity()
        builds = {}
        for preset in PRESET_ORDER:
            build(preset, root / "build")
            builds[preset] = gate(preset)
            log(f"build+gate {preset}: ELF {builds[preset]['elf_sha256'][:12]}…, catálogo "
                f"{builds[preset]['catalog_hash']}")
        identity = None
        if "hw" in args.envs:
            with targets.Bench(next_attempt(root / "hw" / "sessions")) as bench:
                identity = bench.identify(PRESETS["c1-func"].elf)
        elif (root / "plan.json").exists():
            identity = read_json(root / "plan.json")["identity"]
        plan = freeze_plan(root, make_plan(args, versions, builds, vendor, identity), args.resume)
        # O ELF executado fica com a campanha (o plano já conferiu o SHA-256 na
        # retomada): a análise resolve símbolos e disassembly nele.
        for preset in PRESET_ORDER:
            frozen = root / "build" / f"{preset}.elf"
            if not frozen.exists() or sha256_file(frozen) != plan["presets"][preset]["elf_sha256"]:
                shutil.copyfile(PRESETS[preset].elf, frozen)
        if "hw" in args.envs:
            try:
                run_hw(root, plan, log)
            except TargetError as exc:
                log(f"BANCADA INDISPONÍVEL: {exc} — etapa da placa incompleta")
        for env in args.envs:
            if env.startswith("renode"):
                run_renode(root, plan, env, args.jobs, log)
        if plan["trace"]["enabled"]:
            run_traces(root, plan, args.envs, log)
        from .analysis import analyze
        summary = analyze(root, log)
    log(f"análise: {root / 'analysis' / 'report.md'}; campanha "
        f"{'COMPLETA' if summary['complete'] else 'INCOMPLETA'}")
    return EXIT_COMPLETE if summary["complete"] else EXIT_INCOMPLETE
