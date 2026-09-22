#!/usr/bin/env bash
# dump_sram.sh — extrai buffer(s) SRAM do alvo via GDB batch (HW OpenOCD ou Renode :3333).
#
# Uso:
#   dump_sram.sh ELF OUTDIR PREFIX RESULTS_SYM N_SYM DONE_SYM [AUX_SYM AUXN_SYM]
#
#   ELF         firmware.elf com símbolos (para endereços e contagens)
#   OUTDIR      diretório de saída (criado se inexistente)
#   PREFIX      prefixo dos arquivos: OUTDIR/PREFIX.bin (+ _aux.bin se AUX dado)
#   RESULTS_SYM símbolo do buffer principal (ex.: g_results)
#   N_SYM       símbolo com a contagem de words uint32 (ex.: g_n)
#   DONE_SYM    flag de conclusão (==1 pronto; 0xFD/0xFE = erro de firmware)
#   AUX_SYM / AUXN_SYM (opcionais, aos pares): segundo buffer → PREFIX_aux.bin
#
# Porta GDB: env GDB_PORT (default 3333).
# Poll de DONE_SYM até 120 s (sleep 1). Exit 2 = erro de firmware,
# exit 3 = timeout, demais erros exit 1.
set -u

GDB_BIN="arm-none-eabi-gdb"
PORT="${GDB_PORT:-3333}"
TIMEOUT_S="${DUMP_TIMEOUT_S:-120}"

usage() {
    echo "Uso: $0 ELF OUTDIR PREFIX RESULTS_SYM N_SYM DONE_SYM [AUX_SYM AUXN_SYM]" >&2
}

if [ "$#" -lt 6 ] || [ "$#" -eq 7 ]; then
    usage
    exit 1
fi

ELF="$1"
OUTDIR="$2"
PREFIX="$3"
RESULTS_SYM="$4"
N_SYM="$5"
DONE_SYM="$6"
AUX_SYM="${7:-}"
AUXN_SYM="${8:-}"

if ! command -v "$GDB_BIN" >/dev/null 2>&1; then
    echo "dump_sram.sh: erro: $GDB_BIN não encontrado no PATH" >&2
    exit 1
fi

if [ ! -f "$ELF" ]; then
    echo "dump_sram.sh: erro: ELF não encontrado: $ELF" >&2
    exit 1
fi

mkdir -p "$OUTDIR" || { echo "dump_sram.sh: erro: não foi possível criar OUTDIR: $OUTDIR" >&2; exit 1; }

# gdb_eval <expr...>: avalia expressão no alvo e imprime a última linha "$N = ...".
gdb_eval() {
    "$GDB_BIN" --batch \
        -ex "set pagination off" \
        -ex "set confirm off" \
        -ex "file \"$ELF\"" \
        -ex "target extended-remote :$PORT" \
        "$@" \
        -ex "detach" \
        -ex "quit" 2>&1
}

# last_value: extrai o valor da última linha "$N = <val>" (decimal ou 0x...).
last_value() {
    grep -E '^\$[0-9]+ = ' | tail -n 1 | grep -oE '0x[0-9a-fA-F]+|[0-9]+' | tail -n 1
}

to_dec() {
    local v="$1"
    if [ -z "$v" ]; then
        echo ""
        return 1
    fi
    # shellcheck disable=SC1101
    echo "$((v))"
}

echo "dump_sram.sh: aguardando $DONE_SYM==1 (porta $PORT, até ${TIMEOUT_S}s)..."
DONE_DEC=""
i=0
while [ "$i" -lt "$TIMEOUT_S" ]; do
    RAW="$(gdb_eval -ex "interrupt" -ex "print $DONE_SYM")"
    VAL="$(printf '%s\n' "$RAW" | last_value)"
    DONE_DEC="$(to_dec "$VAL" || true)"
    if [ -n "$DONE_DEC" ]; then
        if [ "$DONE_DEC" -eq 1 ]; then
            break
        fi
        if [ "$DONE_DEC" -eq 253 ] || [ "$DONE_DEC" -eq 254 ]; then
            echo "dump_sram.sh: erro: firmware sinalizou erro ($DONE_SYM=$VAL)" >&2
            exit 2
        fi
    else
        echo "dump_sram.sh: aviso: não foi possível ler $DONE_SYM (tentativa $((i + 1))/${TIMEOUT_S})" >&2
    fi
    i=$((i + 1))
    sleep 1
done

if [ "${DONE_DEC:-0}" -ne 1 ]; then
    echo "dump_sram.sh: erro: timeout aguardando $DONE_SYM==1 após ${TIMEOUT_S}s" >&2
    exit 3
fi

# dump_one <SYM> <NSYM> <OUTFILE>: resolve N via "p NSYM" e endereço via "p/x &SYM".
dump_one() {
    local sym="$1"
    local nsym="$2"
    local outfile="$3"

    local raw_n raw_addr val_n val_addr
    raw_n="$(gdb_eval -ex "interrupt" -ex "print $nsym")"
    val_n="$(printf '%s\n' "$raw_n" | last_value)"
    local n_dec
    n_dec="$(to_dec "$val_n" || true)"
    if [ -z "$n_dec" ] || [ "$n_dec" -le 0 ]; then
        echo "dump_sram.sh: erro: contagem inválida para $nsym (saída: $val_n)" >&2
        return 1
    fi

    raw_addr="$(gdb_eval -ex "print/x (unsigned long)&$sym")"
    val_addr="$(printf '%s\n' "$raw_addr" | last_value)"
    local start_dec
    start_dec="$(to_dec "$val_addr" || true)"
    if [ -z "$start_dec" ]; then
        echo "dump_sram.sh: erro: endereço inválido para $sym (saída: $val_addr)" >&2
        return 1
    fi

    local end_dec
    end_dec=$((start_dec + n_dec * 4))
    local start_hex end_hex
    start_hex="$(printf '0x%x' "$start_dec")"
    end_hex="$(printf '0x%x' "$end_dec")"

    echo "dump_sram.sh: dump $sym: n=$n_dec [$start_hex,$end_hex) -> $outfile"
    # NOTE: sem aspas no $outfile — o comando `dump` do GDB não remove
    # aspas e tenta criar arquivo com `"` literal no nome (ENOENT).
    "$GDB_BIN" --batch \
        -ex "set pagination off" \
        -ex "set confirm off" \
        -ex "file \"$ELF\"" \
        -ex "target extended-remote :$PORT" \
        -ex "interrupt" \
        -ex "dump binary memory $outfile $start_hex $end_hex" \
        -ex "detach" \
        -ex "quit" || { echo "dump_sram.sh: erro: falha no dump de $sym" >&2; return 1; }
    # GDB --batch retorna 0 mesmo com falha no comando: verificar o arquivo.
    local want_size
    want_size=$((n_dec * 4))
    local got_size
    got_size="$(stat -c '%s' "$outfile" 2>/dev/null || echo -1)"
    if [ "$got_size" != "$want_size" ]; then
        echo "dump_sram.sh: erro: $outfile ausente ou tamanho errado (esperado $want_size, obtido $got_size)" >&2
        return 1
    fi
}

dump_one "$RESULTS_SYM" "$N_SYM" "$OUTDIR/$PREFIX.bin" || exit 1

if [ -n "$AUX_SYM" ]; then
    dump_one "$AUX_SYM" "$AUXN_SYM" "$OUTDIR/${PREFIX}_aux.bin" || exit 1
fi

echo "dump_sram.sh: OK"
