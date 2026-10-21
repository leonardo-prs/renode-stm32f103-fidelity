/**
 * @file    src/c1/layout/main.c
 * @brief   C1 layout: identidade, estado de reset e layout de memória.
 *
 * Lote 0 (execução normal): FID-01..08, LAY-01..03, LAY-04 (do 1º boot),
 * LAY-05..09. Lote 1 (execução com reset por software): na fase 1 suja .data
 * e .bss, grava um marcador em .noinit e pede SYSRESETREQ; o host para em
 * main de novo, reescreve o bloco do host com C1_HOST_PHASE2, e a fase 2
 * grava LAY-04 (inicialização depois do reset) e LAY-10 (a SRAM sobreviveu?).
 * O protocolo não depende da SRAM sobreviver ao reset: isso é o que LAY-10
 * mede.
 *
 * A ordem dos registros é a de scripts/c1/layout.py (ITEMS).
 */
#include "c1.h"
#include "c1_catalog.h"

#define C1_HOST_PHASE2 (1U << 1)
#define SCB_WORD(off) (*(volatile uint32_t *)(0xE000E000U + (off)))
#define LAY_KEEP_MAGIC 0x4B454550U          /* 'K' 'E' 'E' 'P' */

uint32_t lay_probe32(uint32_t addr);
uint32_t lay_probe16(uint32_t addr);
uint32_t lay_ramfunc(uint32_t x, uint32_t *pc_out);
void lay_svc_sram(void);
volatile uint32_t lay_svc_marker;

/* LAY-04: variáveis inicializadas de 1, 2 e 4 bytes e uma estrutura, e uma
 * área de .bss que a fase 1 suja antes do reset. */
volatile uint8_t lay_d8 = 0xA5U;
volatile uint16_t lay_d16 = 0xBEEFU;
volatile uint32_t lay_d32 = 0x12345678U;
volatile struct { uint8_t a; uint32_t b; uint16_t c; } lay_ds = { 0x11U, 0x22334455U, 0x6677U };
volatile uint32_t lay_bss[16];

/* LAY-10: marcador em .noinit (não zerado pela inicialização). */
__attribute__((section(".noinit.lay_keep"))) volatile uint32_t lay_keep[6];

static void probe_put(uint32_t value)
{
    c1_put(value);
    c1_put(c1_fault.count);
    c1_put(c1_fault.cfsr);
    c1_put(c1_fault.bfar);
    c1_clear_fault();
}

static void put_layout_vars(void)
{
    c1_put(lay_d8);
    c1_put(lay_d16);
    c1_put(lay_d32);
    c1_put(lay_ds.a);
    c1_put(lay_ds.b);
    c1_put(lay_ds.c);
    uint32_t nonzero = 0U;
    for (uint32_t i = 0U; i < 16U; ++i) {
        nonzero += (lay_bss[i] != 0U);
    }
    c1_put(nonzero);
}

static void put_reset(const uint32_t *idx, uint32_t n)
{
    for (uint32_t i = 0U; i < n; ++i) {
        c1_put(c1_snapshot.header.reset[idx[i]]);
    }
}

static void svc0(void)
{
    __asm volatile("svc #0" ::: "memory");
}

static void install_sram_table(uint32_t svc_entry)
{
    volatile uint32_t *dst = _sram_vectors;
    for (uint32_t i = 0U; i < 59U; ++i) {
        dst[i] = c1_vectors[i];
    }
    dst[11] = svc_entry;
    __DSB();
}

