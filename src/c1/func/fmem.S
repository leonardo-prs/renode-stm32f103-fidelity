/*
 * src/c1/func/fmem.S — grupo FMEM: larguras, extensão de sinal e modos de
 * endereçamento (little-endian, RM0008 §3.2; subpalavra não altera vizinhos,
 * TRM §2.4; modos, §A4.6.5; LDM/STM, §A7.7.41/§A7.7.159).
 *
 * Memória: c1_scratch (32 B, alinhada a 16). Nos casos F_MEM o main a
 * pré-enche com 0xA5 e grava a janela inteira depois do vetor, de modo que
 * um byte vizinho alterado indevidamente aparece no resultado.
 * Vetores e oráculo: scripts/c1/func/fmem.py.
 */
#include "moldes.inc"

/* ── FMEM-01: STR/STRH/STRB em c1_scratch + 12, lidos como palavra e bytes.
 * in = {valor}  out = {palavra, b0, b1, b2, b3} + janela ── */
.macro STW name, op
FUNC \name
    push    {r4, lr}
    ldr     r2, =c1_scratch + 12
    ldr     r3, [r0, #0]
X \name
    \op     r3, [r2]
    ldr     r4, [r2]
    str     r4, [r1, #0]
    ldrb    r4, [r2, #0]
    str     r4, [r1, #4]
    ldrb    r4, [r2, #1]
    str     r4, [r1, #8]
    ldrb    r4, [r2, #2]
    str     r4, [r1, #12]
    ldrb    r4, [r2, #3]
    str     r4, [r1, #16]
    pop     {r4, pc}
ENDF \name
.endm
    STW     v_fmem01_str, str
    STW     v_fmem01_strh, strh
    STW     v_fmem01_strb, strb

/* ── FMEM-02: LDRB/LDRH/LDRSB/LDRSH. A palavra do vetor vai para
 * c1_scratch + 12; o byte testado é o de deslocamento 1 e a meia palavra a
 * de deslocamento 2 (r4 = deslocamento nas formas por registrador).
 * in = {palavra}  out = {carregado} ── */
.macro LDX name, off, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, =c1_scratch + 12
    ldr     r3, [r0, #0]
    str     r3, [r2]
    mov.w   r3, #0
    mov.w   r4, #\off
X \name
    \insn
    str     r3, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm
    LDX     v_fmem02_ldrb_t1, 1, ldrb r3, [r2, #1]
    LDX     v_fmem02_ldrb_w, 1, ldrb.w r3, [r2, #1]
    LDX     v_fmem02_ldrsb_r, 1, ldrsb r3, [r2, r4]
    LDX     v_fmem02_ldrsb_w, 1, ldrsb.w r3, [r2, #1]
    LDX     v_fmem02_ldrh_t1, 2, ldrh r3, [r2, #2]
    LDX     v_fmem02_ldrh_w, 2, ldrh.w r3, [r2, #2]
    LDX     v_fmem02_ldrsh_r, 2, ldrsh r3, [r2, r4]
    LDX     v_fmem02_ldrsh_w, 2, ldrsh.w r3, [r2, #2]

/* ── FMEM-03: modos de endereçamento, base r2 = c1_scratch + 16.
 * Carga: o valor do vetor é posto antes no endereço-alvo (deslocamento
 * `tgt` em c1_scratch); out = {carregado, base final − c1_scratch}.
 * Escrita: out = {base final − c1_scratch} + janela. ── */
.macro LDMODE name, tgt, idx, insn:vararg
FUNC \name
    push    {r4, r5, r6, lr}
    ldr     r5, =c1_scratch
    add     r2, r5, #16
    ldr     r3, [r0, #0]
    str     r3, [r5, #\tgt]
    mov.w   r3, #0
    mov.w   r4, #\idx
X \name
    \insn
    str     r3, [r1, #0]
    sub     r2, r2, r5
    str     r2, [r1, #4]
    pop     {r4, r5, r6, pc}
ENDF \name
.endm
.macro STMODE name, idx, insn:vararg
FUNC \name
    push    {r4, r5, r6, lr}
    ldr     r5, =c1_scratch
    add     r2, r5, #16
    ldr     r3, [r0, #0]
    mov.w   r4, #\idx
X \name
    \insn
    sub     r2, r2, r5
    str     r2, [r1, #0]
    pop     {r4, r5, r6, pc}
ENDF \name
.endm
    LDMODE  v_fmem03_ldr_imm12, 20, 0, ldr.w r3, [r2, #4]
    LDMODE  v_fmem03_ldr_neg8, 12, 0, ldr r3, [r2, #-4]
    LDMODE  v_fmem03_ldr_reg, 20, 4, ldr r3, [r2, r4]
    LDMODE  v_fmem03_ldr_lsl0, 20, 4, ldr.w r3, [r2, r4]
    LDMODE  v_fmem03_ldr_lsl1, 20, 2, ldr.w r3, [r2, r4, lsl #1]
    LDMODE  v_fmem03_ldr_lsl2, 20, 1, ldr.w r3, [r2, r4, lsl #2]
    LDMODE  v_fmem03_ldr_lsl3, 24, 1, ldr.w r3, [r2, r4, lsl #3]
    LDMODE  v_fmem03_ldr_pre, 20, 0, ldr r3, [r2, #4]!
    LDMODE  v_fmem03_ldr_post, 16, 0, ldr r3, [r2], #4
    STMODE  v_fmem03_str_imm12, 0, str.w r3, [r2, #4]
    STMODE  v_fmem03_str_neg8, 0, str r3, [r2, #-4]
    STMODE  v_fmem03_str_reg, 4, str r3, [r2, r4]
    STMODE  v_fmem03_str_lsl1, 2, str.w r3, [r2, r4, lsl #1]
    STMODE  v_fmem03_str_lsl2, 1, str.w r3, [r2, r4, lsl #2]
    STMODE  v_fmem03_str_lsl3, 1, str.w r3, [r2, r4, lsl #3]
    STMODE  v_fmem03_str_pre, 0, str r3, [r2, #4]!
    STMODE  v_fmem03_str_post, 0, str r3, [r2], #4

/* ── FMEM-04: LDR literal (T1) em endereço ≡ 0 e ≡ 2 (mod 4): a base é
 * Align(PC, 4), então as duas cargas leem o MESMO literal. out = {valor} ── */
FUNC v_fmem04_a4
    push    {r4, lr}                @ +0
    nop                             @ +2
X v_fmem04_a4
    ldr     r3, 1f                  @ +4: endereço ≡ 0 (mod 4)
    str     r3, [r1, #0]
    pop     {r4, pc}
    .p2align 2
1:  .word   0x5EEDF00D
ENDF v_fmem04_a4

FUNC v_fmem04_a2
    push    {r4, lr}                @ +0
X v_fmem04_a2
    ldr     r3, 1f                  @ +2: endereço ≡ 2 (mod 4)
    str     r3, [r1, #0]
    pop     {r4, pc}
    .p2align 2
1:  .word   0x5EEDF00D
ENDF v_fmem04_a2

/* ── FMEM-05: LDM/STM (IA e DB), PUSH/POP — só combinações codificáveis.
 * A janela recebe o padrão semente + k·0x01010101 na palavra k antes das
 * cargas. Os ponteiros in/out ficam em r10/r11 (fora das listas testadas).
 * in = {semente} ── */
.macro FILLWIN                          @ c1_scratch[k] = r0[0] + k·0x01010101
    ldr     r12, =c1_scratch
    ldr     r2, [r10, #0]
    ldr     r3, =0x01010101
    str     r2, [r12, #0]
    add     r2, r2, r3
    str     r2, [r12, #4]
    add     r2, r2, r3
    str     r2, [r12, #8]
    add     r2, r2, r3
    str     r2, [r12, #12]
    add     r2, r2, r3
    str     r2, [r12, #16]
    add     r2, r2, r3
    str     r2, [r12, #20]
    add     r2, r2, r3
    str     r2, [r12, #24]
    add     r2, r2, r3
    str     r2, [r12, #28]
.endm
.macro SEEDREGS                         @ r0..r7 = semente + k·0x01010101 (só r0..r7)
    ldr     r0, [r10, #0]
    ldr     r12, =0x01010101
    add     r1, r0, r12
    add     r2, r1, r12
    add     r3, r2, r12
    add     r4, r3, r12
    add     r5, r4, r12
    add     r6, r5, r12
    add     r7, r6, r12
.endm
.macro ENTER
    push    {r4-r11, lr}
    sub     sp, sp, #4              @ 10 palavras: SP continua múltiplo de 8
    mov     r10, r0
    mov     r11, r1
.endm
.macro LEAVE
    add     sp, sp, #4
    pop     {r4-r11, pc}
.endm

@ (a) T1, 1 registrador COM writeback (a base não está na lista)
FUNC v_fmem05_ldm1
    ENTER
    FILLWIN
    ldr     r2, =c1_scratch
    mov.w   r3, #0
X v_fmem05_ldm1
    ldm     r2!, {r3}
    str     r3, [r11, #0]
    sub     r2, r2, r12
    str     r2, [r11, #4]
    LEAVE
ENDF v_fmem05_ldm1

FUNC v_fmem05_stm1
    ENTER
    ldr     r2, =c1_scratch
    mov     r12, r2
    ldr     r3, [r10, #0]
X v_fmem05_stm1
    stm     r2!, {r3}
    sub     r2, r2, r12
    str     r2, [r11, #0]
    LEAVE
ENDF v_fmem05_stm1

@ (c) {r0-r7} com e sem writeback (base r12, alta: T2)
.macro LDM8 name, insn:vararg
FUNC \name
    ENTER
    FILLWIN
    ldr     r12, =c1_scratch
X \name
    \insn
    str     r0, [r11, #0]
    str     r1, [r11, #4]
    str     r2, [r11, #8]
    str     r3, [r11, #12]
    str     r4, [r11, #16]
    str     r5, [r11, #20]
    str     r6, [r11, #24]
    str     r7, [r11, #28]
    ldr     r0, =c1_scratch
    sub     r12, r12, r0
    str     r12, [r11, #32]
    LEAVE
ENDF \name
.endm
    LDM8    v_fmem05_ldm8_wb, ldm.w r12!, {r0-r7}
    LDM8    v_fmem05_ldm8, ldm.w r12, {r0-r7}

.macro STM8 name, insn:vararg
FUNC \name
    ENTER
    SEEDREGS
    ldr     r12, =c1_scratch
X \name
    \insn
    ldr     r0, =c1_scratch
    sub     r12, r12, r0
    str     r12, [r11, #0]
    LEAVE
ENDF \name
.endm
    STM8    v_fmem05_stm8_wb, stm.w r12!, {r0-r7}
    STM8    v_fmem05_stm8, stm.w r12, {r0-r7}

@ (e) lista esparsa {r1, r3, r5, r8, r12}, base r2, com e sem writeback
.macro LDMSP name, insn:vararg
FUNC \name
    ENTER
    FILLWIN
    ldr     r2, =c1_scratch
X \name
    \insn
    str     r1, [r11, #0]
    str     r3, [r11, #4]
    str     r5, [r11, #8]
    str     r8, [r11, #12]
    str     r12, [r11, #16]
    ldr     r0, =c1_scratch
    sub     r2, r2, r0
    str     r2, [r11, #20]
    LEAVE
ENDF \name
.endm
    LDMSP   v_fmem05_ldmsp_wb, ldm.w r2!, {r1, r3, r5, r8, r12}
    LDMSP   v_fmem05_ldmsp, ldm.w r2, {r1, r3, r5, r8, r12}

.macro STMSP name, insn:vararg
FUNC \name
    ENTER
    SEEDREGS
    mov     r8, r6
    mov     r12, r7
    ldr     r2, =c1_scratch
X \name
    \insn
    ldr     r0, =c1_scratch
    sub     r2, r2, r0
    str     r2, [r11, #0]
    LEAVE
ENDF \name
.endm
    STMSP   v_fmem05_stmsp_wb, stm.w r2!, {r1, r3, r5, r8, r12}
    STMSP   v_fmem05_stmsp, stm.w r2, {r1, r3, r5, r8, r12}

@ (f) base NA lista, sem writeback: T1 e T2. A base recebe o valor carregado.
FUNC v_fmem05_ldmbase_t1
    ENTER
    FILLWIN
    ldr     r2, =c1_scratch
X v_fmem05_ldmbase_t1
    ldm     r2, {r1, r2, r3}
    str     r1, [r11, #0]
    str     r2, [r11, #4]
    str     r3, [r11, #8]
    LEAVE
ENDF v_fmem05_ldmbase_t1

FUNC v_fmem05_ldmbase_t2
    ENTER
    FILLWIN
    ldr     r2, =c1_scratch
X v_fmem05_ldmbase_t2
    ldm.w   r2, {r2, r8}
    str     r2, [r11, #0]
    str     r8, [r11, #4]
    LEAVE
ENDF v_fmem05_ldmbase_t2

@ (g) DB, base r2 = c1_scratch + 32, com e sem writeback
.macro DB_LOAD name, insn:vararg
FUNC \name
    ENTER
    FILLWIN
    ldr     r2, =c1_scratch + 32
X \name
    \insn
    str     r3, [r11, #0]
    str     r4, [r11, #4]
    ldr     r0, =c1_scratch
    sub     r2, r2, r0
    str     r2, [r11, #8]
    LEAVE
ENDF \name
.endm
    DB_LOAD v_fmem05_ldmdb_wb, ldmdb r2!, {r3, r4}
    DB_LOAD v_fmem05_ldmdb, ldmdb r2, {r3, r4}

.macro DB_STORE name, insn:vararg
FUNC \name
    ENTER
    SEEDREGS
    ldr     r2, =c1_scratch + 32
X \name
    \insn
    ldr     r0, =c1_scratch
    sub     r2, r2, r0
    str     r2, [r11, #0]
    LEAVE
ENDF \name
.endm
    DB_STORE v_fmem05_stmdb_wb, stmdb r2!, {r3, r4}
    DB_STORE v_fmem05_stmdb, stmdb r2, {r3, r4}

@ (h) PUSH/POP de 1, 4 e 8 registradores. out = {SP0 − SP1, memória [SP1..],
@ registradores depois do POP, SP2 − SP0} (n palavras em cada bloco do meio).
.macro PUSHPOP name, n, push_insn, pop_insn
FUNC \name
    ENTER
    SEEDREGS
    mov     r10, sp                 @ SP0 (o ponteiro in não é mais usado)
X \name, 0
    \push_insn
    mov     r12, sp
    sub     r12, r10, r12
    str     r12, [r11, #0]          @ SP0 − SP1
    .set k, 0
    .rept \n
    ldr     r12, [sp, #(k * 4)]
    str     r12, [r11, #(4 + k * 4)]
    .set k, k + 1
    .endr
    movs    r3, #0                  @ apaga os registradores antes do POP
    mov     r4, r3
    mov     r5, r3
    mov     r6, r3
    mov     r7, r3
X \name, 1
    \pop_insn
    .if \n == 1
    str     r3, [r11, #8]
    .else
    str     r4, [r11, #(4 + \n * 4)]
    str     r5, [r11, #(8 + \n * 4)]
    str     r6, [r11, #(12 + \n * 4)]
    str     r7, [r11, #(16 + \n * 4)]
    .endif
    sub     r12, sp, r10
    str     r12, [r11, #(4 + 2 * \n * 4)]   @ SP2 − SP0
    LEAVE
ENDF \name
.endm
    PUSHPOP v_fmem05_push1, 1, "push {r3}", "pop {r3}"
    PUSHPOP v_fmem05_push4, 4, "push {r4-r7}", "pop {r4-r7}"

@ 8 registradores {r4-r11}: r10 e r11 entram na lista, então os ponteiros
@ ficam na pilha e o SP0 é refeito pelo deslocamento.
FUNC v_fmem05_push8
    push    {r4-r11, lr}
    sub     sp, sp, #4
    str     r1, [sp, #0]            @ out na pilha (abaixo do quadro de teste)
    ldr     r0, [r0, #0]
    ldr     r12, =0x01010101
    add     r4, r0, r12
    add     r5, r4, r12
    add     r6, r5, r12
    add     r7, r6, r12
    add     r8, r7, r12
    add     r9, r8, r12
    add     r10, r9, r12
    add     r11, r10, r12
    mov     r12, sp                 @ SP0
X v_fmem05_push8, 0
    push    {r4-r11}
    mov     r0, sp
    sub     r0, r12, r0             @ SP0 − SP1 (32 esperado)
    ldr     r1, [r12, #0]           @ ponteiro out
    str     r0, [r1, #0]
    .set k, 0
    .rept 8
    ldr     r0, [sp, #(k * 4)]
    str     r0, [r1, #(4 + k * 4)]
    .set k, k + 1
    .endr
    movs    r4, #0
    mov     r5, r4
    mov     r6, r4
    mov     r7, r4
    mov     r8, r4
    mov     r9, r4
    mov     r10, r4
    mov     r11, r4
X v_fmem05_push8, 1
    pop     {r4-r11}
    str     r4, [r1, #36]
    str     r5, [r1, #40]
    str     r6, [r1, #44]
    str     r7, [r1, #48]
    str     r8, [r1, #52]
    str     r9, [r1, #56]
    str     r10, [r1, #60]
    str     r11, [r1, #64]
    sub     r0, sp, r12             @ SP2 − SP0 (0 esperado)
    str     r0, [r1, #68]
    add     sp, sp, #4
    pop     {r4-r11, pc}
ENDF v_fmem05_push8

/* ── FMEM-06: LDRD/STRD, base = c1_scratch + desvio (0 ou 4: addr mod 8 =
 * 0 e 4), base SEMPRE diferente dos registradores de dados (§A7.7.50,
 * errata 602117). in = {semente, desvio} ── */
.macro LDRDM name, insn:vararg
FUNC \name
    ENTER
    FILLWIN
    ldr     r2, [r10, #4]
    add     r2, r2, r12             @ r12 = c1_scratch (FILLWIN)
    mov.w   r3, #0
    mov.w   r4, #0
X \name
    \insn
    str     r3, [r11, #0]
    str     r4, [r11, #4]
    sub     r2, r2, r12
    str     r2, [r11, #8]
    LEAVE
ENDF \name
.endm
    LDRDM   v_fmem06_ldrd, ldrd r3, r4, [r2, #8]
    LDRDM   v_fmem06_ldrd_pre, ldrd r3, r4, [r2, #8]!
    LDRDM   v_fmem06_ldrd_post, ldrd r3, r4, [r2], #8

.macro STRDM name, insn:vararg
FUNC \name
    ENTER
    ldr     r3, [r10, #0]
    ldr     r4, =0x01010101
    add     r4, r3, r4
    ldr     r12, =c1_scratch
    ldr     r2, [r10, #4]
    add     r2, r2, r12
X \name
    \insn
    sub     r2, r2, r12
    str     r2, [r11, #0]
    LEAVE
ENDF \name
.endm
    STRDM   v_fmem06_strd, strd r3, r4, [r2, #8]
    STRDM   v_fmem06_strd_pre, strd r3, r4, [r2, #8]!
    STRDM   v_fmem06_strd_post, strd r3, r4, [r2], #8

/* ── FMEM-07: cargas de .rodata na flash (barramento DCode). c1_rom é
 * espelhado em scripts/c1/func/fmem.py (ROM). out = {5 valores} ── */
    .section .rodata.c1_rom, "a", %progbits
    .global c1_rom
    .p2align 4
c1_rom:
    .byte   0x11, 0x22, 0x33, 0x44, 0x80, 0x7F, 0xFF, 0x01
    .byte   0xA5, 0x5A, 0x00, 0x80, 0xFE, 0xDC, 0xBA, 0x98
    .size c1_rom, . - c1_rom

FUNC v_fmem07
    push    {r4, lr}
    ldr     r2, =c1_rom
X v_fmem07, 0
    ldr     r3, [r2, #4]
    str     r3, [r1, #0]
X v_fmem07, 1
    ldrb    r3, [r2, #6]
    str     r3, [r1, #4]
X v_fmem07, 2
    ldrh    r3, [r2, #10]
    str     r3, [r1, #8]
    movs    r4, #4
X v_fmem07, 3
    ldrsb   r3, [r2, r4]
    str     r3, [r1, #12]
    movs    r4, #12
X v_fmem07, 4
    ldrsh   r3, [r2, r4]
    str     r3, [r1, #16]
    pop     {r4, pc}
ENDF v_fmem07

/* ── FMEM-08: STRB em cada faixa de byte e STRH em cada metade de uma
 * palavra inicial conhecida. in = {palavra inicial, valor}  out = {palavra} ── */
.macro LANE name, insn:vararg
FUNC \name
    push    {r4, lr}
    ldr     r2, =c1_scratch + 12
    ldr     r3, [r0, #0]
    str     r3, [r2]
    ldr     r3, [r0, #4]
X \name
    \insn
    ldr     r4, [r2]
    str     r4, [r1, #0]
    pop     {r4, pc}
ENDF \name
.endm
    .irp k, 0, 1, 2, 3
    LANE    v_fmem08_strb_\k, strb r3, [r2, #\k]
    .endr
    LANE    v_fmem08_strh_0, strh r3, [r2, #0]
    LANE    v_fmem08_strh_2, strh r3, [r2, #2]
