#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# scripts/scenario_build.sh — configure (idempotente) + build de um cenário
# via CMakePresets.json PER-CENÁRIO.
#
# Uso:  scripts/scenario_build.sh <cenario>   (sandbox|c1|c2|c2busy|c3|c4|echo)
#
# Esquema: um cenário = uma árvore = um preset. binaryDir = build/<cenario>;
# o ELF sai direto em build/<cenario>/firmware.elf (sem cópia sincronizada) —
# é o path consumido por .resc, launch.json, scripts e gdb.
#
# O configure roda sempre (idempotente: cache existente é re-aproveitado e o
# .clangd é regerado apontando para esta árvore). Requer as ferramentas do
# flake (cmake/ninja) — rode dentro do direnv/nix-develop. A partir das tasks
# do VS Code use via scripts/direnv_exec.sh (garante o nix no PATH).
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

scenario="${1:?uso: scenario_build.sh <cenario>}"
cd "$(dirname "$0")/.."

cmake --preset "${scenario}"
cmake --build --preset "${scenario}"
