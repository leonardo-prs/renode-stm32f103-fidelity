# Cross toolchain: arm-none-eabi-gcc (gcc-arm-embedded, from the Nix shell) for a
# bare-metal Cortex-M3. CPU and code options are per firmware in CMakeLists.txt.
set(CMAKE_SYSTEM_NAME      Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_C_COMPILER   arm-none-eabi-gcc)
set(CMAKE_OBJCOPY      arm-none-eabi-objcopy)
set(CMAKE_SIZE         arm-none-eabi-size)

# No startup files or libc to link a test program with: test the compiler with a library.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
