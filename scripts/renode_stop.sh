#!/usr/bin/env bash
# renode_stop.sh — encerra o Renode iniciado por renode_start.sh (só esse PID).
set -euo pipefail
cd "$(dirname "$0")/.."
pid_file=build/renode.pid
owner_file=build/renode.owner
if [[ -s "$owner_file" ]]; then
    read -r pid started < "$owner_file"
    if [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/stat" ]]; then
        proc_stat="$(</proc/$pid/stat)"
        read -r -a proc_fields <<< "${proc_stat##*) }"
        cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
        if [[ "${proc_fields[19]}" == "$started" && "$cmdline" == *renode* &&
              "$cmdline" == *"--pid-file build/renode.pid"* ]]; then
        kill "$pid" 2>/dev/null || true
        echo ">>> Renode (pid $pid) encerrado."
        fi
    fi
fi
rm -f "$pid_file" "$owner_file"
