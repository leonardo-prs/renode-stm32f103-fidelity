/*
 * src/common/firmware.ld — every firmware of the project (STM32F103C8: 64 KiB
 * flash, 20 KiB SRAM).
 *
 * Vectors + code + constants in flash; .data/.bss/.noinit in SRAM; stack
 * at the top of SRAM. .noinit holds what Reset_Handler must not zero (selected_case,
 * written before boot by the Renode monitor or by OpenOCD on the board; the
 * record, valid up to record_length; sink in the instruments case). The NOLOAD
 * sections have LMA = VMA (AT> RAM) so that `sysbus LoadELF` and the flash
 * programming do not write zeros into flash.
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
    .text   : { *(.text .text.*) *(.glue_7 .glue_7t) . = ALIGN(4); } >FLASH
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

    ASSERT(_estack - _enoinit >= 0x400, "not enough SRAM for the stack")
    ASSERT(ADDR(.isr_vector) == ORIGIN(FLASH), "vector table outside the start of flash")
    ASSERT(_sbss >= _edata, ".bss overlaps .data")
}
