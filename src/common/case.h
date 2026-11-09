/*
 * src/common/case.h — protocol common to the case firmwares.
 *
 * A firmware runs one case per boot. Before boot, the Renode monitor (or
 * OpenOCD on the board) writes the case number to selected_case, which
 * Reset_Handler does not touch (.noinit). The firmware appends what it saw to
 * the record with record_value() and ends with finish_case(), which calls
 * record_complete(): the Renode hook, or the breakpoint on the board, stops
 * there and reads record[0..record_length). Any unexpected exception goes to
 * unexpected_exception(), which loops on itself (the run cannot be analyzed
 * and is run again).
 */
#ifndef CASE_H
#define CASE_H

#include <stdint.h>

#define RECORD_CAPACITY 4608U   /* words of record */

extern volatile uint32_t selected_case;
extern volatile uint32_t record[RECORD_CAPACITY];
extern volatile uint32_t record_length;

int main(void);
__attribute__((noreturn)) void Reset_Handler(void);
__attribute__((noipa, noreturn)) void unexpected_exception(void);
__attribute__((noipa)) void record_complete(void);
__attribute__((noreturn)) void finish_case(void);
void record_value(uint32_t value);

#endif
