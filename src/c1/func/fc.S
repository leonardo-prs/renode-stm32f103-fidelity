/*
 * src/c1/func/fc.S — grupo FC: controle de fluxo.
 *
 * Marcadores: cada caminho grava em r3 um valor distinto; o oráculo diz qual
 * caminho a especificação manda tomar (ConditionPassed, §A7.3.1; ITAdvance,
 * §A7.3.3). Depois do ponto de teste, só MOV.W (sem S) é usado, para que o
 * APSR gravado seja o que a instrução sob teste deixou.
 * Vetores e oráculo: scripts/c1/func/fc.py.
 */
#include "moldes.inc"

/* ── FC-01: B<cond> T1/T3 e B T2/T4. in = {APSR}  out = {tomado, APSR} ── */
.macro BCOND name, insn:vararg
FUNC \name
    push    {r4, lr}
    mov.w   r3, #1                  @ marcador: tomado
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X \name
    \insn   1f
    mov.w   r3, #0                  @ não tomado
1:  mrs     r4, APSR
    str     r3, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm

    .irp c, eq, ne, cs, cc, mi, pl, vs, vc, hi, ls, ge, lt, gt, le
    BCOND   v_fc01_t1_\c, b\c\().n
    BCOND   v_fc01_t3_\c, b\c\().w
    .endr
    BCOND   v_fc01_t2, b.n
    BCOND   v_fc01_t4, b.w

/* ── FC-02: blocos IT. in = {APSR}  out = {bits executados, APSR} ──
 * A k-ésima instrução do bloco liga o bit k de r3. Cada posição recebe a
 * condição do bloco ('t') ou a inversa ('e'). */
.macro ITSLOT s, c, ic, bit
    .ifc \s,t
    orr\c   r3, r3, #\bit
    .else
    orr\ic  r3, r3, #\bit
    .endif
.endm

.macro ITB name, pat, s1, s2, s3, c, ic
FUNC \name
    push    {r4, lr}
    mov.w   r3, #0
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X \name
    it\pat  \c
    ITSLOT  t, \c, \ic, 1
    .ifnb \s1
    ITSLOT  \s1, \c, \ic, 2
    .endif
    .ifnb \s2
    ITSLOT  \s2, \c, \ic, 4
    .endif
    .ifnb \s3
    ITSLOT  \s3, \c, \ic, 8
    .endif
    mrs     r4, APSR
    str     r3, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm

.macro ITPAIR pat, s1, s2, s3, c, ic
    ITB     v_fc02_it\pat\()_\c, \pat, \s1, \s2, \s3, \c, \ic
.endm

.macro ITALL pat, s1, s2, s3
    .irp pair, "eq,ne", "ne,eq", "cs,cc", "cc,cs", "mi,pl", "pl,mi", "vs,vc", "vc,vs", "hi,ls", "ls,hi", "ge,lt", "lt,ge", "gt,le", "le,gt"
    ITPAIR  \pat, \s1, \s2, \s3, \pair
    .endr
.endm

    ITALL   , , ,
    ITALL   t, t, ,
    ITALL   e, e, ,
    ITALL   te, t, e,
    ITALL   et, e, t,
    ITALL   ttt, t, t, t
    ITALL   eee, e, e, e
@ IT AL: legal no ARMv7-M só sem "senão" (§A7.7.38), mas o montador recusa
@ qualquer bloco IT AL. O IT entra como palavra crua (1011 1111 cond mask:
@ IT AL = 0xBFE8, ITTTT AL = 0xBFE1) e as posições como ORR.W sem condição,
@ que é exatamente a codificação de um ORR com condição AL.
.macro ITAL name, raw, n
FUNC \name
    push    {r4, lr}
    mov.w   r3, #0
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X \name
    .inst.n \raw
    orr     r3, r3, #1
    .if \n > 1
    orr     r3, r3, #2
    orr     r3, r3, #4
    orr     r3, r3, #8
    .endif
    mrs     r4, APSR
    str     r3, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm
    ITAL    v_fc02_it_al, 0xbfe8, 1
    ITAL    v_fc02_itttt_al, 0xbfe1, 4

/* ── FC-03: forma de 16 bits que altera flags, dentro e fora de IT ──
 * Mesma codificação (ADDS/MOVS T1); dentro do bloco, setflags = !InITBlock().
 * in = {Rn, Rm, APSR}  out = {Rd, APSR} */
    VBIN    v_fc03_add_out, adds r2, r2, r3
