#!/usr/bin/env bash
# run_hw.sh — bateria hardware (Blue Pill STM32F103 via ST-Link/OpenOCD).
#
# Uso: scripts/run_hw.sh CASE PREFIX
#   CASE: c1 | c2 | c2busy | c3 | c4  (ELFs já compilados em build/c*)
#   PREFIX: ex. c1hw_r1 (datasets em OUTDIR, default tcc/data/raw)
#
# Fluxo por run: flash (program+verify+reset+exit) → daemon openocd em
# background → dump via dump_sram.sh (GDB :3333 — OpenOCD; o Renode usa :3334,
# portas separadas p/ permitir HW e simulador em paralelo).
# buffer + done=1 + alfor parado) → kill daemon.
# Pré-requisitos: regra udev do ST-Link instalada (ver tcc/tmp/log.md),
# jumper PA9->PA10 fitted p/ C4, nenhum openocd/Renode rodando.
#
# Env: OUTDIR (default tcc/data/raw), GDB_PORT (3333),
#      DUMP_TIMEOUT_S (120; C1 leva ~20s reais).
set -u

CASE="${1:?Uso: $0 CASE PREFIX  (CASE=c1|c2|c2busy|c3|c4)}"
PREFIX="${2:?Uso: $0 CASE PREFIX}"
OUTDIR="${OUTDIR:-tcc/data/raw}"
export GDB_PORT="${GDB_PORT:-3333}"  # OpenOCD; Renode usa 3334 (.resc + tasks)
export DUMP_TIMEOUT_S="${DUMP_TIMEOUT_S:-120}"

case "$CASE" in
  c1)     ELF=build/c1/firmware.elf;         SYM=c1_results; N=c1_n; DONE=c1_done; AUX=() ;;
  c2)     ELF=build/c2/firmware.elf;         SYM=c2_results; N=c2_n; DONE=c2_done; AUX=() ;;
  c2busy) ELF=build/c2busy/firmware.elf;     SYM=c2_results; N=c2_n; DONE=c2_done; AUX=() ;;
  c3)     ELF=build/c3/firmware.elf;         SYM=c3_results; N=c3_n; DONE=c3_done; AUX=() ;;
  c4)     ELF=build/c4/firmware.elf;         SYM=c4_results; N=c4_n; DONE=c4_done; AUX=(c4_aux c4_auxn) ;;
  *) echo "CASE desconhecido: $CASE" >&2; exit 1 ;;
esac

mkdir -p "$OUTDIR"

echo "run_hw: flash $ELF"
timeout 120 openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
    -c "program $ELF verify reset exit" > "$OUTDIR/${PREFIX}_flash.log" 2>&1 \
    || { echo "run_hw: FALHA no flash (ver $OUTDIR/${PREFIX}_flash.log)" >&2; tail -5 "$OUTDIR/${PREFIX}_flash.log" >&2; exit 1; }
grep -q 'verified' "$OUTDIR/${PREFIX}_flash.log" && echo "run_hw: flash verified OK" || echo "run_hw: AVISO: 'verified' nao encontrado no log"

echo "run_hw: daemon openocd + dump $PREFIX"
setsid nohup openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
    > "$OUTDIR/${PREFIX}_ocd.log" 2>&1 < /dev/null &
sleep 3
if [ "${#AUX[@]}" -eq 2 ]; then
    scripts/dump_sram.sh "$ELF" "$OUTDIR" "$PREFIX" "$SYM" "$N" "$DONE" "${AUX[0]}" "${AUX[1]}"
else
    scripts/dump_sram.sh "$ELF" "$OUTDIR" "$PREFIX" "$SYM" "$N" "$DONE"
fi
rc=$?
pkill -x openocd 2>/dev/null
exit $rc
