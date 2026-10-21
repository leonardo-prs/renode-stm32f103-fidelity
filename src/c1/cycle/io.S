/*
 * src/c1/cycle/io.S — T-IO (acesso a periféricos e buffer de escrita).
 * Só a unidade de ler-modificar-escrever (T-IO-06.rmw) é nova: os demais
 * casos reutilizam os blocos da SRAM (t_ls01, t_ls03, t_ls06, t_al02_str,
 * t_sys03_str, t_bb03) com a base num registrador de periférico, e esta
 * unidade também roda com a base na SRAM como controle. Ver
 * scripts/c1/cycle/io.py.
 */
#include "blocks.inc"

.macro U_rmw                        @ r0 = registrador, r2 = máscara (1 << 5)
    ldr     r1, [r0]
    orrs    r1, r2
    str     r1, [r0]
.endm
    BLOCKSET t_io06_rmw, U_rmw
