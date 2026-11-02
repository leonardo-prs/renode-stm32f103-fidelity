cmake_minimum_required(VERSION 3.22)

# ════════════════════════════════════════════════════════════════════════════
# Renode × STM32F103 — firmwares experimentais do TCC
# ════════════════════════════════════════════════════════════════════════════
# Um preset = um firmware = uma árvore build/<preset>/firmware.elf.
#   cmake --workflow --preset c1-func
# O MESMO ELF é gravado na placa e carregado no Renode.
#
#   vendor/      ST/CMSIS/LL congelados (compilados com -w, nunca editados)
#   src/c1/      C1: núcleo e memória (startup, .ld e registro próprios)
#   src/q01/     Q-01: verificação do observador externo (só Renode, oD)
#   src/q02/     Q-02: ganchos de escrita/exceção e ações do monitor (só Renode)
#   src/c2/common, src/c2/od   C2 (interrupções): firmware #oD (só Renode)
#   lib/, inc/   registro FID3 dos cenários C2–C4 (legado deste workspace)
#   src/c2..c4/  um main por firmware (legado deste workspace)
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

set(FIRMWARES c1-func c1-layout c1-cycle q01 q02 c2-od c2 c3 c4)
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
elseif(FIRMWARE STREQUAL "q01")
    # ════════════════════════════════════════════════════════════════════
    # Q-01 — verificação do observador externo (03-quadro-comum.typ).
    # Firmware mínimo e independente do C1: startup, .ld e sequência
    # medida próprios; do vendor só os headers CMSIS.
    # ════════════════════════════════════════════════════════════════════
    add_executable(firmware src/q01/startup.S src/q01/q01.S src/q01/main.c)
    target_link_libraries(firmware PRIVATE vendor_headers)
    target_compile_options(firmware PRIVATE
        $<$<COMPILE_LANGUAGE:C>:${project_warnings} -ffreestanding>
        $<$<COMPILE_LANGUAGE:ASM>:-Wa,--fatal-warnings>
        -ffunction-sections -fdata-sections)
    target_link_options(firmware PRIVATE
        -nostartfiles -nostdlib
        "-T${CMAKE_SOURCE_DIR}/src/q01/q01.ld"
        -Wl,--gc-sections
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
    set_target_properties(firmware PROPERTIES
        LINK_DEPENDS ${CMAKE_SOURCE_DIR}/src/q01/q01.ld)
elseif(FIRMWARE STREQUAL "q02")
    # ════════════════════════════════════════════════════════════════════
    # Q-02 — instrumentos genéricos do Renode (03-quadro-comum.typ, família
    # Q). Firmware em C, só núcleo/SRAM/SCS, independente de C1 e C2; a
    # especificação em Python (scripts/q02/spec.py) gera q02_spec.h e é
    # também a referência da análise.
    # ════════════════════════════════════════════════════════════════════
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(q02_gen_dir ${CMAKE_BINARY_DIR}/gen)
    file(GLOB q02_py CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/scripts/q02/*.py)
    add_custom_command(
        OUTPUT ${q02_gen_dir}/q02_spec.h
        COMMAND ${CMAKE_COMMAND} -E env PYTHONPATH=${CMAKE_SOURCE_DIR}/scripts
                ${Python3_EXECUTABLE} -B -m q02 gen --out ${q02_gen_dir}
        DEPENDS ${q02_py}
        COMMENT "especificação do Q-02 → q02/gen/q02_spec.h"
        VERBATIM)
    add_executable(firmware src/q02/q02.c ${q02_gen_dir}/q02_spec.h)
    target_link_libraries(firmware PRIVATE vendor_headers)
    target_include_directories(firmware PRIVATE ${q02_gen_dir})
    set_source_files_properties(src/q02/q02.c PROPERTIES OBJECT_DEPENDS ${q02_gen_dir}/q02_spec.h)
    target_compile_options(firmware PRIVATE
        ${project_warnings} -Werror -ffreestanding -fno-tree-loop-distribute-patterns
        -ffunction-sections -fdata-sections)
    target_link_options(firmware PRIVATE
        -nostartfiles -nostdlib
        "-T${CMAKE_SOURCE_DIR}/src/q02/q02.ld"
        -Wl,--gc-sections -Wl,--fatal-warnings
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
    set_target_properties(firmware PROPERTIES
        LINK_DEPENDS ${CMAKE_SOURCE_DIR}/src/q02/q02.ld)
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
else()
    # ── legado C2–C4: startup/.ld do vendor + registro FID3 (lib/, inc/) ──
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

    if(FIRMWARE STREQUAL "c2")
        set(fw_sources src/c2/timers.c)
        set(fw_defs FID_MAX_CASES=64U FID_MAX_WORDS=768U FID_RING=128U)
    elseif(FIRMWARE STREQUAL "c3")
        set(fw_sources src/c3/nvic.c)
        set(fw_defs FID_MAX_CASES=32U FID_MAX_WORDS=512U FID_RING=128U)
    elseif(FIRMWARE STREQUAL "c4")
        set(fw_sources src/c4/usart.c)
        set(fw_defs FID_MAX_CASES=32U FID_MAX_WORDS=1024U FID_RING=64U)
    endif()

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
        "-T${CMAKE_SOURCE_DIR}/vendor/STM32F103XX_FLASH.ld"
        -Wl,--gc-sections
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
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
