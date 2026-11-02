#!/usr/bin/env bash
# c2.sh — CLI do C2 #oD (interrupções; preset c2-od, só Renode, perfil R1).
#
#   scripts/c2.sh check                                   # build do zero + gate
#   scripts/c2.sh run --case C2-09 --name piloto-01 [--reps 2] [--no-build]
#   scripts/c2.sh analyze --case C2-09 --name piloto-01
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
    exec nix develop "$root" --command python3 -B -m c2 "$@"
fi
exec python3 -B -m c2 "$@"
