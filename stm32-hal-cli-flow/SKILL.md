---
name: "stm32-hal-cli-flow"
description: "STM32 HAL 四层工程（Task / Operation / Device / Common，Tools/fw.py + CMakePresets + J-Link + SEGGER RTT + CubeMX）的构建 / 烧录 / RTT 日志 / 固件体积 / PC 单测 / 闭环验证 / 门禁流程。触发条件：工程根同时存在 Tools/fw.py 与 CMakePresets.json，且要求编译、构建、烧录、看日志、查体积、跑单测、闭环验证、清理 build/、派生新工程、换芯片。禁止误用 st-flash / STM32_Programmer_CLI / openocd / ST-Link。"
agent_created: true
---

# STM32 适配层 —— 骨架 / 适配层 / 项目层 中的中间那层

> 本目录是 [`framework/适配层契约.md`](../framework/适配层契约.md) 的**唯一实现**。
> 它只讲**STM32 特有**的东西；芯片无关的部分（阶段 / 交付物 / 契约 / 状态 / AI 边界）
> 在 [`framework/`](../framework/) 与 [`ROUTE.md`](../ROUTE.md)、[`WORKFLOW.md`](../WORKFLOW.md)。

## 0. 这份 skill 之前是错的 —— 先修事实

2026-10 逐条核实（对着模板实物 `f407vgt6` 的 `Tools/` 与 `docs/`）：

| 本文档旧版引用 | 实测 | 处置 |
|---|---|---|
| `Tools/new_project.py` | **不存在** | 真名是 `Tools/derive.py` |
| `Tools/chip_profile.py` | **不存在** | 换芯片**没有脚本**——这是本层的头号缺口（见 §4） |
| `Tools/cmx_apply.py` | **不存在** | 真名是 `Tools/cubemx_sync.py` |
| `Tools/cmx_gen.py` | **不存在** | 真名是 `Tools/cubemx_gen.py` |
| `Tools/fetch_deps.py` | **不存在** | 依赖体检在 `fw.py env` 里 |
| `Tools/new_peripheral.py` | **不存在** | 加外设目前**没有脚本** |
| `docs/guides/*.md`（5 份） | **不存在**（该目录只有 `README.md`） | 别照旧文档找，会白跑 |

**教训**：`check_doc_links.py` 只扫 `.md`/`.txt`，**管不到 skill 文件**——所以 skill 里写了
不存在的路径，任何门禁都不会报。凡是引用路径，**先 `Test-Path` 再引用**。

## 1. 先确认是不是这套工程

工程根**同时**存在 → 用本 skill：

- `Tools/fw.py`（一体化入口）
- `Task/` + `Operation/` + `Device/` + `Common/` 四层业务目录
- `CMakePresets.json`
- `project_config.h`（数量 / 阈值 / 开关）
- `AGENTS.md`（工程侧硬约束，**优先级高于本文件**）

任一项缺失 → 不是这套工程，别硬套（套错命令会烧错文件或读不到日志）。

## 2. 铁律

| # | 规则 | 原因 |
|---|------|------|
| 1 | **只用 J-Link + SEGGER RTT**。禁用 `st-flash` / `STM32_Programmer_CLI` / `openocd` / `st-info` | 探针路径、产物名、RTT 通道全收敛在 `fw.py`；ST-Link 路线是另一套脚本与判据，混用会烧错文件或拿不到日志 |
| 2 | 硬件动作一律走 `python Tools/fw.py <子命令>` | 别在临时脚本里散落绝对路径 |
| 3 | 体积只认 `fw.py size` | `arm-none-eabi-size` 的 section 求和 ≠ 真实占用（有 ALIGN 间隙、`.data` 初值在 Flash） |
| 4 | 改善后**零告警**是硬指标，禁止新增 `-Wno-*` | 见工程侧 `AGENTS.md` |
| 5 | 动了 `Core/Inc/board_config.h` 的引脚/时钟 → **必须让人重新上板验证** | AI 判断不了硬件接线 |
| 6 | `clean` 只允许动 `build/` | 绝不能碰 `Drivers/`、源码、用户目录 |
| 7 | **调 `fw.py` 前先设 `PYTHONIOENCODING=utf-8`** | 见 §3.3，不设必崩 |

## 3. 工具链与调用约定

### 3.1 工具链（本机实测，2026-10）

