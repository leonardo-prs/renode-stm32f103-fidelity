/*
 * src/c1/func/fm.S — grupo FM: multiplicação.
 *
 * MUL/MLA/MLS: 32 bits baixos, independem de sinal; MULS (T1, fora de IT)
 * atualiza só N e Z. Multiplicação longa: 64 bits, nenhuma flag
 * (PM0056 §3.6.1–3.6.2). Vetores e oráculo: scripts/c1/func/fm.py.
 */
#include "moldes.inc"

@ FM-01 MULS T1 (Rdm = Rn × Rdm)
    VBIN    v_fm01_muls, muls r2, r3, r2
@ FM-02 MUL T2 (sem flags), MLA, MLS (Ra − Rn × Rm)
    VBIN    v_fm02_mul, mul r2, r2, r3
    VACC    v_fm02_mla, mla r2, r2, r3, r4
    VACC    v_fm02_mls, mls r2, r2, r3, r4
@ FM-03 UMULL/SMULL; FM-04 UMLAL/SMLAL (RdLo = r4, RdHi = r5)
    VLONG   v_fm03_umull, umull r4, r5, r2, r3
    VLONG   v_fm03_smull, smull r4, r5, r2, r3
    VLONG   v_fm04_umlal, umlal r4, r5, r2, r3
    VLONG   v_fm04_smlal, smlal r4, r5, r2, r3