static void batch_normal(void)
{
    uint32_t vtor0 = SCB->VTOR;
    static const uint32_t fid03[] = { 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 };
    static const uint32_t fid04[] = { 0, 1, 2, 3, 4, 5, 6 };
    static const uint32_t fid08[] = { 19, 20, 21 };   /* FLASH_ACR, RCC_CR, RCC_CFGR */

    c1_begin(LAY_FID_01);
    c1_put(SCB->CPUID);
    c1_end();

    c1_begin(LAY_FID_02);                      /* PFR0..ISAR4: 0xE000ED40..ED70 */
    for (uint32_t off = 0xD40U; off <= 0xD70U; off += 4U) {
        c1_put(SCB_WORD(off));
    }
    c1_end();

    c1_begin(LAY_FID_03);
    put_reset(fid03, 10U);
    c1_end();

    c1_begin(LAY_FID_04);
    put_reset(fid04, 7U);
    c1_end();

    c1_begin(LAY_FID_05);
    c1_put(SCB_WORD(0xD90U));                  /* MPU_TYPER */
    c1_put(SCB_WORD(0x004U));                  /* ICTR */
    c1_put(DWT->CTRL);                         /* NUMCOMP em [31:28] */
    c1_end();

    c1_begin(LAY_FID_06);                      /* F_SIZE e UID, com aterrissagem */
    probe_put(lay_probe16(0x1FFFF7E0U));
    probe_put(lay_probe32(0x1FFFF7E8U));
    probe_put(lay_probe32(0x1FFFF7ECU));
    probe_put(lay_probe32(0x1FFFF7F0U));
    c1_end();

    c1_begin(LAY_FID_07);                      /* ACTLR (não existe na r1p1) */
    probe_put(lay_probe32(0xE000E008U));
    c1_end();

    c1_begin(LAY_FID_08);                      /* relógio e flash no reset */
    put_reset(fid08, 3U);
    c1_end();

    c1_begin(LAY_LAY_01);                      /* alias de boot: 64 palavras */
    uint32_t equal = 0U;
    for (uint32_t i = 0U; i < 64U; ++i) {
        uint32_t a = lay_probe32(4U * i);
        uint32_t faulted = c1_fault.count;
        c1_clear_fault();
        equal += (faulted == 0U && a == c1_vectors[i]);
    }
    c1_put(equal);
    probe_put(lay_probe32(0x00000000U));
    probe_put(lay_probe32(0x00000004U));
    c1_end();

    c1_begin(LAY_LAY_02);
    c1_put(c1_vectors[0]);
    c1_put(c1_vectors[1]);
    c1_put(c1_snapshot.header.reset[1]);       /* SP capturado no reset */
    c1_end();

    c1_begin(LAY_LAY_03);
    volatile uint32_t local = 0U;
    const uint32_t syms[] = {
        (uint32_t)(uintptr_t)c1_vectors, (uint32_t)(uintptr_t)&_sidata,
        (uint32_t)(uintptr_t)&_sdata, (uint32_t)(uintptr_t)&_edata,
        (uint32_t)(uintptr_t)&_sbss, (uint32_t)(uintptr_t)&_ebss,
        (uint32_t)(uintptr_t)&_siramfunc, (uint32_t)(uintptr_t)&_sramfunc,
        (uint32_t)(uintptr_t)&_eramfunc, (uint32_t)(uintptr_t)&_snoinit,
        (uint32_t)(uintptr_t)&_enoinit, (uint32_t)(uintptr_t)&_estack,
    };
    for (uint32_t i = 0U; i < sizeof(syms) / sizeof(syms[0]); ++i) {
        c1_put(syms[i]);
    }
    c1_put((uint32_t)(uintptr_t)&local);
    c1_end();

    c1_begin(LAY_LAY_04);
    put_layout_vars();
    c1_end();

    c1_begin(LAY_LAY_05);
    uint32_t pc = 0U;
    c1_put(lay_ramfunc(0x1234U, &pc));
    c1_put(pc);
    c1_put((uint32_t)(uintptr_t)lay_ramfunc);
    c1_end();

    c1_begin(LAY_LAY_06);                      /* tabela realocada para a SRAM */
    lay_svc_marker = 0U;
    install_sram_table((uint32_t)(uintptr_t)lay_svc_sram);
    SCB->VTOR = (uint32_t)(uintptr_t)_sram_vectors;
    __DSB();
    __ISB();
    svc0();
    c1_put(lay_svc_marker);
    c1_put(SCB->VTOR);
    SCB->VTOR = vtor0;
    __DSB();
    __ISB();
    c1_end();

    c1_begin(LAY_LAY_07);                      /* sonda dos bits do VTOR */
    static const uint32_t probe[] = { 0xFFFFFF80U, 0x08000280U, 0x40000000U, 0x20000200U, 0U };
    uint32_t got[5];
    __disable_irq();                           /* nada pode falhar entre escrita e restauração */
    for (uint32_t i = 0U; i < 5U; ++i) {
        SCB->VTOR = probe[i];
        __DSB();
        got[i] = SCB->VTOR;
    }
    SCB->VTOR = vtor0;
    __DSB();
    __ISB();
    __enable_irq();
    for (uint32_t i = 0U; i < 5U; ++i) {
        c1_put(got[i]);
    }
    c1_end();

    for (uint32_t variant = 0U; variant < 2U; ++variant) {   /* LAY-08 (a) e (b) */
        c1_begin(variant == 0U ? LAY_LAY_08A : LAY_LAY_08B);
        lay_svc_marker = 0U;
        uint32_t entry = (uint32_t)(uintptr_t)lay_svc_sram & ~1U;   /* bit Thumb = 0 */
        install_sram_table(entry);
        if (variant == 1U) {
            SCB->SHP[7] = 0x80U;               /* SHPR2.PRI_11 = 0x80 */
        }
        c1_fault.landing = entry;              /* retoma no início do tratador */
        SCB->VTOR = (uint32_t)(uintptr_t)_sram_vectors;
        __DSB();
        __ISB();
        svc0();
        SCB->VTOR = vtor0;
        SCB->SHP[7] = 0U;
        __DSB();
        __ISB();
        c1_put(lay_svc_marker);
        c1_put_fault();
        c1_end();
    }

    c1_begin(LAY_LAY_09);                      /* endereços sem memória */
    static const uint32_t holes[] = { 0x20005000U, 0x08010000U, 0x40008000U, 0x60000000U };
    for (uint32_t i = 0U; i < 4U; ++i) {
        probe_put(lay_probe32(holes[i]));
    }
    c1_end();
}

