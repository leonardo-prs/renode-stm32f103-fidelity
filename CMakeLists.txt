cmake_minimum_required(VERSION 3.22)

# ════════════════════════════════════════════════════════════════════════════
# Renode × STM32F103 — firmwares experimentais do TCC
# ════════════════════════════════════════════════════════════════════════════
# Um preset = um firmware = uma árvore build/<preset>/firmware.elf.
#   cmake --workflow --preset q
# O MESMO ELF é gravado na placa e carregado no Renode.
#
#   vendor/      ST/CMSIS congelados (só headers; nunca editados)
#   src/q/       caso Q-01: verificação dos instrumentos do Renode (só Renode)
#   src/c2/      C2, interrupções: c2.c comum + um arquivo por firmware
#                (sw.c: etapas 1–2; mon.c: etapa 3; tim.c: etapa 4)
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

set(FIRMWARES q c2-sw c2-mon c2-tim)
if(NOT FIRMWARE IN_LIST FIRMWARES)
    message(FATAL_ERROR
        "Defina FIRMWARE (use um preset): ${FIRMWARES}\n"
        "  cmake --workflow --preset q")
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

if(FIRMWARE STREQUAL "q")
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
    # C2 — interrupções (04-c2.typ), casos #oD, só Renode. Um firmware por
    # etapa (c2-sw: etapas 1–2; c2-mon: etapa 3; c2-tim: etapa 4), com
    # vetores e partida em src/c2/c2.c.
    # ════════════════════════════════════════════════════════════════════
    string(REPLACE "c2-" "" C2_FW "${FIRMWARE}")
    add_executable(firmware src/c2/c2.c src/c2/${C2_FW}.c)
    target_link_libraries(firmware PRIVATE vendor_headers)
    target_compile_options(firmware PRIVATE
        ${project_warnings} -Werror -ffreestanding -fno-tree-loop-distribute-patterns
        -ffunction-sections -fdata-sections)
    target_link_options(firmware PRIVATE
        -nostartfiles -nostdlib
        "-T${CMAKE_SOURCE_DIR}/src/c2/c2.ld"
        -Wl,--gc-sections -Wl,--fatal-warnings
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map")
    set_target_properties(firmware PROPERTIES
        LINK_DEPENDS ${CMAKE_SOURCE_DIR}/src/c2/c2.ld)
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
