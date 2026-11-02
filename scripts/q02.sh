#!/usr/bin/env bash
# q02.sh — CLI do caso Q-02 (instrumentos genéricos do Renode, só Renode).
#
#   scripts/q02.sh check                                # build do zero + gate
#   scripts/q02.sh run --name piloto-01 [--reps 2] [--no-build]
#   scripts/q02.sh analyze --name piloto-01
#
# Saída: 0 = veredito emitido; 3 = EVIDÊNCIA INVÁLIDA; 1 = erro de pré-condição.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ $# -eq 0 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi
export PYTHONPATH="$root/scripts${PYTHONPATH:+:$PYTHONPATH}"
if ! command -v arm-none-eabi-gcc >/dev/null || ! command -v renode >/dev/null; then
    exec nix develop "$root" --command python3 -B -m q02 "$@"
fi
exec python3 -B -m q02 "$@"
