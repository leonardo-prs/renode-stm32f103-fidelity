cmake_minimum_required(VERSION 3.22)

# ════════════════════════════════════════════════════════════════════════════
# Renode × STM32F103 — firmwares experimentais do TCC
# ════════════════════════════════════════════════════════════════════════════
# Um preset = um firmware = uma árvore build/<preset>/firmware.elf.
#   cmake --workflow --preset c1-func
# O MESMO ELF é gravado na placa e carregado no Renode.
#
#   vendor/      ST/CMSIS congelados (só headers; nunca editados)
#   src/c1/      C1: núcleo e memória (startup, .ld e registro próprios)
#   src/q/       caso Q-01: verificação dos instrumentos do Renode (só Renode)
#   src/c2/common, src/c2/od   C2 (interrupções): firmware #oD (só Renode)
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

set(FIRMWARES c1-func c1-layout c1-cycle q c2-od)
if(NOT FIRMWARE IN_LIST FIRMWARES)
    message(FATAL_ERROR
        "Defina FIRMWARE (use um preset): ${FIRMWARES}\n"
        "  cmake --workflow --preset c1-func")
endif()

# ── vendor: definições e includes (congelados) ──
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

set(project_warnings -Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes)

if(FIRMWARE MATCHES "^c1-")
    # ════════════════════════════════════════════════════════════════════
    # C1 — o firmware não usa o startup, o .ld nem o SystemInit do vendor:
    # o Reset_Handler do C1 captura o estado de reset ANTES de qualquer
    # escrita (FID-03/FID-04) e o .ld declara .ramfunc/.noinit e a área da
    # tabela de vetores na SRAM (LAY-*). Do vendor só vêm os headers CMSIS.
    #
    # As tabelas de vetores de teste, de casos temporais e de lotes são
    # GERADAS a partir do catálogo em Python (scripts/c1), que também é o
    # oráculo: o firmware e o host leem a mesma fonte.
    # ════════════════════════════════════════════════════════════════════
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    string(REPLACE "c1-" "" c1_preset "${FIRMWARE}")
    set(c1_gen_dir ${CMAKE_BINARY_DIR}/gen)
    file(GLOB_RECURSE c1_py CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/scripts/c1/*.py)
    add_custom_command(
        OUTPUT ${c1_gen_dir}/c1_catalog.h ${c1_gen_dir}/c1_config.h
        COMMAND ${CMAKE_COMMAND} -E env PYTHONPATH=${CMAKE_SOURCE_DIR}/scripts
                ${Python3_EXECUTABLE} -B -m c1 gen --preset ${FIRMWARE} --out ${c1_gen_dir}
        DEPENDS ${c1_py}
        COMMENT "catálogo do C1 → ${FIRMWARE}/gen/c1_catalog.h"
        VERBATIM)

    file(GLOB c1_preset_sources CONFIGURE_DEPENDS
        ${CMAKE_SOURCE_DIR}/src/c1/${c1_preset}/*.c
        ${CMAKE_SOURCE_DIR}/src/c1/${c1_preset}/*.S)
    add_executable(firmware
        src/c1/common/startup.S
        src/c1/common/fault.S
        src/c1/common/call.S
        src/c1/common/c1.c
        ${c1_preset_sources}
        ${c1_gen_dir}/c1_catalog.h)
    target_link_libraries(firmware PRIVATE vendor_headers)
    target_include_directories(firmware PRIVATE
        ${CMAKE_SOURCE_DIR}/src/c1/common ${c1_gen_dir})
    set_source_files_properties(${c1_preset_sources} src/c1/common/c1.c
        PROPERTIES OBJECT_DEPENDS ${c1_gen_dir}/c1_catalog.h)
    # -ffreestanding/-fno-tree-loop-distribute-patterns: laços de cópia não
    # viram chamadas a memcpy/memset (não há libc no C1).
    target_compile_options(firmware PRIVATE
        $<$<COMPILE_LANGUAGE:C>:${project_warnings} -ffreestanding -fno-tree-loop-distribute-patterns>
        $<$<COMPILE_LANGUAGE:ASM>:-Wa,--fatal-warnings>
        -ffunction-sections -fdata-sections)
    # --no-warn-rwx-segments: .ramfunc (código executado da SRAM, LAY-05 e
    # T-FE-02) divide o segmento de RAM com .data por projeto.
    target_link_options(firmware PRIVATE
        -nostartfiles -nostdlib -Wl,--no-warn-rwx-segments
        "-T${CMAKE_SOURCE_DIR}/src/c1/common/c1.ld"
        -Wl,--gc-sections
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
    target_link_libraries(firmware PRIVATE gcc)
    set_target_properties(firmware PROPERTIES
        LINK_DEPENDS ${CMAKE_SOURCE_DIR}/src/c1/common/c1.ld)
elseif(FIRMWARE STREQUAL "q")
    # ════════════════════════════════════════════════════════════════════
    # Caso Q-01 — instrumentos do Renode (03-quadro-comum.typ, família Q).
    # Um arquivo em C, só núcleo/SRAM/SCS; do vendor só os headers CMSIS.
    # ════════════════════════════════════════════════════════════════════
    add_executable(firmware src/q/q.c)
    target_link_libraries(firmware PRIVATE vendor_headers)
    target_compile_options(firmware PRIVATE
        ${project_warnings} -Werror -ffreestanding -fno-tree-loop-distribute-patterns
        -ffunction-sections -fdata-sections)
    target_link_options(firmware PRIVATE
        -nostartfiles -nostdlib
        "-T${CMAKE_SOURCE_DIR}/src/q/q.ld"
        -Wl,--gc-sections -Wl,--fatal-warnings
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
    set_target_properties(firmware PROPERTIES
        LINK_DEPENDS ${CMAKE_SOURCE_DIR}/src/q/q.ld)
elseif(FIRMWARE MATCHES "^c2-")
    # ════════════════════════════════════════════════════════════════════
    # C2 — interrupções (04-c2.typ). Startup, .ld e main comuns em C
    # (src/c2/common, sem assembly escrito); casos em src/c2/<preset>/.
    # O catálogo em Python (scripts/c2) gera c2_catalog.h e é também o
    # oráculo: firmware e host leem a mesma fonte.
    # ════════════════════════════════════════════════════════════════════
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    string(REPLACE "c2-" "" c2_preset "${FIRMWARE}")
    set(c2_gen_dir ${CMAKE_BINARY_DIR}/gen)
    file(GLOB_RECURSE c2_py CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/scripts/c2/*.py)
    add_custom_command(
        OUTPUT ${c2_gen_dir}/c2_catalog.h
        COMMAND ${CMAKE_COMMAND} -E env PYTHONPATH=${CMAKE_SOURCE_DIR}/scripts
                ${Python3_EXECUTABLE} -B -m c2 gen --out ${c2_gen_dir}
        DEPENDS ${c2_py}
        COMMENT "catálogo do C2 → ${FIRMWARE}/gen/c2_catalog.h"
        VERBATIM)
    file(GLOB c2_common_sources CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/src/c2/common/*.c)
    file(GLOB c2_preset_sources CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/src/c2/${c2_preset}/*.c)
    add_executable(firmware ${c2_common_sources} ${c2_preset_sources} ${c2_gen_dir}/c2_catalog.h)
    target_link_libraries(firmware PRIVATE vendor_headers)
    target_include_directories(firmware PRIVATE ${CMAKE_SOURCE_DIR}/src/c2/common ${c2_gen_dir})
    set_source_files_properties(${c2_common_sources} ${c2_preset_sources}
        PROPERTIES OBJECT_DEPENDS ${c2_gen_dir}/c2_catalog.h)
    # -ffreestanding/-fno-tree-loop-distribute-patterns: os laços do
    # Reset_Handler não viram chamadas a memcpy/memset (não há libc).
    target_compile_options(firmware PRIVATE
        ${project_warnings} -Werror -ffreestanding -fno-tree-loop-distribute-patterns
        -ffunction-sections -fdata-sections)
    target_link_options(firmware PRIVATE
        -nostartfiles -nostdlib
        "-T${CMAKE_SOURCE_DIR}/src/c2/common/c2.ld"
        -Wl,--gc-sections -Wl,--fatal-warnings
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
    set_target_properties(firmware PROPERTIES
        LINK_DEPENDS ${CMAKE_SOURCE_DIR}/src/c2/common/c2.ld)
endif()

set_target_properties(firmware PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    ADDITIONAL_CLEAN_FILES "${CMAKE_BINARY_DIR}/firmware.map;${CMAKE_BINARY_DIR}/firmware.bin")
add_custom_command(TARGET firmware POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:firmware> "${CMAKE_BINARY_DIR}/firmware.bin"
    COMMAND ${CMAKE_SIZE} -A $<TARGET_FILE:firmware>
    COMMENT "firmware.bin + tamanho por seção (${FIRMWARE})")

# ── .clangd aponta para o compile_commands.json do último preset configurado ──
configure_file(${CMAKE_SOURCE_DIR}/cmake/clangd.in ${CMAKE_SOURCE_DIR}/.clangd @ONLY)
