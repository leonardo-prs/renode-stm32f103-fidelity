/*
 * src/c1/func/fl.S — grupo FL: lógicas, MOV/MVN e constantes modificadas.
 *
 * Lógicas com S: N, Z pelo resultado; C = carry do deslocador (o último bit
 * que saiu do segundo operando, se ele foi deslocado; senão, inalterado);
 * V inalterado (§A7.7.9). Com constante modificada, só a forma rotacionada
 * altera C (PM0056 §3.3.3). Vetores e oráculo: scripts/c1/func/fl.py.
 */
#include "moldes.inc"

@ FL-01 registrador sem deslocamento: T1 (Rdn, 16 bits) e T2 (32 bits)
    .irp op, ands, orrs, eors, bics
    VBIN    v_fl01_\op\()_t1, \op r2, r3
    VBIN    v_fl01_\op\()_t2, \op\().w r2, r2, r3
    .endr
    VBIN    v_fl01_orns_t1, orns r2, r2, r3     @ ORN só existe em 32 bits

@ FL-02 segundo operando deslocado (só 32 bits)
    .irp op, ands, orrs, eors, bics, orns
    VBIN    v_fl02_\op\()_lsl1,  \op r2, r2, r3, lsl #1
    VBIN    v_fl02_\op\()_lsr32, \op r2, r2, r3, lsr #32
    VBIN    v_fl02_\op\()_asr32, \op r2, r2, r3, asr #32
    VBIN    v_fl02_\op\()_ror1,  \op r2, r2, r3, ror #1
    VBIN    v_fl02_\op\()_rrx,   \op r2, r2, r3, rrx
    .endr

@ FL-03 MOVS/MVNS registrador; TST/TEQ registrador
    VUN     v_fl03_movs_t2, movs r2, r3
    VUN     v_fl03_movs_t3, movs.w r2, r3
    VUN     v_fl03_mvns_t1, mvns r2, r3
    VUN     v_fl03_mvns_t2, mvns.w r2, r3
    VFLG2   v_fl03_tst_t1, tst r2, r3
    VFLG2   v_fl03_tst_t2, tst.w r2, r3
    VFLG2   v_fl03_teq_t1, teq r2, r3          @ TEQ só existe em 32 bits

@ FL-04 constantes modificadas (formas de 32 bits)
    .irp c, 0xab, 0xab00ab, 0xab00ab00, 0xabababab, 0x80000000, 0xff0
    VUN     v_fl04_movs_\c, movs.w r2, #\c
    VUN     v_fl04_mvns_\c, mvns r2, #\c
    VUN     v_fl04_ands_\c, ands r2, r3, #\c
    VUN     v_fl04_orrs_\c, orrs r2, r3, #\c
    VUN     v_fl04_eors_\c, eors r2, r3, #\c
    VUN     v_fl04_bics_\c, bics r2, r3, #\c
    VFLG1   v_fl04_tst_\c, tst r2, #\c
    .endr

@ FL-05 sem flags: MOV (T1 16 bits, T3 32 bits), MVN, MOVW, MOVT
    VUN     v_fl05_mov_t1, mov r2, r3
    VUN     v_fl05_mov_t3, mov.w r2, r3
    VUN     v_fl05_mvn, mvn r2, r3
    VUN     v_fl05_movw, movw r2, #0xabcd
    VUN     v_fl05_movt, movt r2, #0xabcd
