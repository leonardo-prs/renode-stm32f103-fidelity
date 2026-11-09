cmake_minimum_required(VERSION 3.22)

# ════════════════════════════════════════════════════════════════════════════
# Renode × STM32F103 — TCC experimental firmwares
# ════════════════════════════════════════════════════════════════════════════
# One build tree builds every firmware; each one is build/<fw>/firmware.elf
# (+ .bin and .map). The SAME ELF is flashed to the board and loaded in Renode.
#   cmake -B build -G Ninja
#   cmake --build build                  # all firmwares
#   cmake --build build --target c3      # one firmware
#
#   vendor/      frozen CMSIS and STM32 LL headers (never edited)
#   src/common/  protocol common to every firmware: boot, fault, case selection,
#                record and end (case.c/case.h) and the linker script
#   src/instruments/  verification of the Renode instruments (Renode only)
#   src/c1/      C1, the core: arithmetic, conversions, memory, ruler, cost (c1.c)
#   src/c2/      C2, interrupts and timer (c2.c)
#   src/c3/      C3, GPIO and EXTI: pins, EXTI0 handler and cases (c3.c)
#   src/c4/      C4, serial: link USART2 → USART3 (c4.c)
# ════════════════════════════════════════════════════════════════════════════

if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
    set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/cmake/gcc-arm-none-eabi.cmake")
endif()

project(stm32-renode-fidelity LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)          # -std=gnu17
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# SINGLE optimization for every firmware: -O2 with full symbols (add_firmware).
# No build type adds flags of its own: no scenario changes the optimization.
foreach(config DEBUG RELEASE RELWITHDEBINFO MINSIZEREL)
    set(CMAKE_C_FLAGS_${config} "")
endforeach()

# vendor: device and include directories (frozen headers; SYSTEM = the project
# warnings below do not apply to them)
add_library(vendor_headers INTERFACE)
target_compile_definitions(vendor_headers INTERFACE STM32F103xB)
target_include_directories(vendor_headers SYSTEM INTERFACE
    ${CMAKE_SOURCE_DIR}/vendor/cmsis/include
    ${CMAKE_SOURCE_DIR}/vendor/cmsis/device
    ${CMAKE_SOURCE_DIR}/vendor/stm32f1xx_ll/inc)

# Protocol common to every case firmware (case selection, record, end, boot).
add_library(common_case INTERFACE)
target_include_directories(common_case INTERFACE ${CMAKE_SOURCE_DIR}/src/common)

# Project warnings. With -Werror, any implicit conversion, shadowing or
# undefined macro in #if breaks the build. -Wpedantic is left out on purpose:
# c2.c uses two GNU extensions (range initializer [a ... b] and
# pointer-to-function cast).
set(project_warnings
    -Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes
    -Wshadow -Wundef -Wformat=2 -Wconversion -Wsign-conversion
    -Wcast-qual -Wdouble-promotion -Werror)

# Link: no libc and no startup files (src/common/case.c is the boot code);
# --fatal-warnings; --print-memory-usage records Flash/RAM.
set(project_link_options
    -nostartfiles -nostdlib
    -Wl,--gc-sections -Wl,--fatal-warnings -Wl,--print-memory-usage)

# add_firmware(<name> <sources>...): build/<name>/firmware.elf, .bin and .map,
# with src/common/case.c and src/common/firmware.ld.
function(add_firmware name)
    set(out "${CMAKE_BINARY_DIR}/${name}")
    add_executable(${name} src/common/case.c ${ARGN})
    target_link_libraries(${name} PRIVATE vendor_headers common_case)
    target_compile_options(${name} PRIVATE
        -mcpu=cortex-m3 -mthumb -O2 -g3 ${project_warnings}
        -ffreestanding -fno-tree-loop-distribute-patterns
        -ffunction-sections -fdata-sections -fstack-usage
        "-ffile-prefix-map=${CMAKE_SOURCE_DIR}=.")     # same source, same ELF SHA-256 in any checkout (build tree at build/)
    target_link_options(${name} PRIVATE
        -mcpu=cortex-m3 -mthumb ${project_link_options}
        "-T${CMAKE_SOURCE_DIR}/src/common/firmware.ld"
        "-Wl,-Map=${out}/firmware.map")
    set_target_properties(${name} PROPERTIES
        OUTPUT_NAME firmware
        SUFFIX .elf
        RUNTIME_OUTPUT_DIRECTORY "${out}"
        LINK_DEPENDS "${CMAKE_SOURCE_DIR}/src/common/firmware.ld"
        ADDITIONAL_CLEAN_FILES "${out}/firmware.map;${out}/firmware.bin")
    add_custom_command(TARGET ${name} POST_BUILD
        COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${name}> "${out}/firmware.bin"
        COMMAND ${CMAKE_SIZE} -A $<TARGET_FILE:${name}>
        COMMENT "${name}: firmware.bin + size per section")
endfunction()

add_firmware(instruments src/instruments/instruments.c)  # verification of the Renode instruments (Renode only)
add_firmware(c1       src/c1/c1.c)                    # C1, the core (Renode and board, no wire)
add_firmware(c2       src/c2/c2.c)                    # C2, interrupts and timer (Renode; board for C2-07 and C2-10 to C2-13; no wire)
add_firmware(c3       src/c3/c3.c)                    # C3, links L2, L3 and L4 (Renode; board for C3-06 and C3-07)
add_firmware(c4       src/c4/c4.c)                    # C4, link L1 PA2 → PB11 (Renode and board)