static void batch_reset(void)
{
    if ((c1_host.flags & C1_HOST_PHASE2) == 0U) {
        /* Fase 1: suja .data e .bss, grava o marcador e pede o reset. */
        for (uint32_t i = 0U; i < 16U; ++i) {
            lay_bss[i] = 0xBADC0DE0U + i;
        }
        lay_d8 = 0U;
        lay_d16 = 0U;
        lay_d32 = 0U;
        lay_ds.b = 0U;
        for (uint32_t i = 0U; i < 4U; ++i) {
            lay_keep[i] = 0xC0DE0000U + i;
        }
        lay_keep[4] = LAY_KEEP_MAGIC;
        lay_keep[5] = c1_host.nonce;
        __DSB();
        SCB->AIRCR = (0x5FAUL << SCB_AIRCR_VECTKEY_Pos) | (SCB->AIRCR & SCB_AIRCR_PRIGROUP_Msk) |
                     SCB_AIRCR_SYSRESETREQ_Msk;
        __DSB();
        /* Espera limitada: se o reset não vier, segue para a fase 2 e os
         * registros mostram .bss suja e o marcador intacto (é o dado). */
        for (volatile uint32_t i = 0U; i < 200000U; ++i) {
        }
    }
    /* Fase 2 (ou o reset não aconteceu: o host não escreveu PHASE2). */
    c1_begin(LAY_LAY_04R);
    put_layout_vars();
    c1_end();
    c1_begin(LAY_LAY_10);                      /* padrão e marcador gravados na fase 1 */
    for (uint32_t i = 0U; i < 5U; ++i) {
        c1_put(lay_keep[i]);
    }
    c1_end();
}

int main(void)
{
    uint32_t batch = c1_host.batch;
    c1_init(C1_PRESET_LAYOUT, C1_CATALOG_HASH, batch < C1_N_BATCHES ? c1_lay_planned[batch] : 0U);
    c1_enable_fault_handlers();
    if (batch == 0U) {
        batch_normal();
    } else if (batch == 1U) {
        batch_reset();
    } else {
        c1_fail(C1_ERR_BATCH);
    }
    c1_finish();
}
