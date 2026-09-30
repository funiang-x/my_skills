---
name: flash-jlink
description: "当需要用 SEGGER J-Link 探针烧录固件（ELF/HEX/BIN）、校验烧录结果、探测探针与工具链环境、或用 J-Link RTT 抓运行日志时使用。适用于任意带 J-Link 的 MCU 工程：脚本纯标准库，Windows/macOS/Linux 通用。烧录属设备动作——AI 动手前必须与用户确认。"
agent_created: true
---

# J-Link 烧录（含 RTT 日志）

## [MUST] 开工前置

- **烧录是设备动作：动手前先与用户确认**（哪块板、哪个产物、是否允许）。
- 先 `--detect` 确认 J-Link 工具与探针在线；找不到工具就报 `environment-missing`，**不要猜路径**。
- **不猜芯片型号**：`--device` 必须显式给（如 `STM32F407VG`），缺了就是 `ambiguous-context`。
- 烧完要验证（脚本内置 `verify`），不要把"命令跑完"说成"烧录成功"。

## 适用场景

- 已有可烧录产物（ELF/HEX/BIN），目标板连着 J-Link 探针。
- 需要 RTT 日志替代串口（不占 UART）。
- 需要探测探针列表 / 工具链路径。

## 必要输入

- `--artifact`：产物路径（ELF/HEX/BIN；BIN 必须同时给 `--base-address`）。
- `--device`：目标芯片型号（J-Link 要求，必填）。
- 可选：`--interface`（默认 SWD）、`--speed`（kHz，默认 4000）。

## 命令

```bash
S=scripts/jlink_flasher.py        # 本 skill 的执行入口（纯标准库）

python $S --detect                                          # 工具 + 探针探测
python $S --artifact build/Debug/app.elf --device STM32F407VG
python $S --artifact app.hex  --device STM32F407VG --interface SWD --speed 4000
python $S --artifact app.bin  --device STM32F407VG --base-address 0x08000000
python $S --rtt --device STM32F407VG --duration 10 --output rtt.log   # 抓 RTT 日志
```

工具查找顺序：环境变量 `JLINK_DIR` → PATH（`JLink`/`JLinkExe`）→ 默认安装目录（Windows `C:\Program Files\SEGGER`，Linux/macOS `/opt/SEGGER`、`~/SEGGER`）。

## 失败分流（退出码）

| 码 | 分类 | 怎么办 |
|---|---|---|
| 0 | 成功 | 输出内含烧录脚本与校验结果 |
| 2 | `environment-missing` | 没找到 JLink.exe / JLinkExe / JLinkRTTLogger |
| 3 | `artifact-missing` / `ambiguous-context` | 产物不存在；BIN 缺 `--base-address`；缺 `--device` |
| 4 | `connection-failure` | 探针/目标连不上：查 USB、供电、SWD 线序、`--interface`/`--speed` |
| 5 | `target-response-abnormal` | 连上了但烧录/校验/复位失败：查读写保护、供电跌落、芯片型号选错 |

## 输出约定

- 打印：工具路径、设备名、接口、速度、产物路径、执行过的 J-Link 脚本、校验结果。
- 交接：看运行日志 → `serial-monitor`（UART）或本 skill 的 `--rtt`；GDB 调试 → `debug-jlink`。