#!/usr/bin/env bash
# campaign.sh — campanha completa (placa + Renode + análise) em UM comando.
#
#   scripts/campaign.sh --name final-genuino-01 --board "stm32f103c8-genuino-lab-01"
#
# Entra no ambiente Nix do projeto (se ainda não estiver nele) e delega tudo a
# scripts/fidelity.py. Parâmetros principais (todos repassados):
#   --name N          identidade da campanha (data/fidelity/N/)          [obrigatório]
#   --board B         identidade física do exemplar (etiqueta do lab)   [obrigatório]
#   --board-note T    observação (marcação do chip, lote, cabo...)
#   --reps R          runs por firmware e ambiente (padrão 50; piloto 10)
#   --pilot           modo piloto
#   --firmwares ...   subconjunto (c1-functional c1-timing c2 c3 c4)
#   --env ...         hw e/ou renode (padrão: os dois)
#   --calibration     complemento do C1 (MIPS calibrado; nunca usado em C2–C4)
#   --no-instr        pula o traço por stepi do C1 (≈ 25 min na placa)
#   --resume          retoma a campanha com o MESMO plano (hashes, exemplar...)
#   --jobs J          processos Renode em paralelo (padrão 4)
# Saída: 0 = campanha completa (divergências científicas não são erro);
#        3 = infraestrutura incompleta; 1 = erro de pré-condição/build/plano.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -eq 0 ]]; then
    sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi
if ! command -v arm-none-eabi-gcc >/dev/null || ! command -v renode >/dev/null \
   || ! python3 -c "import numpy, matplotlib" 2>/dev/null; then
    exec nix develop "$root" --command python3 scripts/fidelity.py campaign "$@"
fi
exec python3 scripts/fidelity.py campaign "$@"
