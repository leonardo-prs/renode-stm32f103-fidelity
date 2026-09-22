#!/usr/bin/env python3
"""analyze.py — estatística simples de dumps .bin (little-endian uint32).

Somente stdlib (struct, argparse, statistics, csv, sys).

Uso:
    analyze.py file.bin [--cols C --col I] [--nominal X]
                        [--tol-cycles T | --tol-pct P]
                        [--hist-bins 20] [--csv out.csv]

    --cols C --col I : usa cada C-ésima word a partir do índice I (default: tudo).
    --nominal X      : valor nominal esperado (ex.: 800000 ciclos).
    --tol-cycles T   : tolerância absoluta em ciclos (|media - nominal| <= T).
    --tol-pct P      : tolerância percentual (|media - nominal| <= nominal*P/100).
    --hist-bins N    : nº de bins do histograma texto (default: 20).
    --csv out.csv    : grava valores selecionados (index,value).
"""

import argparse
import csv
import statistics
import struct
import sys


def parse_args(argv):
    p = argparse.ArgumentParser(description="Estatística de dump .bin u32 LE.")
    p.add_argument("binfile", help="arquivo .bin de words uint32 little-endian")
    p.add_argument(
        "--cols",
        type=int,
        default=None,
        help="passo de seleção (usar cada C-ésima word)",
    )
    p.add_argument(
        "--col", type=int, default=0, help="índice inicial da seleção (default: 0)"
    )
    p.add_argument("--nominal", type=float, default=None, help="valor nominal esperado")
    tol = p.add_mutually_exclusive_group()
    tol.add_argument(
        "--tol-cycles", type=float, default=None, help="tolerância absoluta em ciclos"
    )
    tol.add_argument(
        "--tol-pct",
        type=float,
        default=None,
        help="tolerância percentual sobre o nominal",
    )
    p.add_argument(
        "--hist-bins",
        type=int,
        default=20,
        help="nº de bins do histograma (default: 20)",
    )
    p.add_argument("--csv", default=None, help="arquivo CSV de saída")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    if args.cols is not None and args.cols < 1:
        print("analyze.py: erro: --cols deve ser >= 1", file=sys.stderr)
        return 1
    if args.col < 0:
        print("analyze.py: erro: --col deve ser >= 0", file=sys.stderr)
        return 1
    if args.hist_bins < 1:
        print("analyze.py: erro: --hist-bins deve ser >= 1", file=sys.stderr)
        return 1

    try:
        with open(args.binfile, "rb") as f:
            raw = f.read()
    except OSError as e:
        print(
            f"analyze.py: erro: não foi possível ler {args.binfile}: {e}",
            file=sys.stderr,
        )
        return 1

    if len(raw) == 0:
        print("analyze.py: erro: arquivo vazio", file=sys.stderr)
        return 1
    if len(raw) % 4 != 0:
        print(
            f"analyze.py: erro: tamanho {len(raw)} não é múltiplo de 4", file=sys.stderr
        )
        return 1

    words = list(struct.unpack(f"<{len(raw) // 4}I", raw))

    if args.cols is not None:
        if args.col >= len(words):
            print(
                f"analyze.py: erro: --col {args.col} fora do range (n={len(words)})",
                file=sys.stderr,
            )
            return 1
        data = words[args.col :: args.cols]
    else:
        data = words

    n = len(data)
    mean = statistics.fmean(data)
    # Mediana manual (sem statistics.median) — didático para o TCC.
    s = sorted(data)
    mid = n // 2
    if n % 2 == 1:
        median = float(s[mid])
    else:
        median = (s[mid - 1] + s[mid]) / 2.0
    stdev = statistics.stdev(data) if n >= 2 else 0.0
    vmin = min(data)
    vmax = max(data)

    print(f"file: {args.binfile}")
    print(f"n: {n}")
    print(f"mean: {mean:.3f}")
    print(f"median: {median:.3f}")
    print(f"stdev: {stdev:.3f}")
    print(f"min: {vmin}")
    print(f"max: {vmax}")

    # Histograma texto.
    nbins = args.hist_bins
    counts = [0] * nbins
    if vmax == vmin:
        counts[0] = n
        lo = [vmin] * nbins
        hi = [vmax] * nbins
    else:
        width = (vmax - vmin) / nbins
        lo = [vmin + i * width for i in range(nbins)]
        hi = [vmin + (i + 1) * width for i in range(nbins)]
        for v in data:
            idx = int((v - vmin) / (vmax - vmin) * nbins)
            if idx >= nbins:
                idx = nbins - 1
            counts[idx] += 1
    cmax = max(counts) if counts else 0
    print(f"histogram ({nbins} bins):")
    for i in range(nbins):
        bar_len = int(counts[i] * 50 / cmax) if cmax else 0
        print(f"  [{lo[i]:12.3f},{hi[i]:12.3f}] {counts[i]:6d} {'#' * bar_len}")

    if args.csv:
        try:
            with open(args.csv, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["index", "value"])
                for i, v in enumerate(data):
                    w.writerow([i, v])
            print(f"csv: {args.csv}")
        except OSError as e:
            print(
                f"analyze.py: erro: não foi possível escrever {args.csv}: {e}",
                file=sys.stderr,
            )
            return 1

    if args.nominal is not None:
        delta = mean - args.nominal
        print(f"nominal: {args.nominal:.3f}")
        print(f"delta (mean-nominal): {delta:+.3f}")
        if args.tol_cycles is not None:
            ok = abs(delta) <= args.tol_cycles
            print(
                f"tolerance: ±{args.tol_cycles:.3f} cycles -> "
                f"{'PASS' if ok else 'FAIL'}"
            )
            return 0 if ok else 2
        if args.tol_pct is not None:
            tol_abs = abs(args.nominal) * args.tol_pct / 100.0
            ok = abs(delta) <= tol_abs
            print(
                f"tolerance: ±{args.tol_pct} % (±{tol_abs:.3f}) -> "
                f"{'PASS' if ok else 'FAIL'}"
            )
            return 0 if ok else 2
        print("tolerance: (não informada — sem veredicto)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
