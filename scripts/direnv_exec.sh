#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# scripts/direnv_exec.sh — `direnv exec` com garantia de `nix` no PATH.
#
# Para que servem os argumentos: mesmas posições do `direnv exec` —
#   scripts/direnv_exec.sh . <comando> [args...]
# O "." é o cwd do projeto (as tasks do VS Code rodam na raiz do workspace).
#
# Motivo: as tasks são lançadas pelo processo do editor (não-shell de login),
# então o /etc/profile.d/nix.sh (que adiciona
# /nix/var/nix/profiles/default/bin) não roda. Sem o `nix`, o hook
# `use flake` do .envrc falha com "nix: command not found" e a task morre
# com exit 127 (cmake: command not found), abortando o preLaunchTask dos
# configs de debug do Renode. O direnv (/usr/bin/direnv) é do sistema e por
# isso é encontrado; só o `nix` depende do profile do daemon nix. Se o
# editor for aberto de um terminal com direnv ativo (ou via mkhl.direnv),
# este wrapper é inócuo (o guard deixa tudo como está).
# ────────────────────────────────────────────────────────────────────────────
if ! command -v nix >/dev/null 2>&1; then
    [ -d /nix/var/nix/profiles/default/bin ] &&
        PATH="/nix/var/nix/profiles/default/bin:$PATH"
    [ -d "${HOME:-/nonexistent}/.nix-profile/bin" ] &&
        PATH="${HOME}/.nix-profile/bin:$PATH"
    export PATH
fi
exec direnv exec "$@"
