# vendor/ — ARM CMSIS and STMicroelectronics headers

Frozen copies of the upstream headers: do not edit or regenerate them. Only the headers the
firmwares include, directly or through another header, are kept (the project builds with
`STM32F103xB`, so `stm32f1xx.h` includes only `stm32f103xb.h`). No vendor source is compiled; the
boot code, vector tables and linker script are the project's own (`src/common/`). Of the LL, only
the `__STATIC_INLINE` functions are used, since its `.c` files are not here.

## Origin

Every file is byte-identical to its upstream.

| Directory | Upstream | Version |
|---|---|---|
| `stm32f1xx_ll/inc/` | [`stm32f1xx-hal-driver`](https://github.com/STMicroelectronics/stm32f1xx-hal-driver) `Inc/stm32f1xx_ll_*.h` | commit `fee494a`, the one `STM32CubeF1` `v1.8.7` (`d12e752`) pins; tag `v1.1.10` (`77fbb30`) is an ancestor |
| `cmsis/include/` | [`STM32CubeF1`](https://github.com/STMicroelectronics/STM32CubeF1) `Drivers/CMSIS/Core/Include/` | tag `v1.8.7` (`d12e752`), CMSIS 5.4.0 |
| `cmsis/device/` | [`cmsis_device_f1`](https://github.com/STMicroelectronics/cmsis_device_f1) `Include/` | commit `c8e9a4a`, the one `STM32CubeF1` `v1.8.7` pins (device header 4.3.5) |

Each upstream's license is next to its files: Apache-2.0 for CMSIS (`cmsis/LICENSE.txt`,
`cmsis/device/License.md`) and BSD-3-Clause for the LL (`stm32f1xx_ll/LICENSE.md`).

## Integrity (SHA-256)

`(cd vendor && sha256sum -c)` with the list below:

```text
b40930bbcf80744c86c46a12bc9da056641d722716c378f5659b9e555ef833e1  ./cmsis/LICENSE.txt
b645e89bbfb6accf914cf7adca011712bf90055391fdd55f2af6439d98aa36d4  ./cmsis/device/License.md
d9c7c613d9fea74220892b4fbc3e80617493acad82a04bafadab2b4a7198399c  ./cmsis/device/stm32f103xb.h
05e93fa3ddefb2e83d762b9ca4de36e3bba9cd8e9690400fe9f2c11fc0a3cef5  ./cmsis/device/stm32f1xx.h
a54dfbb3480c672f532d472a6e84bcf34df6551771d2e9966c5a3503c676b6ab  ./cmsis/device/system_stm32f1xx.h
03ab80c426a8360eaaad833ac816462a9f38cb2e4dbdc490914880ad071181fe  ./cmsis/include/cmsis_compiler.h
341982e6d6c91119214c47d7a04b31f1f8ce0970c45e2c9fe0870c80d0876e28  ./cmsis/include/cmsis_gcc.h
c2570d56ee85d4f2ec0fb62f31d080d3cddf3a015500a4ed5a006a571637b43c  ./cmsis/include/cmsis_version.h
655bb08e9474438dec8b1874ea6c63749dc2787b85f06a0987c4870bcb580f21  ./cmsis/include/core_cm3.h
dff179cfe1405dc3381dc6865bf4a5173b35605b65694d73356b01aaec1f09f1  ./stm32f1xx_ll/LICENSE.md
6680693a685a8ed0d09d9c6901328ac23bb207ecc9d68e9521b66cf09c8f75a8  ./stm32f1xx_ll/inc/stm32f1xx_ll_bus.h
9f816072941e79763cbc048fe03bf803fd81bf0a0ade876d74a49be8620bfde5  ./stm32f1xx_ll/inc/stm32f1xx_ll_exti.h
c26c8e6cf44e838326a01baa73337938fce71a6e77d0670c0ad33fdc586629ae  ./stm32f1xx_ll/inc/stm32f1xx_ll_gpio.h
8f9653c499ac50a5d874c2606091b1a2fbed71aae7d25e70d9d518337d7922ed  ./stm32f1xx_ll/inc/stm32f1xx_ll_rcc.h
5506acce915aad3a1d0a93f17a07eb2c26c731808dc77c28014eef081c3824bb  ./stm32f1xx_ll/inc/stm32f1xx_ll_system.h
827944611b0f0cfa031f2a0c752bc73e173055b540fe971d3480e810dfceaa2e  ./stm32f1xx_ll/inc/stm32f1xx_ll_tim.h
```