FUNC v_fc03_add_in
    push    {r4, lr}
    ldr     r2, [r0, #8]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    ldr     r3, [r0, #4]
X v_fc03_add_in, 0
    it      eq
X v_fc03_add_in, 1
    addeq   r2, r2, r3
    mrs     r4, APSR
    str     r2, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF v_fc03_add_in
    VBIN    v_fc03_mov_out, movs r2, #0
FUNC v_fc03_mov_in
    push    {r4, lr}
    ldr     r2, [r0, #8]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
X v_fc03_mov_in, 0
    it      eq
X v_fc03_mov_in, 1
    moveq   r2, #0
    mrs     r4, APSR
    str     r2, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF v_fc03_mov_in

/* ── FC-04: instrução do bloco que muda flags. in = {Rn, Rm, APSR}
 * out = {marcador, APSR}: o MOVEQ usa as flags produzidas pelo CMPEQ. */
FUNC v_fc04
    push    {r4, lr}
    mov.w   r12, #0
    ldr     r2, [r0, #8]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
    ldr     r3, [r0, #4]
X v_fc04
    itt     eq
    cmpeq   r2, r3
    moveq   r12, #1
    mrs     r4, APSR
    str     r12, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF v_fc04

/* ── FC-05: CBZ/CBNZ. in = {Rn, APSR}  out = {tomado, APSR} ── */
.macro CBX name, op
FUNC \name
    push    {r4, lr}
    mov.w   r3, #1
    ldr     r2, [r0, #4]
    msr     APSR_nzcvq, r2
    ldr     r2, [r0, #0]
X \name
    \op     r2, 1f
    mov.w   r3, #0
1:  mrs     r4, APSR
    str     r3, [r1, #0]
    str     r4, [r1, #4]
    pop     {r4, pc}
ENDF \name
.endm
    CBX     v_fc05_cbz, cbz
    CBX     v_fc05_cbnz, cbnz

/* ── FC-06: TBB/TBH. in = {índice}  out = {alvo 1..3} ──
 * Tabela na flash (base = PC) e na SRAM (base = registrador). Na SRAM, a
 * tabela é a cópia da que segue o TBB: as entradas são relativas ao PC do
 * próprio TBB, então continuam valendo. Tabelas alinhadas (errata 674118). */
FUNC v_fc06_tbb_flash
    push    {r4, lr}
    ldr     r2, [r0, #0]
X v_fc06_tbb_flash
    tbb     [pc, r2]
1:  .byte   (2f - 1b) / 2, (3f - 1b) / 2, (4f - 1b) / 2
    .p2align 1
2:  mov.w   r3, #1
    b.n     5f
3:  mov.w   r3, #2
    b.n     5f
4:  mov.w   r3, #3
5:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc06_tbb_flash

FUNC v_fc06_tbh_flash
    push    {r4, lr}
    ldr     r2, [r0, #0]
X v_fc06_tbh_flash
    tbh     [pc, r2, lsl #1]
1:  .hword  (2f - 1b) / 2, (3f - 1b) / 2, (4f - 1b) / 2
2:  mov.w   r3, #1
    b.n     5f
3:  mov.w   r3, #2
    b.n     5f
4:  mov.w   r3, #3
5:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc06_tbh_flash

FUNC v_fc06_tbb_sram
    push    {r4, lr}
    ldr     r4, =c1_scratch
    adr.w   r3, 1f
    ldrb    r2, [r3, #0]
    strb    r2, [r4, #0]
    ldrb    r2, [r3, #1]
    strb    r2, [r4, #1]
    ldrb    r2, [r3, #2]
    strb    r2, [r4, #2]
    ldr     r2, [r0, #0]
X v_fc06_tbb_sram
    tbb     [r4, r2]
1:  .byte   (2f - 1b) / 2, (3f - 1b) / 2, (4f - 1b) / 2
    .p2align 1
2:  mov.w   r3, #1
    b.n     5f
3:  mov.w   r3, #2
    b.n     5f
4:  mov.w   r3, #3
5:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc06_tbb_sram

FUNC v_fc06_tbh_sram
    push    {r4, lr}
    ldr     r4, =c1_scratch
    adr.w   r3, 1f
    ldrh    r2, [r3, #0]
    strh    r2, [r4, #0]
    ldrh    r2, [r3, #2]
    strh    r2, [r4, #2]
    ldrh    r2, [r3, #4]
    strh    r2, [r4, #4]
    ldr     r2, [r0, #0]
X v_fc06_tbh_sram
    tbh     [r4, r2, lsl #1]
1:  .hword  (2f - 1b) / 2, (3f - 1b) / 2, (4f - 1b) / 2
2:  mov.w   r3, #1
    b.n     5f
3:  mov.w   r3, #2
    b.n     5f
4:  mov.w   r3, #3
5:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc06_tbh_sram

/* ── FC-07: BL e BLX Rm para rotina folha; retorno por BX LR.
 * in = {—}  out = {LR visto pela folha, marcador da folha} ── */
FUNC c1_fc07_leaf
    mov     r12, lr
    movs    r3, #7
    bx      lr
ENDF c1_fc07_leaf

FUNC v_fc07_bl
    push    {r4, lr}
    movs    r3, #0
X v_fc07_bl
    bl      c1_fc07_leaf
    str     r12, [r1, #0]
    str     r3, [r1, #4]
    pop     {r4, pc}
ENDF v_fc07_bl

FUNC v_fc07_blx
    push    {r4, lr}
    movs    r3, #0
    ldr     r2, =c1_fc07_leaf       @ endereço de função Thumb: bit 0 = 1
X v_fc07_blx
    blx     r2
    str     r12, [r1, #0]
    str     r3, [r1, #4]
    pop     {r4, pc}
ENDF v_fc07_blx

/* ── FC-08: BX/BLX para endereço PAR → UsageFault INVSTATE na instrução
 * do alvo (PC empilhado = alvo, T empilhado = 0). in = {APSR}  out = {marcador} */
.macro BXEVEN name, op
FUNC \name
    push    {r4, lr}
    LAND    r3, r4, 9f
    mov.w   r3, #0
    adr.w   r2, 8f
    bic     r2, r2, #1              @ bit 0 = 0: sai do estado Thumb
    ldr     r4, [r0, #0]
    msr     APSR_nzcvq, r4
X \name, 0
    \op     r2
X \name, 1
8:  mov.w   r3, #1                  @ nunca executa (falta antes)
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm
    BXEVEN  v_fc08_bx, bx
    BXEVEN  v_fc08_blx, blx

/* ── FC-09: MOV PC, Rm e ADD PC, Rm (16 bits) com bit 0 = 0 e = 1:
 * ALUWritePC ignora o bit 0, sem falta e sem troca de estado.
 * in = {bit}  out = {marcador}. MOV desvia para Rm; ADD para PC + Rm, com
 * PC = endereço do ADD + 4 (§A7.7.4, §A7.7.77). ── */
FUNC v_fc09_mov
    push    {r4, lr}
    LAND    r3, r4, 9f
    mov.w   r3, #0
    ldr     r4, [r0, #0]
    adr.w   r2, 8f
    bic     r2, r2, #1
    orr     r2, r2, r4
X v_fc09_mov
    mov     pc, r2
    mov.w   r3, #2                  @ não deveria executar
    b.n     9f
8:  mov.w   r3, #1
LANDING v_fc09_mov
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc09_mov

FUNC v_fc09_add
    push    {r4, lr}
    LAND    r3, r4, 9f
    mov.w   r3, #0
    ldr     r4, [r0, #0]
    adr.w   r2, 8f
    adr.w   r12, 7f
    sub     r2, r2, r12
    sub     r2, r2, #4              @ deslocamento até o alvo a partir de ADD + 4
    orr     r2, r2, r4
X v_fc09_add
7:  add     pc, r2
    mov.w   r3, #2
    b.n     9f
8:  mov.w   r3, #1
LANDING v_fc09_add
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc09_add

/* ── FC-10: LDR PC, POP {PC}, LDM {…, PC}: bit 0 = 1 desvia; bit 0 = 0
 * troca para ARM → INVSTATE no alvo. in = {bit, APSR}  out = {marcador} ── */
.macro LOADPC name, kind
FUNC \name
    push    {r4, lr}
    LAND    r3, r4, 9f
    mov.w   r3, #0
    ldr     r4, [r0, #0]
    adr.w   r2, 8f
    bic     r2, r2, #1
    orr     r2, r2, r4              @ endereço carregado, com o bit 0 do vetor
    ldr     r12, =c1_scratch
    str     r4, [r12, #0]           @ c1_scratch = {lixo, alvo}
    str     r2, [r12, #4]
    ldr     r4, [r0, #4]
    msr     APSR_nzcvq, r4
    .ifc \kind,ldr
    add     r12, r12, #4
X \name, 0
    ldr     pc, [r12]
    .endif
    .ifc \kind,pop
    ldr     r4, [r12, #4]
    str     r4, [sp, #-4]!          @ pilha = {lixo, alvo}: POP {r4, pc}
    ldr     r4, [r12, #0]
    str     r4, [sp, #-4]!
X \name, 0
    pop     {r4, pc}
    .endif
    .ifc \kind,ldm
X \name, 0
    ldm     r12, {r4, pc}
    .endif
    mov.w   r3, #2
    b.n     9f
X \name, 1
8:  mov.w   r3, #1
LANDING \name
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm
    LOADPC  v_fc10_ldr, ldr
    LOADPC  v_fc10_pop, pop
    LOADPC  v_fc10_ldm, ldm

/* ── FC-11: instrução indefinida dentro de IT com condição falsa = NOP
 * (§A7.3.2). QADD (DSP) é indefinida no M3: com Z = 1, IT NE pula; com
 * Z = 0, UNDEFINSTR. in = {APSR}  out = {marcador} ── */
FUNC v_fc11
    push    {r4, lr}
    LAND    r3, r4, 9f
    mov.w   r3, #1
    ldr     r2, [r0, #0]
    msr     APSR_nzcvq, r2
X v_fc11, 0
    it      ne
X v_fc11, 1
    .inst.w 0xFA81F080              @ QADD r0, r0, r1 (codificação do ARMv7E-M)
LANDING v_fc11
9:  str     r3, [r1, #0]
    pop     {r4, pc}
ENDF v_fc11
