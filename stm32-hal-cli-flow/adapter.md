---
name: stm32-hal
chip:
  id: stm32f4
  family: STM32F4
  core: cortex-m4
toolchain:
  compiler: arm-none-eabi-gcc
  builder: cmake+ninja
  probe: jlink
contract:
  gate_impl: Tools/fw.py
  template: templates/stm32-hal
  board_diff: 板级差异.md
  lessons: 坑册.md
capabilities:
  flash: "fw.py flash"
  reset: "fw.py reset"
  log_rtt: "fw.py rtt"
  log_uart: "fw.py build --preset Debug-UART"
  debug: "fw.py gdb"
  none_allowed: false
---

# STM32 适配层声明

> 本文件是 [`framework/适配层契约.md`](../framework/适配层契约.md) 第 1、3、4、5 项的**机器可读答复**。
> 上层解析只读本文件的 front-matter，**不引入 YAML/JSON 依赖**（按行解析，纯标准库）。

## 七项对照

| # | 契约项 | 本层答复 |
|---|---|---|
| 1 | 芯片标识 | front-matter `chip`（`stm32f4` / `STM32F4` / `cortex-m4`） |
| 2 | 工具链三元组 | front-matter `toolchain` + [`工具链.md`](工具链.md) 的探测命令表 |
| 3 | 物理能力四问 | front-matter `capabilities`（`none_allowed: false` = 六项都有实现） |
| 4 | 门禁实现位置 | `Tools/fw.py`（工程侧），6 件事的对应见 [`工具链.md`](工具链.md) §3 |
| 5 | 模板位置 | `templates/stm32-hal/`（库根） |
| 6 | 板级差异清单 | [`板级差异.md`](板级差异.md) |
| 7 | 坑册 | [`坑册.md`](坑册.md) |

## 为什么 front-matter 用这几个键

`chip` / `toolchain` / `capabilities` 三个键直接对应契约里**要机器判**的三项
（"能不能识别这颗芯片"、"工具链在不在"、"哪项能力没有"）。
其余项是**给人读的规程**，写成文档由 `ROUTE.md` 指，不进 front-matter——
不把文档塞进结构化字段，是为了让这个文件**不会因为文档改写而失效**。

## 扩展位（刻意的空白）

| 位 | 状态 |
|---|---|
| `esp32` / `nrf52` / `gd32` | **未实现**——需要时照 `framework/适配层契约.md` §3 的 7 步新增一个库根一级目录 |
| 换芯片脚本（`chip_profile.py` 类） | **不存在**，属工程侧资产；本层只承诺"改哪四处 + 判据"（见 `SKILL.md` §4） |
| IDE 路线（CubeIDE / Keil / IAR） | 不支持，本层只认 CLI 链 |
