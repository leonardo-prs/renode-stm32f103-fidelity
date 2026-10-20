#!/usr/bin/env bash
# c1.sh — CLI do C1 com o ambiente do projeto (entra no Nix se necessário).
#
#   scripts/c1.sh campaign --name piloto-01 --mode pilot --board "stm32f103c8-st-01"
#   scripts/c1.sh campaign --name final-01 --mode final --board "stm32f103c8-st-01" --pilot-from piloto-01
#   scripts/c1.sh analyze  --name final-01
#   scripts/c1.sh run      --env renode --preset c1-func --batch 0
#
# Saída de `campaign`: 0 = completa (divergências são resultado, não erro);
# 3 = evidência incompleta; 1 = erro de pré-condição, build, gate ou plano.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ $# -eq 0 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi
export PYTHONPATH="$root/scripts${PYTHONPATH:+:$PYTHONPATH}"
if ! command -v arm-none-eabi-gcc >/dev/null || ! command -v renode >/dev/null \
   || ! python3 -c "import matplotlib" 2>/dev/null; then
    exec nix develop "$root" --command python3 -B -m c1 "$@"
fi
exec python3 -B -m c1 "$@"
