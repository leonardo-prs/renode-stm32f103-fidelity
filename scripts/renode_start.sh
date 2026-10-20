#!/usr/bin/env bash
# renode_start.sh <preset> [renode|renode-doc] — build + Renode headless com GDB
# em :3334 (depuração no VS Code), com o MESMO script e as mesmas plataformas da
# campanha (renode/c1.resc). Encerra só uma instância anterior iniciada por
# este script (PID em build/renode.pid).
set -euo pipefail
fw="${1:?uso: renode_start.sh <c1-func|c1-layout|c1-cycle> [renode|renode-doc]}"
profile="${2:-renode}"
case "$profile" in
    renode) repl=renode/stm32f103_hsi8.repl ;;
    renode-doc) repl=renode/c1_doc.repl ;;
    *) echo "perfil desconhecido: $profile" >&2; exit 1 ;;
esac
cd "$(dirname "$0")/.."
mkdir -p build data/c1
exec 9>data/c1/.build.lock
flock -n 9 || { echo "ERRO: build em uso por outra execução (campanha?)." >&2; exit 1; }
cmake --workflow --preset "$fw"
"$(dirname "$0")/renode_stop.sh" >/dev/null
if (exec 3<>/dev/tcp/127.0.0.1/3334) 2>/dev/null; then
    echo "ERRO: :3334 ocupada por outro servidor." >&2
    exit 1
fi
trap '"$(dirname "$0")/renode_stop.sh" >/dev/null' EXIT
nohup renode --disable-xwt --plain --port -1 --pid-file build/renode.pid \
    -e "\$elf=@build/$fw/firmware.elf; \$gdb_port=3334; \$platform=@$repl; i @renode/c1.resc" \
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
        echo ">>> Renode ($profile) pronto: GDB em :3334 (log build/renode.log)"
        trap - EXIT
        exit 0
    fi
    sleep 0.5
done
echo "ERRO: Renode não abriu :3334 em 60 s (o Renode não termina em erro de script):" >&2
tail -20 build/renode.log >&2
exit 1
