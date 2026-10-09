cmake_minimum_required(VERSION 3.22)

# ════════════════════════════════════════════════════════════════════════════
# Renode × STM32F103 — firmwares experimentais do TCC
# ════════════════════════════════════════════════════════════════════════════
# Um preset = um firmware = uma árvore build/<preset>/firmware.elf.
#   cmake --preset c2 && cmake --build --preset c2
# O MESMO ELF é gravado na placa e carregado no Renode.
#
#   vendor/   ST/CMSIS/LL congelados (compilados com -w, nunca editados)
#   lib/      board (clock HSI 8 MHz) + fidelity (ABI v3 de resultados/eventos)
#   src/cN/   um main por firmware
# ════════════════════════════════════════════════════════════════════════════

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)          # -std=gnu17

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type" FORCE)
endif()

project(stm32-renode-fidelity LANGUAGES C ASM)
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Otimização ÚNICA para todos os firmwares (e para o vendor): -O2 com
# símbolos completos para o GDB. Nenhum cenário muda a otimização para
# ajustar resultado; o valor também vai para o manifesto da campanha.
set(CMAKE_C_FLAGS_DEBUG "-O2 -g3")
set(CMAKE_ASM_FLAGS_DEBUG "-g3")

# ── vendor: definições, includes e fontes (congelados) ──
add_library(vendor_headers INTERFACE)
target_compile_definitions(vendor_headers INTERFACE
    STM32F103xB
    USE_FULL_LL_DRIVER
    HSE_VALUE=8000000
    HSI_VALUE=8000000
    LSE_VALUE=32768
    LSI_VALUE=40000
    HSE_STARTUP_TIMEOUT=100
    LSE_STARTUP_TIMEOUT=5000
    VDD_VALUE=3300
    PREFETCH_ENABLE=1
)
target_include_directories(vendor_headers INTERFACE
    ${CMAKE_SOURCE_DIR}/vendor/cmsis/include
    ${CMAKE_SOURCE_DIR}/vendor/cmsis/device
    ${CMAKE_SOURCE_DIR}/vendor/stm32f1xx_ll/inc
)

add_library(vendor_ll OBJECT
    vendor/system_stm32f1xx.c
    vendor/sysmem.c
    vendor/syscalls.c
    vendor/startup_stm32f103xb.s
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_gpio.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_rcc.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_utils.c
)
target_link_libraries(vendor_ll PUBLIC vendor_headers)
target_compile_options(vendor_ll PRIVATE -w)

# ── firmware escolhido pelo preset ──
set(FIRMWARES c1-functional c1-timing c2 c3 c4)
if(NOT FIRMWARE IN_LIST FIRMWARES)
    message(FATAL_ERROR
        "Defina FIRMWARE (use um preset): ${FIRMWARES}\n"
        "  cmake --preset c1-functional && cmake --build --preset c1-functional")
endif()

# Fontes e capacidades da ABI (FID_*) de cada firmware. As capacidades são
# gravadas no header do snapshot; o host nunca as presume.
if(FIRMWARE STREQUAL "c1-functional")
    set(fw_sources src/c1/functional.c)
    set(fw_defs FID_MAX_CASES=32U FID_MAX_WORDS=1536U FID_RING=128U)
elseif(FIRMWARE STREQUAL "c1-timing")
    set(fw_sources src/c1/timing.c)
    set(fw_defs FID_MAX_CASES=32U FID_MAX_WORDS=2048U FID_RING=64U)
elseif(FIRMWARE STREQUAL "c2")
    set(fw_sources src/c2/timers.c)
    set(fw_defs FID_MAX_CASES=64U FID_MAX_WORDS=768U FID_RING=128U)
elseif(FIRMWARE STREQUAL "c3")
    set(fw_sources src/c3/nvic.c)
    set(fw_defs FID_MAX_CASES=32U FID_MAX_WORDS=512U FID_RING=128U)
elseif(FIRMWARE STREQUAL "c4")
    set(fw_sources src/c4/usart.c)
    set(fw_defs FID_MAX_CASES=32U FID_MAX_WORDS=1024U FID_RING=64U)
endif()

set(project_warnings -Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes)

add_executable(firmware
    ${fw_sources}
    lib/board.c
    lib/fidelity.c
    lib/fidelity_measure.S
)
target_link_libraries(firmware PRIVATE vendor_ll vendor_headers m)
target_include_directories(firmware PRIVATE ${CMAKE_SOURCE_DIR}/lib ${CMAKE_SOURCE_DIR}/inc)
target_compile_definitions(firmware PRIVATE ${fw_defs})
target_compile_options(firmware PRIVATE
    $<$<COMPILE_LANGUAGE:C>:${project_warnings}>
    -ffunction-sections -fdata-sections)
target_link_options(firmware PRIVATE
    -Wl,--gc-sections
    "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
set_target_properties(firmware PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    ADDITIONAL_CLEAN_FILES "${CMAKE_BINARY_DIR}/firmware.map;${CMAKE_BINARY_DIR}/firmware.bin")
add_custom_command(TARGET firmware POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:firmware> "${CMAKE_BINARY_DIR}/firmware.bin"
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE:firmware>
    COMMENT "firmware.bin + tamanho (${FIRMWARE})")

# ── .clangd aponta para o compile_commands.json do último preset configurado ──
configure_file(${CMAKE_SOURCE_DIR}/cmake/clangd.in ${CMAKE_SOURCE_DIR}/.clangd @ONLY)
