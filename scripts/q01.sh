#!/usr/bin/env bash
# q01.sh — CLI do caso Q-01 (verificação do observador externo, só Renode).
#
#   scripts/q01.sh run --name piloto-01 [--reps 2] [--no-build]
#   scripts/q01.sh analyze --name piloto-01
#
# Saída: 0 = veredito emitido; 3 = EVIDÊNCIA INVÁLIDA; 1 = erro de pré-condição.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ $# -eq 0 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi
export PYTHONPATH="$root/scripts${PYTHONPATH:+:$PYTHONPATH}"
if ! command -v arm-none-eabi-gcc >/dev/null || ! command -v renode >/dev/null; then
    exec nix develop "$root" --command python3 -B -m q01 "$@"
fi
exec python3 -B -m q01 "$@"
