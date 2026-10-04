# STM32F103 Renode Fidelity (TCC EA019)

Medir quantitativamente a fidelidade do simulador **Renode** ao hardware real
**STM32F103C8T6 Blue Pill** (ARM Cortex-M3) em firmware bare metal, dentro
de margens aceitáveis.

> **Status:** MVP. Apenas o cenário `SANDBOX` (blink LED) está implementado.
> Cenários A (TIM2 + NVIC + DWT) e B (USART1 115200 8N1) são placeholders.

---

## Pré-requisitos

- **Linux x86_64** (NixOS, Ubuntu nativo, ou WSL2 com Ubuntu).
- **Nix** (com flakes habilitados). Recomendado: [Determinate Nix][det-nix]
  — instalador mais estável que o oficial em WSL2 e empacota o daemon Nix.

  ```bash
  # Instalador recomendado (não-oficial, mantido pela Determinate Systems):
  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
  ```

  > Por que não o instalador oficial `nixos.org/nix/install`?
  > Em WSL2, o instalador oficial historicamente tem fricção com o `systemd`
  > e a integração com Windows. O [Determinate Nix][det-nix] resolve isso
  > e configura o daemon Nix corretamente para WSL2.

- **direnv** (auto-ativação do ambiente Nix ao entrar na pasta) — via `apt`:

  ```bash
  # 1. Instalar
  sudo apt update && sudo apt install -y direnv

  # 2. Hook no shell (bash) — persiste entre sessões
  #    DIRENV_LOG_FORMAT="" silencia o dump de 50+ vars ao entrar na pasta
  grep -q 'DIRENV_LOG_FORMAT' ~/.bashrc || echo 'export DIRENV_LOG_FORMAT=""' >> ~/.bashrc
  grep -q 'direnv hook bash' ~/.bashrc || echo 'eval "$(direnv hook bash)"' >> ~/.bashrc

  # 3. Ativar no shell atual (ou feche e reabra o terminal)
  export DIRENV_LOG_FORMAT=""
  eval "$(direnv hook bash)"

  # 4. Autorizar o .envrc deste projeto (uma vez por clone)
  direnv allow
  ```

  > Depois disso, basta `cd` na raiz do projeto e o shell Nix carrega
  > sozinho (banner `STM32F103 Renode Fidelity — dev shell`). Para
  > confirmar: `which arm-none-eabi-gcc` deve apontar para
  > `/nix/store/.../bin/arm-none-eabi-gcc`. Sem `direnv`, use
  > `nix develop` manualmente.

[det-nix]: https://determinate.systems/

---

## Quickstart

```bash
# 1. Entrar no ambiente — com direnv já configurado acima, é automático ao dar cd.
#    Sem direnv, entre manualmente (cria flake.lock na 1ª vez; pode demorar alguns min):
nix develop

# 2. Build do cenário sandbox (gera firmware.elf)
cmake -B build/sandbox -DSCENARIO=SANDBOX -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake
ninja -C build/sandbox

# 3. Flash no hardware (ST-Link/V2 + OpenOCD)
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \
        -c "program build/sandbox/firmware.elf verify reset exit"

# 4. Simular no Renode (mesmo ELF, sem hardware)
renode renode/sandbox.resc

# 5. Editar configuração de hardware (.ioc via CubeMX)
stm32cubemx    # GUI aparece
```

---

## Tooling (versões gerenciadas pelo flake)

| Ferramenta          | Pacote Nix                         | Função                            |
|---------------------|------------------------------------|-----------------------------------|
| `gcc-arm-embedded`  | 15.2 (C11/C17/C18/C23)             | Cross-compiler ARM                |
| `cmake`             | 4.1                                | Build system generator            |
| `ninja`             | 1.13                               | Build executor                    |
| `pkg-config`        | 0.29                               | Lib metadata                      |
| `openocd`           | 0.12                               | Flash + GDB server                |
| `arm-none-eabi-gdb` | (incluso no gcc-arm-embedded 15.2) | Source-level debug ARM            |
| `renode`            | 1.17.0                             | Simulador do MCU                  |
| `python3`           | 3.14                               | Scripts auxiliares                |
| `clang-tools`       | 22.1 (clangd, clang-tidy, …)       | LSP / análise estática            |
| `stm32cubemx`       | 6.17                               | GUI para editar `.ioc`            |

