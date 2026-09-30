---
name: serial-monitor
description: "当需要识别正确的串口、抓取嵌入式固件的串口日志、等待某个启动/错误字符串出现、或持续监听 UART 输出并做摘要分析时使用。自动按常见 USB 串口芯片（CH340/CP210x/ST-Link/CMSIS-DAP…）挑端口，支持时间戳与存盘；缺 pyserial 时给出替代工具路径。"
agent_created: true
---

# 串口日志抓取与分析

## [MUST] 开工前置

- **端口不猜**：多个候选时**列出候选再问**，不许静默选一个（`ambiguous-context`）。
- 波特率优先级：显式 `--baud` → 工程文档/代码常量 → 默认 115200。
- 抓完要**给结论**（错误/断言/重启命中），不要只把原始文本倒给用户。
- 缺 pyserial 时先说清替代路径（PuTTY / screen），不要硬装环境。

## 适用场景

- 看启动日志、断言输出、运行期打印。
- 刚烧录/复位完，需要观察运行行为；怕错过早期日志就先开监听再复位。
- 用 `--wait "boot ok"` 自动判定启动成功/失败。

## 命令

```bash
S=scripts/serial_monitor.py       # 本 skill 的执行入口（依赖 pyserial）

python $S --list                                   # 列串口
python $S --auto --duration 10                     # 自动挑端口，抓 10 秒
python $S --port COM7 --baud 115200 --wait "boot ok" --timeout 20
python $S --port COM7 --monitor --timestamp --save run.log   # 持续监听 + 存盘
```

依赖：`pip install pyserial`（唯一外部依赖；没装时会明确报 `environment-missing` 并给替代工具）。

## 失败分流（退出码）

| 码 | 分类 | 怎么办 |
|---|---|---|
| 0 | 成功 | 输出含行数、时长与关键词命中摘要 |
| 2 | `environment-missing` | 缺 pyserial：装它，或用 PuTTY/screen 替代 |
| 3 | `ambiguous-context` | 多个候选串口 / 没给动作参数 |
| 4 | `connection-failure` | 一个串口都没有，或端口打不开（被占用、驱动缺失） |
| 5 | `wait-timeout` | `--wait` 超时没等到目标字符串 |

## 输出约定

- 给出选中的端口与波特率、实际命令、以及日志结论（错误/断言/重启等关键词命中数）。
- 日志显示崩溃/卡死/异常 → 交 `debug-jlink` 取证；需要先烧录 → `flash-jlink`。