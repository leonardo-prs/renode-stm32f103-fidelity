cmake_minimum_required(VERSION 3.22)

# ════════════════════════════════════════════════════════════════════════════
# STM32F103 Renode Fidelity Evaluation — CMake Root Orchestrator
# ════════════════════════════════════════════════════════════════════════════
# Arquitetura desacoplada: arquivos ST/CMSIS congelados em vendor/,
# init comum e periféricos sob demanda em lib/, e cada cenário com seu
# próprio main() em src/, compilando de forma independente e isolada.
# ════════════════════════════════════════════════════════════════════════════

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug" CACHE STRING "Build type" FORCE)
endif()

project(stm32-renode-fidelity LANGUAGES C ASM)

set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

message(STATUS "════════════════════════════════════════════════")
message(STATUS "Project    : ${CMAKE_PROJECT_NAME}")
message(STATUS "Build type : ${CMAKE_BUILD_TYPE}")
message(STATUS "════════════════════════════════════════════════")

# ── Vendor Definitions and Includes (INTERFACE) ──
add_library(vendor_headers INTERFACE)
target_compile_definitions(vendor_headers INTERFACE
    STM32F103xB
    USE_FULL_LL_DRIVER
    HSE_VALUE=8000000
    HSE_STARTUP_TIMEOUT=100
    LSE_STARTUP_TIMEOUT=5000
    LSE_VALUE=32768
    HSI_VALUE=8000000
    LSI_VALUE=40000
    VDD_VALUE=3300
    PREFETCH_ENABLE=1
    $<$<CONFIG:Debug>:DEBUG>
)
target_include_directories(vendor_headers INTERFACE
    ${CMAKE_SOURCE_DIR}/vendor/cmsis/include
    ${CMAKE_SOURCE_DIR}/vendor/cmsis/device
    ${CMAKE_SOURCE_DIR}/vendor/stm32f1xx_ll/inc
)

# ── Vendor Library (OBJECT) ──
# Contém código gerado pela ST / CMSIS / Newlib stubs com warnings desabilitados (-w).
add_library(vendor_ll OBJECT
    vendor/system_stm32f1xx.c
    vendor/sysmem.c
    vendor/syscalls.c
    vendor/startup_stm32f103xb.s
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_gpio.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_pwr.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_exti.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_tim.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_dma.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_rcc.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_utils.c
    vendor/stm32f1xx_ll/src/stm32f1xx_ll_usart.c
)
target_link_libraries(vendor_ll PUBLIC vendor_headers)
target_compile_options(vendor_ll PRIVATE -w)

# ── Board & Peripheral Support Library (OBJECT) ──
# Inicialização mínima comum (board.c) e periféricos sob demanda (periph.c).
# Compilado com flags estritos do projeto.
add_library(board OBJECT
    lib/board.c
    lib/periph.c
)
target_link_libraries(board PUBLIC vendor_headers)
target_include_directories(board PUBLIC
    ${CMAKE_SOURCE_DIR}/lib
    ${CMAKE_SOURCE_DIR}/inc
)
target_compile_options(board PRIVATE
    -Wall
    -Wextra
    -Wmissing-prototypes
    -Wstrict-prototypes
    -ffunction-sections
    -fdata-sections
)

# ── Helper para registrar cenários ──
function(add_scenario target_name source_file)
    set(extra_defs ${ARGN})
    add_executable(${target_name} ${source_file})

    target_link_libraries(${target_name} PRIVATE
        board
        vendor_ll
        m
    )
    target_include_directories(${target_name} PRIVATE
        ${CMAKE_SOURCE_DIR}/lib
        ${CMAKE_SOURCE_DIR}/inc
    )
    target_compile_options(${target_name} PRIVATE
        -Wall
        -Wextra
        -Wmissing-prototypes
        -Wstrict-prototypes
        -ffunction-sections
        -fdata-sections
    )
    if(extra_defs)
        target_compile_definitions(${target_name} PRIVATE ${extra_defs})
    endif()

    set_target_properties(${target_name} PROPERTIES
        OUTPUT_NAME "firmware"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
        ADDITIONAL_CLEAN_FILES "${CMAKE_BINARY_DIR}/firmware.map;${CMAKE_BINARY_DIR}/firmware.bin"
    )

    target_link_options(${target_name} PRIVATE
        -Wl,--gc-sections
        "-Wl,-Map=${CMAKE_BINARY_DIR}/firmware.map"
    )

    # Gera binário e exibe tamanho após o build
    add_custom_command(TARGET ${target_name} POST_BUILD
        COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${target_name}> "${CMAKE_BINARY_DIR}/firmware.bin"
        COMMAND ${CMAKE_SIZE} $<TARGET_FILE:${target_name}>
        COMMENT "Gerando firmware.bin e calculando tamanho para ${target_name}"
    )