Todas vêm via `nixpkgs-unstable`, pinadas no `flake.lock`. Para atualizar:
`nix flake update --commit`.

**PATH precedence:** ao entrar em `nix develop`, o Nix prepende
`~/.nix-profile/bin` ao PATH, então qualquer binário apt em `/usr/bin` é
shadowed. Para confirmar: `which arm-none-eabi-gcc` deve apontar para
`~/.nix-profile/bin/`.

---

## WSL2 — notas de configuração

O dev primário usa WSL2 com Ubuntu. Para o Nix e para o build, WSL2 é
transparente — é Linux x86_64 comum. Pontos de atenção:

### GUI (STM32CubeMX)

WSL2 no **Windows 11** com WSLg ativo já dá suporte a GUI nativamente
(sem X server). No Windows 10, instale um X server (VcXsrv ou Xming) e
configure `DISPLAY=:0`.

Para confirmar: `stm32cubemx` deve abrir uma janela.

### ST-Link via USB

O OpenOCD precisa acessar o ST-Link via USB. No WSL2, o dispositivo USB
do host Windows precisa ser explicitamente anexado à instância WSL:

```powershell
# No PowerShell do Windows (com privilegios de admin):
# 1. Listar devices USB:
usbipd list
# 2. Anexar o ST-Link (procure por vendor 0483:3744 ou 0483:3748):
usbipd bind --busid <busid>      # uma vez
usbipd attach --wsl --busid <busid>   # cada sessão WSL
```

Para não precisar do `attach` toda vez que abrir o WSL, adicione ao
`~/.bashrc`:

```bash
# Auto-attach do ST-Link se presente
STLINK_BUSID=$(usbipd list 2>/dev/null | grep -i 'STM32 STLink' | awk '{print $1}' | head -1)
[ -n "$STLINK_BUSID" ] && usbipd attach --wsl --busid "$STLINK_BUSID" 2>/dev/null
```

(Requer `usbipd` instalado no PATH do WSL — `sudo apt install usbipd`.)

### udev rules (Linux nativo, não WSL)

Não aplicável em WSL2 (não há `udev` real). Em Linux nativo (Ubuntu,
Fedora, etc.), copie a regra uma vez:

```bash
sudo cp $(nix eval --raw nixpkgs#openocd)/etc/udev/rules.d/*.rules \
        /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

---

## Layout

```
├── flake.nix                       # Ambiente Nix (este arquivo)
├── flake.lock                      # Pinned versions (commit!)
├── CMakeLists.txt                  # Build orchestrator
├── renode-stm32f103-fidelity.ioc   # CubeMX source-of-truth
├── Core/                           # CubeMX-gerado
├── Drivers/                        # ST vendor (intocado)
├── cmake/                          # CubeMX-gerado (toolchain file)
├── src/                            # Nosso código (sandbox.c, scenario_a.c, …)
├── inc/                            # Headers do nosso código
├── lib/                            # Módulos compartilhados (sob demanda)
├── renode/                         # .repl, .resc, PLAN.md
├── scripts/                        # flash_stlink.sh, dump_sram.sh
└── docs/                           # metodologia, métricas (futuro)
```

---

## Pendente (resumo)

- Implementar cenários A (TIM2 + NVIC + DWT) e B (USART1 115200 8N1).
- Smoke test no hardware (flash + LED pisca).
- Smoke test no Renode (mesmo ELF, mesmo comportamento).
- Coletar dados comparativos HW vs Renode.
- Escrever `docs/decisoes-metricas-cenarios.md` e
  `docs/metodologia-cenario-a.md`.

Ver `AGENTS.md` para detalhes completos.
