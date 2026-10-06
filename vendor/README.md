# Vendor: STMicroelectronics & ARM CMSIS Support Files

> **Status:** Congelado. NÃO editar manualmente. NÃO regenerar via STM32CubeMX.

Este diretório contém os arquivos de suporte de baixo nível fornecidos pela STMicroelectronics e pela ARM, congelados para garantir rastreabilidade e reprodutibilidade no TCC.

## Origem

- **Ferramenta geradora inicial:** STM32CubeMX 6.17.0 (DB.6.0.170)
- **Pacote de Firmware:** STM32Cube FW_F1 V1.8.7
- **CMSIS Core:** V5.0.8 (ARM Cortex-M3)
- **CMSIS Device STM32F1xx:** V4.3.3
- **Drivers:** STM32F1xx Low Layer (LL) Drivers (sem HAL)
- **SVD:** `svd/STM32F103.svd` — download **direto da ST** (st.com CAD
  resources, pack `STM32F1_svd_V1.2.zip`), bytes originais (CRLF, zero
  transformação). Validação cruzada: o conteúdo é **idêntico** ao archive
  `modm-io/cmsis-svd-stm32` @ `1761a45d` após normalização CRLF→LF
  (SHA-256 normalizado `ff632bd0…` = mesmo arquivo ST).

## Estrutura

- `cmsis/`: Headers de compilador, núcleo Cortex-M3 e device ST STM32F103xB.
- `stm32f1xx_ll/`: Drivers LL para barramentos, cortex, DMA, EXTI, GPIO, PWR, RCC, sistema, TIM, USART e utilitários.
- `startup_stm32f103xb.s`: Vetor de interrupções e código de inicialização do microcontrolador.
- `STM32F103XX_FLASH.ld`: Linker script para 64 KB Flash @ 0x08000000 e 20 KB SRAM @ 0x20000000.
- `system_stm32f1xx.c`: Configuração de sistema padrão da ST.
- `reference/renode-stm32f103-fidelity.ioc`: Configuração histórica de pinout do STM32CubeMX para referência documental.
- `svd/STM32F103.svd`: CMSIS-SVD do device STM32F103 (67 periféricos, incl. TIM2/USART1/GPIOC/RCC/EXTI) — consumido pelo cortex-debug/Peripheral Viewer via `svdFile` no `.vscode/launch.json`.

## Verificação de Integridade (SHA-256)

