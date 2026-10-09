#!/usr/bin/env bash
# renode_start.sh <firmware> — build + Renode headless com GDB em :3334 (debug no VS Code).
#
# Usa o MESMO script da campanha (renode/fidelity.resc). Encerra apenas uma
# instância anterior iniciada por este script (PID em build/renode.pid).
set -euo pipefail
fw="${1:?uso: renode_start.sh <c1-functional|c1-timing|c2|c3|c4>}"
cd "$(dirname "$0")/.."
mkdir -p build data/fidelity
exec 9>data/fidelity/.build.lock
flock -n 9 || { echo "ERRO: build em uso por outra execução." >&2; exit 1; }
cmake --workflow --preset "$fw"
"$(dirname "$0")/renode_stop.sh" >/dev/null
if python3 -c 'from scripts.fidelity.targets import port_in_use; raise SystemExit(not port_in_use(3334))'; then
    echo "ERRO: :3334 ocupada por outro servidor." >&2
    exit 1
fi
trap '"$(dirname "$0")/renode_stop.sh" >/dev/null' EXIT
nohup renode --disable-xwt --plain --port -1 --pid-file build/renode.pid \
    -e "\$elf=@build/$fw/firmware.elf; \$gdb_port=3334; i @renode/fidelity.resc" \
    > build/renode.log 2>&1 9>&- &
child_pid=$!
for _ in $(seq 1 120); do
    if [[ -s build/renode.pid && ! -s build/renode.owner ]]; then
        pid="$(<build/renode.pid)"
        if [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/stat" ]]; then
            proc_stat="$(</proc/$pid/stat)"
            read -r -a proc_fields <<< "${proc_stat##*) }"
            printf '%s %s\n' "$pid" "${proc_fields[19]}" > build/renode.owner
        fi
    fi
    if ! kill -0 "$child_pid" 2>/dev/null; then
        echo "ERRO: Renode terminou antes de abrir :3334." >&2
        tail -20 build/renode.log >&2
        exit 1
    fi
    if (exec 3<>/dev/tcp/127.0.0.1/3334) 2>/dev/null; then
        if [[ ! -s build/renode.owner ]]; then
            echo "ERRO: servidor sem identificação de processo próprio." >&2
            exit 1
        fi
        echo ">>> Renode pronto: GDB em :3334 (log build/renode.log)"
        trap - EXIT
        exit 0
    fi
    sleep 0.5
done
echo "ERRO: Renode não abriu :3334 em 60 s (o Renode não termina em erro de script):" >&2
tail -20 build/renode.log >&2
exit 1
