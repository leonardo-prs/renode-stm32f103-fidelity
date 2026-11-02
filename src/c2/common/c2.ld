/*
 * src/c2/common/c2.ld — firmwares do C2 (04-c2.typ).
 *
 * Vetores + código + constantes na flash; .data/.bss/.noinit na SRAM; pilha
 * no topo da SRAM. Independente do .ld do C1 (que ainda será redesenhado).
 * .noinit guarda o bloco de parâmetros que o monitor do Renode grava antes
 * da partida: o Reset_Handler não o toca. As seções NOLOAD têm LMA = VMA
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

    ASSERT(_estack - _enoinit >= 0x400, "C2: SRAM insuficiente para a pilha")
    .ARM.attributes 0 : { *(.ARM.attributes) }
}