| 件 | 路径 | 状态 |
|---|---|---|
| 编译器 | `C:\Program Files\Compiler\arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi\bin\arm-none-eabi-gcc.exe` | 在 |
| 构建器 | `C:\Program Files\CMake\bin\cmake.exe` + `C:\msys64\ucrt64\bin\ninja.exe` | 在 |
| 探针工具包 | `C:\Program Files\SEGGER\JLink_V936\`（`JLink.exe` / `JLinkRTTLogger.exe` / `JLinkGDBServerCL.exe`） | 在 |
| python | `C:\Python314\python.exe` | 在 |
| `STM32_Programmer_CLI` | — | **缺**（不需要，本链不用它） |
| `idf.py` | — | 缺（ESP32 用，与本层无关） |

**依赖不猜路径**：`fw.py env` 才是唯一判据。上面这张表是**缓存**，过期就以 `fw.py env` 为准。

### 3.2 四问：物理能力（本层对契约第 3 项的答复）

| 能力 | 命令 | 没有时 |
|---|---|---|
| 烧录 | `fw.py flash`（J-Link SWD 4 MHz） | 转人工：输出命令给人手跑 |
| 复位 | `fw.py reset`（只复位，不烧不擦） | 同上 |
| 日志 | `fw.py rtt --channel 0`（RTT） | **降级**：`--preset Debug-UART` 走 USART1（引脚在 `board_config.h`），用串口抓 |
| 调试 | `fw.py gdb`（`JLinkGDBServerCL` + `arm-none-eabi-gdb`） | 只用日志取证，不承诺寄存器现场 |

### 3.3 调用 fw.py 的固定写法（**踩过的坑**）

```powershell
$env:PYTHONIOENCODING='utf-8'; python Tools/fw.py <子命令>
```

**为什么**：`fw.py` 输出含 `⇒` 等非 GBK 字符，GBK 控制台下抛
`UnicodeEncodeError` 直接崩（实测 `fw.py env` 必崩）——**症状看起来像"门禁失败"，
其实是编码问题**。AI 的 shell 默认就是 GBK 码页，所以这条不是可选提示。

**要结论就读退出码，不要读输出措辞。**

## 4. 换芯片（本层最大的缺口，如实标出）

**现状：没有换芯片脚本。** `Tools/derive.py` 只做**同板派生**（复制 + 改名 + 重开 git），
它的文件头自己写明了："换芯片还要动链接脚本、启动文件、`.ioc` 型号、`board_config.h` 的容量与引脚"。

换芯片时**必须同步的四处**（照着做，别漏）：

| # | 改哪 | 判据 |
|---|---|---|
| 1 | 链接脚本（`*.ld` 的 MEMORY 段 + 段布局） | 容量数字**从 CubeMX 固件包的官方 `.ld` 现读**，不凭记忆 |
| 2 | 启动文件（`startup_<device>.s`） | 文件名与器件一致，且被 CMake 引到 |
| 3 | `.ioc` 的芯片型号 | 用 CubeMX 打开不报型号不符 |
| 4 | `Core/Inc/board_config.h` 的器件名 / 容量 / 引脚 | `fw.py lint` 对账通过（这是唯一权威判据） |
| + | 清 `build/` | `LINKER_SCRIPT` 是 CMake CACHE 变量，不清会**沿用旧内存布局**——芯片名变了、链接脚本没变、编译照样过（**假成功**） |

**判定"切换是否真生效"**：看配置输出里的芯片名与构建日志里编的启动文件。
⚠️ **不要只看 `fw.py size` 的内存数字**——同容量芯片之间可能逐字段完全相同（F405RG 与 F407VG
的 ROM/RAM/CCM 三项一模一样），数字没变 ≠ 切换失败。

**想补这个缺口**：新增 `Tools/chip_profile.py` 之类，但它是**工程侧资产**，不归本库。
本层只承诺"换芯片要改哪四处 + 判据是什么"。

## 5. 命令表（**只列实测存在的**）

| 用途 | 命令 |
|---|---|
| 环境体检（工具链 / 依赖源码 / J-Link / 各预设） | `fw.py env` |
| 编译（缺 cache 时自动先 configure） | `fw.py build` / `--preset Release` / `--preset Debug-UART` |
| 零告警口径 | `fw.py build --clean-first`（每个预设都要） |
| PC 侧单测（**不用板子**，秒级） | `fw.py test` |
| 配置对账（`.ioc` ↔ `board_config.h`） | `fw.py lint` |
| 文档死链 | `fw.py doccheck` |
| 体积 / 体积门禁 | `fw.py size` / `fw.py sizecheck` |
| 门禁自检（注入真违规，证明检查器会报错） | `fw.py selftest` |
| 烧录 / 复位 / 抓 RTT / 调试 | `fw.py flash` / `reset` / `rtt` / `gdb` |
| 闭环（门禁 → 烧录 → 抓 RTT → 判标记） | `fw.py verify` |
| 清理 | `fw.py clean` |
| 同板派生新工程（复制 + 改名 + 新 git） | `python Tools/derive.py <名字>`（`--verify` 派生后立刻 build+test） |
| CubeMX 生成 | `python Tools/cubemx_gen.py`（可选，手点 GUI 一样） |
| CubeMX 生成物搬进工程 | `python Tools/cubemx_sync.py [--write]`（默认只预览） |
| `.ioc` 工具 | `Tools/ioc_append.py` / `ioc_drop.py` / `ioc_pinlabels.py` / `ioc_common.py` |

**退出码**（以 `fw.py` 为准）：`0` 通过 · `1` 固件报 `[AI_FAIL]` · `2` 超时/无标记（**先看探针插没插**）·
`3` 编译失败 · `4` 烧录失败 · `5` RTT 抓不到 · `6` 环境不完整 · `7` 静态检查未过 · `8` 资源超预算。

## 6. 改完代码的固定顺序

```
test → lint → Debug 构建 → （改了 Device/Core 再加）Release 构建 → sizecheck → verify
```

`test` 最便宜（秒级、不用板子）⇒ **先跑它**。业务逻辑的错误应该在这一步抓完，别留到烧板之后——
那是四层结构存在的唯一理由。双预设都要过：`-Os` 与 `-Og` 下告警各不相同。

## 7. 四层边界（AI 往哪写）

```
Task/         调度：只管"什么时候做"。唯一能同时用 RTOS / Device / Operation 的层
Operation/    纯逻辑：吃数字吐数字。禁 HAL / 禁 FreeRTOS / 禁延时（时间由参数传入）
Device/       硬件：唯一直接调 HAL 的层。句柄 static 在 .c 内，.h 不外泄 HAL 类型
Common/       日志 + 错误码。零依赖，MCU 与 PC 两侧各一份实现
Core/         CubeMX 生成（只写 USER CODE BEGIN/END 之间）
project_config.h  数量 / 阈值 / 开关（工程根）
```

**规矩靠 CMake 强制**：`operation` 目标只链 `common`，拿不到 HAL/FreeRTOS 的 include 路径 ⇒
在 Operation 里 include HAL 或调 `vTaskDelay` **直接编译失败**。

**本层头号坑**：`.ioc` 里没配的外设，其 HAL 模块宏不会开 ⇒ 用到就报
`unknown type name 'Xxx_HandleTypeDef'`（**编译期**）。修法是去 CubeMX 加该外设，
**不是手改 `Core/Inc/stm32f4xx_hal_conf.h`**（生成物，下次生成会覆盖）。

## 8. 为什么**不**收编 `embedded_ai_skills/stm32`

那套三件（`stm32-dev-setup` / `stm32-project-init` / `stm32-debug`）2026-10 逐条核实后**决定不收编**，
理由是可复核的：

| 它假设 | 本机实际 | 后果 |
|---|---|---|
| MSYS2 环境（`uname -s` 检测，不在就引导装 MSYS2 + `pacman`） | 原生 Windows，工具链在 `C:\Program Files\` | 会诱导 AI 装**第二套**工具链 |
| `~/stm32-tools/stm32-cmake`（第三方 CMake 工具链文件） | 本工程自带 `cmake/gcc-arm-none-eabi.cmake` | 引入第二套构建配置 |
| `st-info --probe` + 串口调试（ST-Link 路线） | J-Link + RTT | 与铁律 1 直接冲突 |
| 从 `kukucaiCndy/embedded_ai_skills` 现 clone | 正本在本地共享库 | 多一个网络依赖 |

**唯一吸收的一条**：环境探测要「**报缺失 + 给安装指引，绝不猜路径**」——已落在 §3.1 与本库
`ROUTE.md` §2.7。其余**明确不收**：收进来会让"该用哪套"重新变成不确定的事，
正是本次改造要消除的东西。

## 9. 模板：`templates/stm32-hal/`

派生新工程：

```powershell
$env:PYTHONIOENCODING='utf-8'
cd <库>/templates/stm32-hal
python Tools/derive.py <新工程名> --dest <父目录> --verify
```

`--verify` 派生后立刻跑 build + test，**退出码 0 = 新工程可用**。其它开关：`--no-git`、`--dest`。

### ⚠️ 模板带的是**具体缺省值**，不是占位符

引脚 / 时钟 / 容量是参考板（STM32F407VGTx）的**真实值**，`.ioc` 的芯片字段也是真值
（CubeMX 能直接打开）。**换板子就改这些值，别改回占位。**

为什么不是占位：本库的[工程契约](../framework/工程契约.md)要求「派生出的工程**首次构建零告警 +
门禁 6 项全绿**」。占位值会让 `fw.py lint` 与 `fw.py selftest` 在派生工程里
**一出生就是红的**——**假失败比没门禁更糟**（2026-10 实测踩过：占位版模板派生出的工程
`lint` 报 5 处"确定性矛盾"、`selftest` 基线不过，而工程本身完全正常）。

### 换板子 / 换芯片要改哪几处

| 换什么 | 改哪 |
|---|---|
| **换板子**（同芯片） | `Core/Inc/board_config.h` 的引脚与时钟宏 → `fw.py lint` 对账通过 |
| **换芯片** | 上面 + 链接脚本 + 启动文件 + `.ioc` 芯片字段（4 个）→ 见 [`板级差异.md`](板级差异.md) §1 |

**换芯片时 `derive.py` 只做同板派生**（复制 + 改名 + 新 git），换芯片要人工同步上面那几处——
本层没有换芯片脚本（那是工程侧资产，见 §4）。派生后 `derive.py` 会扫一遍旧工程名残留并
**分类列出**（活引用 vs 历史叙述），**只报告不自动改**——因为残留里混着"曾写死过什么"这类
历史事实，自动替换会把它们改成语义错误的句子。
