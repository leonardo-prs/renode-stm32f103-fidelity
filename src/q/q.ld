/*
 * src/q/q.ld — caso Q-01 (03-quadro-comum.typ, família Q).
 *
 * Vetores + código + constantes na flash; .data/.bss/.noinit na SRAM; pilha
 * no topo da SRAM. Independente dos cenários (mesmo leiaute de src/c2/common/c2.ld).
 * .noinit guarda o que o Reset_Handler não pode zerar (q_magic, gravado
 * pelo monitor antes da partida, e q_sink, vigiado). As seções NOLOAD têm LMA = VMA
 * (AT> RAM) para o `sysbus LoadELF` não gravar zeros na flash (mesma razão
 * documentada em src/c1/common/c1.ld).
 */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 64K
    RAM   (xrw) : ORIGIN = 0x20000000, LENGTH = 20K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector ORIGIN(FLASH) : { KEEP(*(.isr_vector)) . = ALIGN(4); } >FLASH
    .text   : { *(.text .text.*) . = ALIGN(4); } >FLASH
    .rodata : { *(.rodata .rodata.*) . = ALIGN(4); } >FLASH
    .ARM.exidx : { *(.ARM.exidx* .gnu.linkonce.armexidx.*) } >FLASH

    .data : ALIGN(4)
    {
        _sdata = .;
        *(.data .data.*)
        . = ALIGN(4);
        _edata = .;
    } >RAM AT> FLASH
    _sidata = LOADADDR(.data);

    .bss (NOLOAD) : ALIGN(4)
    {
        _sbss = .;
        *(.bss .bss.*) *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } >RAM AT> RAM

    .noinit (NOLOAD) : ALIGN(4)
    {
        *(.noinit .noinit.*)
        . = ALIGN(4);
        _enoinit = .;
    } >RAM AT> RAM

    ASSERT(_estack - _enoinit >= 0x400, "Q: SRAM insuficiente para a pilha")
    .ARM.attributes 0 : { *(.ARM.attributes) }
}