endfunction()

# ── Registro de cenários ──────────────────────────────────────────────────
# Um preset per-cenário = UMA árvore de build (build/<cenario>/) com UM
# alvo — o firmware sai direto no buildDir (build/<cenario>/firmware.elf),
# MESMO caminho que .resc, launch.json e scripts consomem. Não existe cópia
# de sincronização nem árvore original/per-preset.
if(NOT DEFINED SCENARIO)
    message(FATAL_ERROR
        "Defina SCENARIO — use um preset per-cenário (fonte de verdade):\n"
        "  cmake --preset <cenario> && cmake --build --preset <cenario>\n"
        "  cenarios: sandbox|c1|c2|c2busy|c3|c4|echo|s1|s2|s3|s4 (ver CMakePresets.json)")
endif()

if(SCENARIO STREQUAL "SANDBOX")
    add_scenario(sandbox src/sandbox.c)
elseif(SCENARIO STREQUAL "C1")
    add_scenario(c1 src/c1_core.c TRACE_N=1536)          # 1401 emits; RAM ~59%
elseif(SCENARIO STREQUAL "C2")
    add_scenario(c2 src/c2_irq_baseline.c TRACE_N=2048)  # 2001 emits (WFI envolve: lost documentado)
elseif(SCENARIO STREQUAL "C2BUSY")
    add_scenario(c2busy src/c2_irq_baseline.c C2_BUSY_LOOP TRACE_N=2048)
elseif(SCENARIO STREQUAL "C3")
    add_scenario(c3 src/c3_irq_arbitration.c TRACE_N=1536)  # ~1210 emits; RAM ~85%
elseif(SCENARIO STREQUAL "C4")
    add_scenario(c4 src/c4_usart.c TRACE_N=1536)         # cabe em 20K (90%); wrap parcial documentado
elseif(SCENARIO STREQUAL "ECHO")
    add_scenario(echo src/echo_peer.c)
