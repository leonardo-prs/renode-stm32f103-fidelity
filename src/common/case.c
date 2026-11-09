/*
 * src/common/case.c — boot, record and end of every case firmware
 * (protocol in case.h).
 */
#include "case.h"

#include "stm32f1xx.h"

extern uint32_t _sdata[], _edata[], _sidata[], _sbss[], _ebss[];

__attribute__((section(".noinit"))) volatile uint32_t selected_case;
__attribute__((section(".noinit"))) volatile uint32_t record[RECORD_CAPACITY];  /* valid up to record_length */
volatile uint32_t record_length;

/* Copies .data from flash, zeroes .bss and runs the case. main never returns;
 * if it did, the run would stop as at an unexpected exception. */
void Reset_Handler(void)
{
    const uint32_t *source = _sidata;
    for (uint32_t *destination = _sdata; destination < _edata; destination++) {
        *destination = *source++;
    }
    for (uint32_t *destination = _sbss; destination < _ebss; destination++) {
        *destination = 0U;
    }
    (void)main();
    unexpected_exception();
}

void unexpected_exception(void)
{
    for (;;) {
    }
}

void record_value(uint32_t value)
{
    uint32_t length = record_length;
    if (length < RECORD_CAPACITY) {
        record[length] = value;
        record_length = length + 1U;
    }
}

/* Only a hook point: reaching it means the record is complete. */
void record_complete(void)
{
}

/* End of the case: the hook (or breakpoint) at record_complete reads the
 * record; then the core sleeps with interrupts disabled (in Renode, virtual
 * time runs without instructions). */
void finish_case(void)
{
    __disable_irq();
    record_complete();
    for (;;) {
        __WFI();
    }
}
