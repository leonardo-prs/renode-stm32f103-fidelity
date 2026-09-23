#!/usr/bin/env bash
# run_battery.sh — bateria Renode p/ o relatório tcc/reports/renode-1.17.md.
#
# Os .resc canônicos (renode/c1|c2|c2busy|c3|c4.resc) NÃO têm `start`;
# este script acrescenta perfil (-e) + `start` e coleta o dump.
#
# Uso:
#   scripts/run_battery.sh CASE PREFIX [--launch-only | --dump-only]
#     CASE: c1 | c1m8 | c2 | c2busy | c3 | c3q10us | c3q100us | c3q1ms | c4
#     default: lança + aguarda done + dump (bloqueante; C4 é longo, prefira
#              --launch-only e depois --dump-only em outra chamada).
#
# Matriz do relatório (1.17, OUTDIR=tcc/data/raw), 2 runs por caso base:
#   c1_r1 c1_r2 | c1m8_r1 c1m8_r2 | c2_r1 c2_r2 | c2busy_r1 c2busy_r2 |
#   c3_r1 c3_r2 | c3q10us c3q100us c3q1ms | c4_r1 c4_r2
#   c1m8 = C1 perfil idealizado (MIPS=8, Q=12.5us), MESMO ELF build/c1.
#   c3q* = sweep de quantum E(Q), MESMO ELF build/c3.
#
# Env: RENODE_BIN (default renode, 1.17.0 via flake), OUTDIR (default tcc/data/raw),
#      GDB_PORT (3333), MON_PORT (1234), DUMP_TIMEOUT_S (300; C4 quer ~900).
# Paralelo: MON_PORT+GDB_PORT distintos por run (matriz no log);
# nunca kill global com runs paralelos (kill_renode só p/ uso manual).
set -u

RENODE_BIN="${RENODE_BIN:-renode}"
# Rodar dentro de `nix develop` (ou `nix develop -c scripts/run_battery.sh`)
# para que `renode` seja o 1.17.0 do flake.
command -v "$RENODE_BIN" >/dev/null || { echo "ERRO: '$RENODE_BIN' fora do PATH (rodar em nix develop)" >&2; exit 1; }
OUTDIR="${OUTDIR:-tcc/data/raw}"
export GDB_PORT="${GDB_PORT:-3333}"
MON_PORT="${MON_PORT:-1234}"
export DUMP_TIMEOUT_S="${DUMP_TIMEOUT_S:-300}"

MODE="run"
if [ "${1:-}" = "--launch-only" ]; then MODE="launch"; shift; fi
if [ "${1:-}" = "--dump-only" ]; then MODE="dump"; shift; fi
CASE="${1:?Uso: $0 [--launch-only|--dump-only] CASE PREFIX}"
PREFIX="${2:?Uso: $0 [--launch-only|--dump-only] CASE PREFIX}"

# --- descritor do caso: RESC ELF SYM N DONE [AUX AUXN] ---
case "$CASE" in
  c1)     RESC=renode/c1.resc;     ELF=build/c1/firmware.elf;     SYM=c1_results; N=c1_n; DONE=c1_done; AUX=() ; EXTRA=() ;;
  c1m8)   RESC=renode/c1.resc;     ELF=build/c1/firmware.elf;     SYM=c1_results; N=c1_n; DONE=c1_done; AUX=() ;
          EXTRA=(-e 'sysbus.cpu PerformanceInMips 8' -e 'emulation SetGlobalQuantum "0.0000125"') ;;
  c2)     RESC=renode/c2.resc;     ELF=build/c2/firmware.elf;     SYM=c2_results; N=c2_n; DONE=c2_done; AUX=() ; EXTRA=() ;;
  c2busy) RESC=renode/c2busy.resc; ELF=build/c2busy/firmware.elf; SYM=c2_results; N=c2_n; DONE=c2_done; AUX=() ; EXTRA=() ;;
  c3)     RESC=renode/c3.resc;     ELF=build/c3/firmware.elf;     SYM=c3_results; N=c3_n; DONE=c3_done; AUX=() ; EXTRA=() ;;
  c3q10us)   RESC=renode/c3.resc;  ELF=build/c3/firmware.elf;     SYM=c3_results; N=c3_n; DONE=c3_done; AUX=() ;
          EXTRA=(-e 'emulation SetGlobalQuantum "0.00001"') ;;
  c3q100us)  RESC=renode/c3.resc;  ELF=build/c3/firmware.elf;     SYM=c3_results; N=c3_n; DONE=c3_done; AUX=() ;
          EXTRA=(-e 'emulation SetGlobalQuantum "0.0001"') ;;
  c3q1ms)    RESC=renode/c3.resc;  ELF=build/c3/firmware.elf;     SYM=c3_results; N=c3_n; DONE=c3_done; AUX=() ;
          EXTRA=(-e 'emulation SetGlobalQuantum "0.001"') ;;
  c4)     RESC=renode/c4.resc;     ELF=build/c4/firmware.elf;     SYM=c4_results; N=c4_n; DONE=c4_done; AUX=(c4_aux c4_auxn) ; EXTRA=() ;;
  *) echo "CASE desconhecido: $CASE" >&2; exit 1 ;;
esac

kill_renode() {
    # case-insensitive de propósito: apphost 1.17 tem comm minúsculo
    # (limpezas com `ps -C Renode` falharam por isso — ver log).
    ps -eo pid,comm | awk 'tolower($2)=="renode" {print $1}' | xargs -r kill -9 2>/dev/null
    sleep 1
}

do_dump() {
    if [ "${#AUX[@]}" -eq 2 ]; then
        scripts/dump_sram.sh "$ELF" "$OUTDIR" "$PREFIX" "$SYM" "$N" "$DONE" "${AUX[0]}" "${AUX[1]}"
    else
        scripts/dump_sram.sh "$ELF" "$OUTDIR" "$PREFIX" "$SYM" "$N" "$DONE"
    fi
}

do_launch() {
    local log="$OUTDIR/${PREFIX}.log"
    mkdir -p "$OUTDIR"
    # resc temporário (/tmp) com a porta GDB deste run; repo mantém 3333.
    # Portas (monitor+GDB) isolam runs paralelos — sem kill global aqui.
    local tmpresc="/tmp/battery_${PREFIX}.resc"
    sed "s/StartGdbServer 3333/StartGdbServer $GDB_PORT/" "$RESC" > "$tmpresc"
    setsid nohup "$RENODE_BIN" --disable-xwt -P "$MON_PORT" -e "s @$tmpresc" "${EXTRA[@]}" -e start > "$log" 2>&1 < /dev/null &
    echo "run_battery: $CASE -> $PREFIX (pid $!, mon $MON_PORT, gdb $GDB_PORT, log $log)"
}

case "$MODE" in
  launch) do_launch ;;
  dump)   do_dump ;;
  run)    do_launch; sleep 2; do_dump ;;
esac
