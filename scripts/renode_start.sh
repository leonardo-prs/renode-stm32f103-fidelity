#!/usr/bin/env bash
# renode_start.sh <cenario> [--build] — sobe Renode headless com GDB em :3334.
#
# Usado como preLaunchTask dos configs Renode em .vscode/launch.json. O
# editor não roda tasks com o env do direnv, e tasks do tipo "isBackground" não têm
# sinalização confiável — então este script:
#   1. (opcional, --build) faz `scripts/scenario_build.sh <cenario>` (configure
#      idempotente + build via preset per-cenário — ver CMakePresets.json);
#   2. mata instância Renode anterior (best-effort, via PID em build/renode.pid);
#   3. sobe `renode --disable-xwt` em background (nohup) executando o .resc;
#   4. bloqueia até o GDB :3334 aceitar conexão (poll /dev/tcp, timeout 60 s).
#
# O .resc carrega o ELF (`sysbus LoadELF @build/<cenario>/firmware.elf`),
# a plataforma (renode/stm32f103_hsi8.repl) e sobe o GDB server em :3334.
# Detalhes do mapeamento cN: ver renode/PLAN.md.
#
# Uso: scripts/renode_start.sh <sandbox|c1|c2|c2busy|c3|c4|echo> [--build]
set -euo pipefail

usage() { echo "uso: $0 <cenario> [--build]" >&2; exit 2; }

scenario="${1:-}"
[[ -n "$scenario" ]] || usage
build_first=false
[[ "${2:-}" == "--build" ]] && build_first=true

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [[ "$build_first" == true ]]; then
    # c4.resc carrega TAMBÉM o peer (build/echo/firmware.elf) — constrói o
    # echo ANTES do c4 para que o .clangd gerado fique apontando para o
    # cenário debugado (o c4).
    if [[ "$scenario" == "c4" && ! -f "build/echo/firmware.elf" ]]; then
        echo ">>> C4 precisa do peer: scenario_build.sh echo (dependência do c4.resc)"
        "$(dirname "$0")/scenario_build.sh" "echo"
    fi
    echo ">>> CMake: scenario_build.sh ${scenario} (configure + build, preset per-cenário)"
    "$(dirname "$0")/scenario_build.sh" "${scenario}"
fi

pid_file="build/renode.pid"
log_file="build/renode.log"

# ── Mata instância anterior, se houver (best-effort) ────────────────────────
if [[ -s "$pid_file" ]]; then
    old_pid="$(<"$pid_file")"
    if [[ -r "/proc/$old_pid/cmdline" ]] && tr '\0' ' ' < "/proc/$old_pid/cmdline" | grep -qi renode; then
        echo ">>> Renode anterior (pid $old_pid) ainda ativo — encerrando."
        kill "$old_pid" 2>/dev/null || true
        for _ in {1..20}; do
            [[ -r "/proc/$old_pid" ]] || break
            sleep 0.25
        done
        kill -9 "$old_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
fi

# ── Sanidade: ELF e .resc precisam existir ──────────────────────────────────
if [[ ! -f "build/${scenario}/firmware.elf" ]]; then
    echo "ERRO: build/${scenario}/firmware.elf não existe — rode o build antes." >&2
    exit 1
fi
if [[ "$scenario" == "c4" && ! -f "build/echo/firmware.elf" ]]; then
    echo "ERRO: c4.resc carrega o peer build/echo/firmware.elf — rode" >&2
    echo "      scripts/scenario_build.sh echo (ou renode_start.sh c4 --build)." >&2
    exit 1
fi
if [[ ! -f "renode/${scenario}.resc" ]]; then
    echo "ERRO: renode/${scenario}.resc não existe." >&2
    exit 1
fi

# ── Sobe Renode em background ───────────────────────────────────────────────
echo ">>> Renode: renode/${scenario}.resc (log: ${log_file})"
nohup renode --disable-xwt --pid-file "$pid_file" -P 6512 \
    -e "s @renode/${scenario}.resc" > "$log_file" 2>&1 &

# ── Aguarda o GDB :3334 abrir (Renode levanta JVM; timeout 60 s) ────────────
for _ in $(seq 1 120); do
    if (exec 3<>/dev/tcp/localhost/3334) 2>/dev/null; then
        exec 3>&- || true
        echo ">>> Renode GDB pronto em :3334 (pid: $(cat "$pid_file" 2>/dev/null || echo '?'))"
        exit 0
    fi
    # Aborta cedo se o processo já morreu
    if [[ -s "$pid_file" ]] && ! kill -0 "$(<"$pid_file")" 2>/dev/null; then
        echo "ERRO: Renode morreu durante o startup. Log:" >&2
        tail -20 "$log_file" >&2
        exit 1
    fi
    sleep 0.5
done
echo "ERRO: Renode GDB :3334 não respondeu em 60 s. Log:" >&2
tail -20 "$log_file" >&2
exit 1