```text
e5154fa3682aa9fe8cda1bb914e8b6b510cd25a3ffccdc812d406035275aa00a  ./STM32F103XX_FLASH.ld
e03ba41d7fab20700769fe4118bab50d800cb74f990353a05d2f5fff1c228363  ./cmsis/LICENSE.txt
b616ef9c1ae02a5da902bc4a3efb48a8a3170308b30fc09bfda77ba712f49f95  ./cmsis/device/LICENSE.txt
d9c7c613d9fea74220892b4fbc3e80617493acad82a04bafadab2b4a7198399c  ./cmsis/device/stm32f103xb.h
05e93fa3ddefb2e83d762b9ca4de36e3bba9cd8e9690400fe9f2c11fc0a3cef5  ./cmsis/device/stm32f1xx.h
a54dfbb3480c672f532d472a6e84bcf34df6551771d2e9966c5a3503c676b6ab  ./cmsis/device/system_stm32f1xx.h
57b8d88cd03152f60bf74de0149ec979ae20210d86ab06e837aa69c66f27d615  ./cmsis/include/cmsis_armcc.h
da29dbad3cf27f6c86437af6bd0b302e105210742ad7a602bea51b104f1661c9  ./cmsis/include/cmsis_armclang.h
cd3cbd1c771a5252827a14c75a12e7ed975f76b9fc1577d53a74ba0e7c1af6c3  ./cmsis/include/cmsis_compiler.h
8c16d51f7884a9fc07c5cbe6f2bcd24e5e092ddc519f71d36740c2d2e2ff6a27  ./cmsis/include/cmsis_gcc.h
a600765888c69ee60cd2d01d77356902d4ae5fa98aa7e1d73703663c96b7f87a  ./cmsis/include/cmsis_iccarm.h
280b9fc8739aefa878d47e68d7adbd4908a15f98ec193cdba1a4b514133f5c34  ./cmsis/include/cmsis_version.h
368296087a925cf78133d27e0854d748605441915e0f4fece93f2f97eea68adb  ./cmsis/include/core_cm3.h
b0b6da4ec744b5f547a94e60e24b0a6ff6bb7307d3f81a83d0b7c3a64dc29326  ./cmsis/include/mpu_armv7.h
0f77a5ef82d63f05e0a10833d7ca00093856024ab42cae55df830a396d200a84  ./reference/renode-stm32f103-fidelity.ioc
a9a5fc7ed5ff617527dd98b3092830f4d17ed4bf57c99eac2c53bdb514ce138c  ./startup_stm32f103xb.s
d5a162f3eaf2b7b6762f00700017cae5695ebbdce7932fead8316448baafd9c1  ./stm32f1xx_ll/LICENSE.txt
ad55f9c1e4ffac6637fcbdbdce11ed576399798f289f3b23da73d8068eb633b8  ./stm32f1xx_ll/inc/stm32_assert.h
6680693a685a8ed0d09d9c6901328ac23bb207ecc9d68e9521b66cf09c8f75a8  ./stm32f1xx_ll/inc/stm32f1xx_ll_bus.h
e46032e4e08ce856c204f91f28018dc4ac59f4b8ea24e3bf0f5a609a4ba7bb32  ./stm32f1xx_ll/inc/stm32f1xx_ll_cortex.h
1a0eba87b8820b996098d1be8d09ab3df996845cf1c1fa5b536cbf6bce8fe16d  ./stm32f1xx_ll/inc/stm32f1xx_ll_dma.h
9f816072941e79763cbc048fe03bf803fd81bf0a0ade876d74a49be8620bfde5  ./stm32f1xx_ll/inc/stm32f1xx_ll_exti.h
d2fe5810dc0640bfc6f10be30162425d6b0004444bc40cb5d62257b6f21338fe  ./stm32f1xx_ll/inc/stm32f1xx_ll_gpio.h
4e706bc7ad93abf9e67433d7c46abf777e74d9036fa03a16380348c118b8c998  ./stm32f1xx_ll/inc/stm32f1xx_ll_pwr.h
8f9653c499ac50a5d874c2606091b1a2fbed71aae7d25e70d9d518337d7922ed  ./stm32f1xx_ll/inc/stm32f1xx_ll_rcc.h
5506acce915aad3a1d0a93f17a07eb2c26c731808dc77c28014eef081c3824bb  ./stm32f1xx_ll/inc/stm32f1xx_ll_system.h
3400329643cad2343f8c357788d5689e8b8db861bd0b1ef953537b45a0e56875  ./stm32f1xx_ll/inc/stm32f1xx_ll_tim.h
8684e487827c318256ba7ae36841bd2c7fa2438c0cc5c8aa36b555f607873e77  ./stm32f1xx_ll/inc/stm32f1xx_ll_usart.h
decb7156d26dc56db7ed76c06c71533ca579905b80824b178749a03a2f224a1b  ./stm32f1xx_ll/inc/stm32f1xx_ll_utils.h
7561a0ac6e58c6b68e9fa72115c3aa63ad1dcae97cd13e40569e9882fc921915  ./stm32f1xx_ll/src/stm32f1xx_ll_dma.c
4459a3a593b0afe533151a222a6572c91e604bbc4b13fe7560d483538d97320a  ./stm32f1xx_ll/src/stm32f1xx_ll_exti.c
28d81b691b2b7fed7cebafc599d0c54f2de84b7451db5af396e7153f760cfcb5  ./stm32f1xx_ll/src/stm32f1xx_ll_gpio.c
ddf15b387ef4f9272046317489edc5fcfd73fb27d19b61c496462e413470d3c9  ./stm32f1xx_ll/src/stm32f1xx_ll_pwr.c
3ec8d87fd11c285e9dd6a85633717f67df668191e26c93bd8de0bc90f79c178c  ./stm32f1xx_ll/src/stm32f1xx_ll_rcc.c
05db6c31e77f6035650f2d71a6d31150e80dd4a4517a161f64d3b0fe3d7638ad  ./stm32f1xx_ll/src/stm32f1xx_ll_tim.c
bffafc271e7ab52d3ec58c98c264548a2052598fb26ee4fbac514ede4d6c71ab  ./stm32f1xx_ll/src/stm32f1xx_ll_usart.c
fc35a6b8b3faac3960b25a3431eaca1d7deb7c8ef19ecf6f8db5ec15b5efea7f  ./stm32f1xx_ll/src/stm32f1xx_ll_utils.c
da80e14faeb94188af3024a59eae487567de2701f1531c715e7a1fa936d5f5ed  ./svd/STM32F103.svd
6f13b57054f33b4dcb8f3f23fa05b2942d9dca8abd9a2a08ecde6f99693505a5  ./system_stm32f1xx.c
```