elseif(SCENARIO MATCHES "^S[1-4][A-Z]$")
    # ── Firmwares FINAIS do TCC (ABI v2, inc/fidelity.h) ──────────────────
    # Cenário N, variante X → preset sNx → build/sNx/firmware.elf. Vários
    # mains por cenário: cada firmware isola UMA pergunta experimental.
    # Otimização FIXA -O2 (declarada no manifesto do coletor): kernels cujo
    # mix de instruções importa são assembly (.S) e não dependem dela.
    set(FINAL_S1A src/s1/isa.c src/s1/isa_kernels.S)   # CPI por classe
    set(FINAL_S1B src/s1/app.c)                        # cargas C realistas
    set(FINAL_S2A src/s2/latency.c src/s2/spin.S)                 # latência IRQ + razão CPU/periférico
    set(FINAL_S2B src/s2/events.c)                     # semântica UIF/NVIC
    set(FINAL_S3A src/s3/link.c)                       # integridade/ORE
    set(FINAL_S3B src/s3/timing.c)                     # tempo de quadro
    set(FINAL_S4A src/s4/nvic.c)                       # preempção × arbitragem
    set(FINAL_S4B src/s4/race.c)                       # late-arrival/tail-chain
    # Capacidades da ABI por firmware (aplicadas também a lib/fidelity.c).
    set(FINAL_S2A_DEFS FIDELITY_ROWS=384U FIDELITY_TRACE=32U)
    set(FINAL_S3B_DEFS FIDELITY_ROWS=200U FIDELITY_TRACE=48U)
    set(FINAL_S4B_DEFS FIDELITY_ROWS=200U FIDELITY_TRACE=48U)
    if(NOT DEFINED FINAL_${SCENARIO})
        message(FATAL_ERROR "firmware final desconhecido: ${SCENARIO}")
    endif()
    string(TOLOWER "${SCENARIO}" final_target)
    set(final_opt -O2 -g3)

    add_library(fidelity OBJECT lib/fidelity.c lib/fidelity_measure.S)
    target_link_libraries(fidelity PUBLIC vendor_headers)
    target_include_directories(fidelity PUBLIC ${CMAKE_SOURCE_DIR}/inc)
    target_compile_options(fidelity PRIVATE
        $<$<COMPILE_LANGUAGE:C>:-Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes>
        -ffunction-sections -fdata-sections ${final_opt})
    if(FINAL_${SCENARIO}_DEFS)
        target_compile_definitions(fidelity PUBLIC ${FINAL_${SCENARIO}_DEFS})
    endif()
    target_compile_options(board PRIVATE ${final_opt})

    set(final_extra ${FINAL_${SCENARIO}})
    list(POP_FRONT final_extra final_main)
    add_scenario(${final_target} ${final_main})
    target_sources(${final_target} PRIVATE ${final_extra})
    target_compile_options(${final_target} PRIVATE ${final_opt})
    target_include_directories(${final_target} PRIVATE ${CMAKE_SOURCE_DIR}/src/common)
    target_link_libraries(${final_target} PRIVATE fidelity)
    # Builds de DIAGNÓSTICO (árvore separada, nunca o build oficial):
    #   cmake --preset s1a -B build/diag-x -DFINAL_DEFS="FOO=1;BAR=2"
    if(FINAL_DEFS)
        target_compile_definitions(${final_target} PRIVATE ${FINAL_DEFS})
        message(STATUS "FINAL_DEFS (diagnóstico): ${FINAL_DEFS}")
    endif()
    # Mapa de memória p/ o gate: arm-none-eabi-size + firmware.map.
elseif(SCENARIO MATCHES "^S[1-4]$")
    # Final ABI v1 support is linked ONLY into final scenarios. Exploratory
    # C1..C4 remain untouched until paired validation of their replacements.
    add_library(fidelity OBJECT lib/fidelity.c)
    target_link_libraries(fidelity PUBLIC vendor_headers)
    target_include_directories(fidelity PUBLIC ${CMAKE_SOURCE_DIR}/inc)
    target_compile_options(fidelity PRIVATE
        -Wall -Wextra -Wmissing-prototypes -Wstrict-prototypes
        -ffunction-sections -fdata-sections
    )
    if(SCENARIO STREQUAL "S1")
        add_scenario(s1 src/s1_core.c)
        set(final_target s1)
    elseif(SCENARIO STREQUAL "S2")
        add_scenario(s2 src/s2_timer_irq.c)
        set(final_target s2)
    elseif(SCENARIO STREQUAL "S3")
        add_scenario(s3 src/s3_usart.c)
        set(final_target s3)
    else()
        add_scenario(s4 src/s4_preemption.c)
        set(final_target s4)
    endif()
    target_link_libraries(${final_target} PRIVATE fidelity)
    # Parent must verify map/size: total static/runtime SRAM <=16384 bytes,
    # leaving >=4096 bytes (including stack). Vendor linker stays unchanged.
else()
    message(FATAL_ERROR
        "SCENARIO desconhecido: ${SCENARIO}\n"
        "  valores: SANDBOX|C1|C2|C2BUSY|C3|C4|ECHO|S1|S2|S3|S4 (ver CMakePresets.json)")
endif()

# ── Gera .clangd automaticamente (aponta para compile_commands.json) ──
configure_file(
    ${CMAKE_SOURCE_DIR}/cmake/clangd.in
    ${CMAKE_SOURCE_DIR}/.clangd
    @ONLY
)
