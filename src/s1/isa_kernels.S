/*
 * src/s1/isa_kernels.S — S1A: microbenchmarks por classe de instrução.
 *
 * Cada kernel: uint32_t k(uint32_t iterations, uint32_t *ctx)
 *   - corpo do laço = EXATAMENTE 16 instruções de UMA classe (.rept 16;
 *     o mix de calibração escreve as 16 explicitamente, reps=1)
 *     + SUBS/BNE de controle  → 18 instruções por iteração (K_LOOP: 2);
 *   - operandos lidos de ctx (SRAM) em tempo de execução → nada é dobrado;
 *   - retorna r2+r4+r5+r6+r7: assinatura funcional comparável HW × Renode.
 * Assembly (não C) para que o mix medido seja o escrito, independentemente
 * do compilador/-O. O gate de disassembly confere a contagem no ELF.
 *
 * ctx (uint32_t[32], SRAM, alinhado a 8):
 *   [0] &ctx[0] (auto-ponteiro p/ perseguição)   [1] a   [2] b (ímpar)
 *   [3] dividendo rápido  [4] divisor rápido  [5] dividendo lento
 *   [6] divisor lento     [7] &palavra em flash   [16..] área de STR
 */
    .syntax unified
    .cpu cortex-m3
    .thumb

    .macro KERNEL name, setup, body, section=.text, reps=16
    .section \section\().\name, "ax", %progbits
    .global \name
    .type \name, %function
    .thumb_func
    .p2align 4
\name:
    push    {r4-r7, lr}
    movs    r2, #0
    movs    r3, #0
    movs    r4, #0
    movs    r5, #0
    movs    r6, #0
    movs    r7, #0
    \setup
    .p2align 3
1:
    .rept \reps
    \body
    .endr
    subs    r0, r0, #1
    bne     1b
    adds    r0, r2, r4
    adds    r0, r0, r5
    adds    r0, r0, r6
    adds    r0, r0, r7
    pop     {r4-r7, pc}
    .size \name, . - \name
    .endm

/* Laço vazio: só SUBS/BNE (base para isolar o corpo). */
KERNEL s1k_loop,    "", ""
/* ALU 1-ciclo, cadeia dependente (r2 depende do r2 anterior). */
KERNEL s1k_alu,     "ldr r2, [r1, #4]; ldr r3, [r1, #8]", "adds r2, r2, r3"
/* MUL 32x32→32 (MULS), cadeia dependente. */
KERNEL s1k_mul,     "ldr r2, [r1, #4]; ldr r3, [r1, #8]", "muls r2, r3, r2"
/* UDIV com terminação antecipada favorável (quociente 0). */
KERNEL s1k_udiv_fast, "ldr r2, [r1, #12]; ldr r3, [r1, #16]", "udiv r4, r2, r3"
/* UDIV com quociente grande (dividendo 0xFFFFFFFF / divisor pequeno). */
KERNEL s1k_udiv_slow, "ldr r2, [r1, #20]; ldr r3, [r1, #24]", "udiv r4, r2, r3"
/* LDR SRAM independentes (candidatas a pipelining N+1). */
KERNEL s1k_ldr,     "", "ldr r4, [r1, #4]"
/* LDR SRAM dependentes: endereço = valor anterior (auto-ponteiro). */
KERNEL s1k_ldr_dep, "mov r5, r1", "ldr r5, [r5]"
/* STR SRAM. */
KERNEL s1k_str,     "ldr r2, [r1, #4]", "str r2, [r1, #64]"
/* LDR de dado em FLASH (barramento D-Code, 0 wait states a 8 MHz). */
KERNEL s1k_ldr_flash, "ldr r6, [r1, #28]", "ldr r4, [r6]"
/* Desvio incondicional tomado para a instrução seguinte. */
KERNEL s1k_branch,  "", "b 2f; 2:"
/* LDM de 4 registradores. */
KERNEL s1k_ldm,     "", "ldm r1, {r4-r7}"

/* Mix designado (CALIBRAÇÃO, congelado): 9 ALU, 3 LDR SRAM, 2 STR SRAM,
 * 1 MUL, 1 desvio tomado = 16. Sem UDIV (CPI dependente de dados). */
KERNEL s1k_mix, "ldr r2, [r1, #4]; ldr r3, [r1, #8]", \
    "adds r2, r2, r3; ldr r4, [r1, #4]; eors r2, r2, r4; str r2, [r1, #64]; muls r4, r3, r4; lsls r5, r2, #3; b 2f; 2: adds r2, r2, r5; ldr r6, [r1, #8]; subs r2, r2, r6; rors r2, r2, r3; orrs r2, r2, r4; ldr r7, [r1, #4]; str r7, [r1, #68]; adds r2, r2, r7; eors r2, r2, r3", .text, 1

/* Os mesmos corpos ALU/LDR executando a partir da SRAM (.RamFunc, copiado
 * para RAM pelo startup): busca de instrução pelo barramento System. */
KERNEL s1k_alu_ram, "ldr r2, [r1, #4]; ldr r3, [r1, #8]", "adds r2, r2, r3", .RamFunc
KERNEL s1k_ldr_ram, "", "ldr r4, [r1, #4]", .RamFunc
