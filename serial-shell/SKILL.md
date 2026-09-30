---
name: serial-shell
description: "当需要通过串口与嵌入式设备建立交互式 Shell 会话、发单条命令看响应、或批量执行一串命令脚本时使用。支持 --send 单发 / --script 批量 / --interactive 交互；行尾符可配（crlf/lf/cr）。依赖 pyserial（唯一外部依赖，缺了会明确报环境缺失）。"
agent_created: true
---

# 串口交互 Shell

## [MUST] 开工前置

- 先确认端口（serial-monitor `--list`），**不要猜**；端口被占用就先关掉占用程序。
- 交互写操作可能改变设备状态（比如写参数、触发复位）：**对设备有副作用的命令，先与人确认**。
- 批量脚本里不要放会擦片/改保护的命令——本 skill 不做安全拦截，靠人把关。

## 适用场景

- 设备带命令行（CLI shell / bootloader 提示符），需要发命令看响应。
- 需要批跑一串命令（初始化序列、读写寄存器命令、测试用例）。
- 手动调试时想有个最简交互终端。

## 命令

```bash
S=scripts/shell_proxy.py          # 本 skill 的执行入口（依赖 pyserial）

python $S --port COM7 --send "help"                    # 单发一条
python $S --port COM7 --script cmds.txt                # 批量（逐行发，空行与 # 跳过）
python $S --port COM7 --interactive                    # 交互模式
python $S --port COM7 --baud 921600 --eol lf --send "status"
```

响应判定：每条命令后，**连续 `--timeout` 秒（默认 1.0）没有新行**即认为响应结束；

单条命令的响应最长等 `--budget` 秒（默认 10）。

## 失败分流（退出码）

| 码 | 分类 | 怎么办 |
|---|---|---|
| 0 | 成功 | — |
| 2 | `environment-missing` | 缺 pyserial：`pip install pyserial` |
| 3 | 参数问题 | 没给 `--send/--script/--interactive` 或 `--port` |
| 4 | `connection-failure` | 端口打不开：被占用 / 不存在 / 驱动缺失 |

## 交接

- 只想看日志 → `serial-monitor`（它带关键词摘要）。
- 设备崩溃/卡死 → `debug-jlink` 取证。