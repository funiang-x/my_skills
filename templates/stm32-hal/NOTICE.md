# NOTICE —— 第三方组件与许可证

本目录是 STM32 四层工程的**去板级模板副本**，它**随副本携带**下列第三方组件
（源码 / 预编译库）。各组件著作权与许可证归其各自所有者；**本库自身的 MIT 许可不改变它们**。

> 核实方法：逐个目录查找 `LICENSE*` / `LICENCE*` / `COPYING*` / `NOTICE*`，
> 并**打开文件读正文**确认许可证种类。下表"证实文件"一列写的是**实际存在的路径**，
> 没有的写"没有"——**不编造文件名**。核实结果 = 全模板共 5 个许可证文件（见下表），无遗漏。

| 组件 | 路径 | 许可证 | 副本内证实的文件（已读正文） |
|---|---|---|---|
| STMicroelectronics STM32F4 HAL 驱动 | `Drivers/STM32F4xx_HAL_Driver/` | **BSD-3-Clause** | `Drivers/STM32F4xx_HAL_Driver/LICENSE.txt`（377 B；正文：*"the terms of the BSD-3-Clause license shall apply"*，并给 https://opensource.org/licenses/BSD-3-Clause 链接） |
| ARM CMSIS（Core 头 + ST 器件头） | `Drivers/CMSIS/` | **Apache-2.0** | `Drivers/CMSIS/LICENSE.txt`（11357 B，Apache License Version 2.0 **全文**）；器件目录另有一份：`Drivers/CMSIS/Device/ST/STM32F4xx/LICENSE.txt`（371 B，正文指向 Apache-2.0） |
| FreeRTOS 内核 + CMSIS-RTOS v2 适配 | `Middlewares/Third_Party/FreeRTOS/` | **MIT**（Amazon FreeRTOS） | `Middlewares/Third_Party/FreeRTOS/Source/LICENSE`（1119 B；正文首行 `Copyright (C) 2020 Amazon.com, Inc. or its affiliates.`，MIT 条款） |
| ARM CMSIS-DSP（`arm_math.h` + 预编译 `libarm_cortexM4lf_math.a`，6.4 MB） | `Middlewares/ST/ARM/DSP/` | **Apache-2.0**（旁证，见缺口 2） | ⚠️ **该目录内没有许可证文件**（只有 `Inc/` 与 `Lib/`）。同族另一份带许可证：`Middlewares/Third_Party/ARM/DSP/LICENSE.txt`（11558 B，Apache-2.0 全文） |
| SEGGER RTT | `Middlewares/RTT/` | ⚠️ **目录内没有许可证文件**（见缺口 1） | 没有 `LICENSE*` / `LICENCE*` / `COPYING*`。能证实的只有：`Middlewares/RTT/SEGGER_RTT.h` / `SEGGER_RTT.c` 头部版权声明 `(c) SEGGER Microcontroller GmbH … The Embedded Experts`，以及 `Middlewares/RTT/README.md` 第 58 行自述"版权：`(c) SEGGER Microcontroller GmbH`（源文件头部保留，符合其许可要求）" |

本库自身：**MIT** —— 许可证正文在**库根** `C:\Users\funiang\.ai-skills\LICENSE`
（首行 `MIT License`，`Copyright (c) 2026 funiang-x`）。

⚠️ 注意：**本模板目录内没有 `LICENSE` 文件**；MIT 正文在模板目录**之外**的库根。
单独把 `templates/stm32-hal/` 拷出去分发时，请一并带上库根的 MIT 许可证。

---

## 缺口（**不要当成"没问题"**）

1. **`Middlewares/RTT/` 里没有 SEGGER RTT 的许可证文件。** 全模板只找到上表那 5 个许可证文件，
   没有一个属于 SEGGER RTT。本文件**不编造文件名**：能证实的只有源文件头部的版权声明。
   ⇒ 若要把本模板**对外分发**，请从 SEGGER 官方 RTT 发行包补齐其许可证文件再分发。
2. **`Middlewares/ST/ARM/DSP/` 里没有许可证文件**，而 `CMakeLists.txt` 的 `cmsis_dsp`
   `IMPORTED_LOCATION` 指的正是这个目录（`Middlewares/ST/ARM/DSP/Lib/libarm_cortexM4lf_math.a`）。
   同源的 `Middlewares/Third_Party/ARM/DSP/LICENSE.txt` 是 Apache-2.0，但那是**另一个目录**的
   许可证，严格说不能当作前者的证明。
3. 本模板**带一块具体参考板的真实缺省值**（立创·梁山派·天空星 F407 开发板 / STM32F407VGTx）：
   `Core/Inc/board_config.h` 的引脚、时钟、容量与 `.ioc` 的器件型号都**是实际值、非占位**——
   为的是让派生出的工程**第一天就能构建、门禁 6 项全绿**（占位值会让门禁一出生就红）。
   换板子/换芯片要改哪几处见 `README.md` §11。
