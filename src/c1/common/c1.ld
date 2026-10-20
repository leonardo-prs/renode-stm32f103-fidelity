/*
 * src/c1/common/c1.ld — script de ligação dos três firmwares do C1.
 *
 * STM32F103C8 (datasheet, Tab. 2): flash 64 KiB em 0x08000000 (com alias em
 * 0x00000000 no boot pela flash, RM0008 §3.4) e SRAM 20 KiB em 0x20000000.
 *
 * Seções e por que existem (os casos LAY-03 conferem todas contra o ELF):
 *
 *   .isr_vector  tabela de vetores, no início da flash (0x08000000, alinhado
 *                a 512 B: satisfaz o TRM e o PM0056, ver LAY-07)
 *   .text        código; .rodata constantes (lidas pelo DCode)
 *   .ram_vectors área de 512 B no INÍCIO da SRAM (0x20000000) para a tabela
 *                realocada de LAY-06; NOLOAD, nunca inicializada
 *   .data        VMA na SRAM, LMA na flash; copiada pelo Reset_Handler
 *   .ramfunc     código com VMA na SRAM e LMA na flash (LAY-05, T-FE-02)
 *   .bss         zerada pelo Reset_Handler
 *   .noinit      NUNCA tocada pela inicialização: captura do estado de reset
 *                (FID-03/04) e marcadores que atravessam um reset (LAY-10)
 *   .psp         pilha de processo dos casos com CONTROL.SPSEL = 1
 *   pilha (MSP)  do fim das seções até _estack (topo da SRAM); o mínimo é
 *                garantido por ASSERT
 *
 * As seções NOLOAD têm LMA = VMA (AT> RAM). Sem isso elas herdariam um LMA
 * na flash, e o `sysbus LoadELF` do Renode preenche com zeros o tamanho em
 * memória de cada segmento no endereço FÍSICO — gravaria zeros na flash,
 * depois da imagem (o OpenOCD ignora segmentos sem bytes no arquivo).
 */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 64K
    RAM   (xrw) : ORIGIN = 0x20000000, LENGTH = 20K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);
_c1_min_stack = 0x800;
_c1_psp_size  = 0x200;

SECTIONS
{
    .isr_vector ORIGIN(FLASH) :
    {
        . = ALIGN(512);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } >FLASH

    .text :
    {
        . = ALIGN(4);
        _stext = .;
        *(.text.Reset_Handler)
        *(.text .text.*)
        *(.glue_7) *(.glue_7t) *(.vfp11_veneer) *(.v4_bx)
        . = ALIGN(4);
        _etext = .;
    } >FLASH

    .rodata :
    {
        . = ALIGN(4);
        _srodata = .;
        *(.rodata .rodata.*)
        . = ALIGN(4);
        _erodata = .;
    } >FLASH

    .ARM.exidx :
    {
        *(.ARM.exidx* .gnu.linkonce.armexidx.*)
    } >FLASH

    .ram_vectors (NOLOAD) : ALIGN(512)
    {
        _sram_vectors = .;
        . = . + 0x200;
        _eram_vectors = .;
    } >RAM AT> RAM

    .data : ALIGN(4)
    {
        _sdata = .;
        *(.data .data.*)
        . = ALIGN(4);
        _edata = .;
    } >RAM AT> FLASH
    _sidata = LOADADDR(.data);

    .ramfunc : ALIGN(8)
    {
        _sramfunc = .;
        *(.ramfunc .ramfunc.*)
        . = ALIGN(4);
        _eramfunc = .;
    } >RAM AT> FLASH
    _siramfunc = LOADADDR(.ramfunc);

    .bss (NOLOAD) : ALIGN(4)
    {
        _sbss = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } >RAM AT> RAM

    .noinit (NOLOAD) : ALIGN(4)
    {
        _snoinit = .;
        *(.noinit .noinit.*)
        . = ALIGN(4);
        _enoinit = .;
    } >RAM AT> RAM

    .psp (NOLOAD) : ALIGN(8)
    {
        _spsp = .;
        . = . + _c1_psp_size;
        _epsp = .;
    } >RAM AT> RAM

    _sstack = ALIGN(8);
    ASSERT(_estack - _sstack >= _c1_min_stack, "C1: SRAM insuficiente para a pilha principal")
    ASSERT(_sram_vectors == ORIGIN(RAM), "C1: .ram_vectors precisa começar em 0x20000000 (LAY-06)")
    ASSERT(ADDR(.isr_vector) == ORIGIN(FLASH), "C1: tabela de vetores fora de 0x08000000")

    /DISCARD/ :
    {
        *(.ARM.attributes.discard)
    }

    .ARM.attributes 0 : { *(.ARM.attributes) }
}
