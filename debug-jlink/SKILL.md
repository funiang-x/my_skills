---
name: debug-jlink
description: "当需要通过 J-Link GDB Server + GDB 检查目标现场（寄存器、栈回溯、变量）、附着在线调试、或前台启动 GDB Server 供 IDE/手动 gdb 连接时使用。适用于崩溃/卡死取证：拿到寄存器现场与调用栈，把结论写成可复现的判据。纯标准库脚本，Windows/macOS/Linux 通用。"
agent_created: true
---

# J-Link GDB 调试 / 现场取证

## [MUST] 开工前置

- 先有**稳定日志通道**再谈取证（serial-monitor 或 flash-jlink --rtt）；否则连"跑到哪一步"都不知道。
- **附着会改变目标运行态**（halt/单步）：动手前与用户确认这是在调板子、不是产线在用。
- 取证要出**可复现的判据**（寄存器值 + 栈回溯 + 复现步骤），不要停在"看起来是这里"。
- 芯片型号 `--device` 必填；GDB Server 与 GDB 都要先在位（先 `--detect`）。

## 适用场景

- 固件崩了/卡死：抓 PC/LR/SP 等寄存器与调用栈（`bt`）。
- 需要在线单步、断点（起 `--server-only`，用 IDE 或 gdb 连）。
- 烧录/串口流程显示需要进一步看内部状态。

## 命令

```bash
S=scripts/jlink_debugger.py       # 本 skill 的执行入口（纯标准库）

python $S --detect                                            # 探测 Server + GDB
python $S --device STM32F407VG --artifact build/Debug/app.elf \
    --cmd "info registers" --cmd "bt" --cmd "x/16xw 0x20000000"   # 批量取证
python $S --device STM32F407VG --server-only                  # 前台起 Server（端口 2331）
python $S --device STM32F407VG --artifact app.elf --gdb "C:/path/to/arm-none-eabi-gdb.exe"
```

默认命令是 `info registers` + `bt`（最容易定位卡死/崩溃现场的两条）。执行完自动 `detach`，目标继续跑。

## 失败分流（退出码）

| 码 | 分类 | 怎么办 |
|---|---|---|
| 0 | 成功 | gdb 输出即现场证据 |
| 2 | `environment-missing` | 缺 JLinkGDBServerCL 或 arm-none-eabi-gdb（`--gdb` 可指定路径） |
| 3 | `ambiguous-context` | 缺 `--device` |
| 4 | `connection-failure` | 端口没起来：探针/目标连不上，或端口被别处占用 |
| 5 | `target-response-abnormal` | 连上了但 gdb 命令报错（看原始输出） |

## 交接

- 看日志 → `serial-monitor`（UART）或 `flash-jlink --rtt`。
- 需要重新烧录 → `flash-jlink`；需要重新构建 → `build-cmake`。