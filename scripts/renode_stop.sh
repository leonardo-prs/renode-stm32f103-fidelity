#!/usr/bin/env bash
# renode_stop.sh — encerra o Renode iniciado por renode_start.sh (só esse PID).
set -euo pipefail
cd "$(dirname "$0")/.."
pid_file=build/renode.pid
if [[ -s "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    if [[ -r "/proc/$pid/cmdline" ]] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -qi renode; then
        kill "$pid" 2>/dev/null || true
        echo ">>> Renode (pid $pid) encerrado."
    fi
    rm -f "$pid_file"
fi
