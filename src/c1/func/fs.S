/*
 * src/c1/func/fs.S — grupo FS: deslocamentos e rotações.
 *
 * Por imediato: quantidades 32 de LSR/ASR são codificadas como 0
 * (DecodeImmShift, §A7.4.2). Por registrador: só o byte baixo de Rm conta
 * (§A7.7.69); 0 (inclusive 256) não desloca e preserva C. Vetores e
 * oráculo: scripts/c1/func/fs.py.
 */
#include "moldes.inc"

@ FS-01 imediato: T1 (16 bits) e T2 (32 bits); RORS só T2
    .irp n, 1, 31
    VUN     v_fs01_lsls_t1_\n, lsls r2, r3, #\n
    VUN     v_fs01_lsls_t2_\n, lsls.w r2, r3, #\n
    VUN     v_fs01_rors_t2_\n, rors r2, r3, #\n
    .endr
    .irp n, 1, 31, 32
    VUN     v_fs01_lsrs_t1_\n, lsrs r2, r3, #\n
    VUN     v_fs01_lsrs_t2_\n, lsrs.w r2, r3, #\n
    VUN     v_fs01_asrs_t1_\n, asrs r2, r3, #\n
    VUN     v_fs01_asrs_t2_\n, asrs.w r2, r3, #\n
    .endr
@ FS-02 RRXS
    VUN     v_fs02_rrxs, rrxs r2, r3
@ FS-03/FS-04 por registrador: T1 (Rdn) e T2
    .irp op, lsls, lsrs, asrs, rors
    VBIN    v_fs03_\op\()_t1, \op r2, r3
    VBIN    v_fs03_\op\()_t2, \op\().w r2, r2, r3
    .endr
@ FS-05 sem S: flags inalteradas
    .irp op, lsl, lsr, asr, ror
    VBIN    v_fs05_\op, \op\().w r2, r2, r3
    .endr
