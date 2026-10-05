#!/usr/bin/env bash
# renode_stop.sh — encerra a instância Renode iniciada por renode_start.sh.
# Usado como postDebugTask nos configs Renode de .vscode/launch.json.
# Best-effort: sem instância ativa, sai 0 silenciosamente.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

pid_file="build/renode.pid"
if [[ -s "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    if [[ -r "/proc/$pid/cmdline" ]] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -qi renode; then
        kill "$pid" 2>/dev/null || true
        for _ in {1..20}; do
            [[ -r "/proc/$pid" ]] || break
            sleep 0.25
        done
        kill -9 "$pid" 2>/dev/null || true
        echo ">>> Renode (pid $pid) encerrado."
    fi
    rm -f "$pid_file"
else
    echo ">>> Nenhuma instância Renode registrada (${pid_file} ausente/vazio)."
fi
