#!/usr/bin/env bash
# renode_start.sh <firmware> — build + Renode headless com GDB em :3334 (debug no VS Code).
#
# Usa o MESMO script da campanha (renode/fidelity.resc). Encerra apenas uma
# instância anterior iniciada por este script (PID em build/renode.pid).
set -euo pipefail
fw="${1:?uso: renode_start.sh <c1-functional|c1-timing|c2|c3|c4>}"
cd "$(dirname "$0")/.."
cmake --workflow --preset "$fw"
"$(dirname "$0")/renode_stop.sh" >/dev/null
nohup renode --disable-xwt --plain --port -1 --pid-file build/renode.pid \
    -e "\$elf=@build/$fw/firmware.elf; \$gdb_port=3334; i @renode/fidelity.resc" \
    > build/renode.log 2>&1 &
for _ in $(seq 1 120); do
    if (exec 3<>/dev/tcp/127.0.0.1/3334) 2>/dev/null; then
        echo ">>> Renode pronto: GDB em :3334 (log build/renode.log)"
        exit 0
    fi
    sleep 0.5
done
echo "ERRO: Renode não abriu :3334 em 60 s (o Renode não termina em erro de script):" >&2
tail -20 build/renode.log >&2
exit 1
