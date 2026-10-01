# STM32 四层工程模板（参考板：立创·梁山派·天空星 F407）

**CubeMX 直生成 + GCC/Ninja + J-Link SWD + SEGGER RTT + GDB**，四层分层把
"业务逻辑"从"硬件"里切出来 —— 于是它**能在电脑上编译并单测**，不用烧板。

> 🧭 两条入口，各看各的：
> · **人读本文件**（怎么上手、有哪些能力、哪些还没验证）
> · **AI 读 [`AGENTS.md`](AGENTS.md)**（硬规则 R1~R6、安全档位、任务路由）
>
> 冲突时以 `AGENTS.md` 为准。

---

## 1. 五分钟上手

四条命令，从零到板上跑起来：

```bash
python Tools/fw.py env       # ① 体检：工具链 / J-Link / 器件 / 各预设
python Tools/fw.py build     # ② 编译（加 --clean-first 才是"零告警"口径）
python Tools/fw.py flash     # ③ 烧录（J-Link SWD）+ 复位运行
python Tools/fw.py rtt       # ④ 看日志（Ctrl+C 停）
```

一条命令闭环（门禁 → 烧录 → 抓 RTT → 判标记，**退出码即结论**）：

```bash
python Tools/fw.py verify
```

| 退出码 | 含义 |
|---|---|
| **0** | 看到 `[AI_READY]` ⇒ 固件真的跑起来了 |
| **1** | 看到 `[AI_FAIL]` ⇒ 固件主动报错 |
| **2** | 超时，两个标记都没看到 ⇒ 探针/接线/固件卡死，**原因未知** |

⚠️ 退出码 2 **不等于**"固件有问题" —— 也可能是探针没插。先 `fw.py env`。

不需要板子也能验证业务逻辑：

```bash
python Tools/fw.py test      # PC 侧单测：host 编译 Operation/，秒级出结果
```

---

## 2. 它解决什么问题

嵌入式项目最常见的困境是：**业务逻辑和 HAL 调用缠在一起，只能靠"烧进去看看"来验证**。
这个模板把代码切成四层，让"纯计算"那部分脱离硬件：

```
Task/        调度：只管"什么时候做"          ← FreeRTOS API 只在这层
  ↓  只能向下调
Operation/   业务：吃数字吐数字               ← 禁 HAL、禁 FreeRTOS ⇒ 电脑上可编译可单测
  ↓
Device/      设备：怎么操作一个硬件           ← 唯一直接调 HAL 的层
  ↓
Core/ + Drivers/   CubeMX 生成物 + ST HAL / CMSIS

Common/      横切：日志接口（谁都能用，但它自己零依赖）
```

**分层不靠自觉，靠编译器**（见 [`docs/01`](docs/01_工程分层架构.md) §强制表）：

| 规矩 | 强制手段 | 违规时你会看到 |
|---|---|---|
| `Operation/` 不碰硬件 | 该 CMake 目标**只链 `common`** ⇒ 没有 HAL 的 include 路径 | `fatal error: stm32f4xx_hal.h: No such file or directory` |
| 同上（防绕过） | PC 侧构建里没有 HAL / FreeRTOS 符号 | `undefined reference to 'vTaskDelay'` |
| 只上层调下层 | CMake 管不了（目标级粒度） | 靠约定 + review（不假装它有兜底） |

上面两条不是"设计意图"，是**实测过的**：`python Tools/fw.py selftest --full`
会注入真违规并断言它们失败（见 §6）。

---

## 3. 目录速览

| 路径 | 谁写的 | 干什么 |
|---|---|---|
| `Task/` | **人** | 调度 + 组合根 `app.c`（全工程唯一允许跨层的地方） |
| `Operation/` | **人** | 业务纯逻辑 —— 也放在这里的东西才有 PC 单测 |
| `Device/` | **人** | 板级驱动（`bsp_*`）+ 中断回调 + 故障取证 |
| `Common/` | **人** | 横切零依赖：日志接口、工具函数 |
| `Test/` | **人** | PC 侧单测（host 编译，**不参与固件**） |
| `Tools/` | **人** | 工具链与门禁脚本 |
| `docs/` | **人** | 规范文档（骨架在 `AGENTS.md`） |
| `Core/Inc/board_config.h` | **人** | 板级事实的唯一来源（引脚/时钟/器件名） |
| `project_config.h` | **人** | 应用参数（周期/阈值/开关） |
| `Core/Src/` `Core/Inc/`（其余） | CubeMX | 生成物，只在 `USER CODE BEGIN/END` 间改 |
| `Drivers/` `Middlewares/Third_Party/` | CubeMX | 生成物，一行都不改 |
| `Middlewares/RTT/` | vendor | SEGGER RTT 源码 |

**加一个外设**、**加一个业务模块**的逐步清单在 [`docs/10`](docs/10_新增模块Checklist.md)。

---

## 4. 五条链

| # | 链 | 工具 | 入口 |
|---|---|---|---|
| 1 | 编译 | `arm-none-eabi-gcc` 15.2.1 | `fw.py build` |
| 2 | 构建 | CMake 4.3.1 + Ninja 1.13.2 | `CMakePresets.json` |
| 3 | 烧录 | J-Link SWD（器件 `STM32F407VG`） | `fw.py flash` |
| 4 | 日志 | SEGGER RTT 通道 0 | `fw.py rtt` |
| 5 | 调试 | `JLinkGDBServerCL` + `arm-none-eabi-gdb` | `fw.py gdb` / VS Code 调试面板 |

操作手册与踩坑清单（RTT 1024 B 静默丢数据、GDB 崩溃取证、体积口径）在
[`docs/11`](docs/11_构建烧录调试.md)。

### 构建预设

| 预设 | 优化 | 用途 |
|---|---|---|
| `Debug` | `-Og -g3` | 日常开发、单步调试 |
| `Release` | `-Os -g0` | 发布；体积最小 |
| `RelWithDebInfo` | `-O2 -g3` | 现场取证 / profiling |
| `Debug-UART` | `-Og -g3` + 日志走 USART1 | 手边没有 J-Link 时用 |

⚠️ 每个预设都要 `--clean-first` 才算"零告警"：增量构建只重编改动过的文件，
只在别处触发的告警会被漏报。

---

## 5. 门禁（四条，都可用一条命令跑）

| 门禁 | 命令 | 拦什么 |
|---|---|---|
| **零告警** | `fw.py build --clean-first` | `warning` + `error` 总数必须为 0。**不许加 `-Wno-*` 消错** |
| **体积预算** | `fw.py sizecheck` | Flash / RAM 超上限。口径唯一来源 `Tools/stm32_size.py` |
| **配置对账** | `fw.py lint` | `.ioc` 与 `board_config.h` 的确定性矛盾（双真相源漂移） |
| **文档死链** | `fw.py doccheck` | 骨架用短引用 `docs/01`（不是合法路径，肉眼看不出对错） |

⚠️ **`arm-none-eabi-size` 的三列不是占用**（section 间有 ALIGN 间隙，`.data` 初值
烧写时在 Flash）。回答"固件多大"之前先跑 `fw.py size`。

⚠️ **为了让门禁变绿而调高上限 = 把门禁拆了。** 要调先走
[`docs/12`](docs/12_安全边界.md) 的授权记录。

---

## 6. 门禁自检（为什么可以信上面那张表）

```bash
python Tools/fw.py selftest            # 基线 + 9 条静态负向用例
python Tools/fw.py selftest --full     # 追加 2 条编译期用例
```

**「退出码 0」不是有效判据** —— 一个什么都不做的检查器同样返回 0，
而且它不报错、不影响构建、报告照样全绿。所以自检做两件事：

1. **基线**：干净工程上跑全部门禁 → 必须全绿（排除"永远报错"的假检查器）；
2. **负向用例**：逐条注入真违规 → 对应门禁**必须**报错（排除"什么都不做"的假检查器）。

全部在**工程副本**上做，原工程只读。

---

## 7. AI 参与开发

本工程是按"AI 能直接驱动"设计的，不是"AI 顺便也能用"：

- **退出码即结论** —— 所有子命令都能被脚本/AI 判断，不需要人肉读屏；
- **门禁是硬的** —— 零告警 / 体积 / 对账 / 死链，都是"跑了就知道"；
- **操作范围是明写的** —— [`docs/12`](docs/12_安全边界.md) 把 AI 能做的分成三档
  （可直接做 / 必须先说再做 / 必须人来做），不是"希望 AI 谨慎"；
- **故障要响亮** —— 栈溢出、堆耗尽、HardFault 都会把现场打到 RTT 上并停住，
  而不是无声死循环。

AI 的工作手册是 [`AGENTS.md`](AGENTS.md)（硬规则、任务路由表、交付口径）。

---

## 8. 实测状态（别把"编译通过"当成"能跑"）

| 项 | 状态 |
|---|---|
| 四个预设 `--clean-first` 零告警构建 | ✅ 已验证（**本模板的来源工程**；派生后请在新工程重跑） |
| 产出 `.elf` / `.bin` / `.hex` | ✅ 已验证（同上） |
| 体积门禁 / 配置对账 / 死链 / 门禁自检 | ✅ 已验证（**本模板自身 + 由它派生的工程**都跑过，2026-10） |
| PC 侧单测（`fw.py test`，用例 `op_blink` + `op_flash`） | ✅ 已验证（同上） |
| `op_flash` 的单测**确实能抓错**（注入 bug → 断言失败 → 撤掉后恢复） | ✅ 已验证（同上） |
| `Operation/` 偷用 HAL → 编译期失败 | ✅ 已验证（`fatal error: stm32f4xx_hal.h`） |
| `Operation/` 偷用 FreeRTOS → 链接期失败 | ✅ 已验证（`undefined reference to 'vTaskDelay'`） |
| `Device/` 调 `Operation/` → 编译期失败（R1 的硬保证） | ✅ 已验证（`device` 目标不链 `operation`） |
| **板级硬件（引脚 / 时钟 / 外设 / 烧录 / RTT / 上板自检）** | ⚠️ **未验证** —— 本模板带的是**参考板（立创·梁山派·天空星 F407）的真实缺省值**，但**没在本机接过探针上板跑过**。换板子/换芯片后按 [`AGENTS.md`](AGENTS.md) §7 的三态标注把结果写回本节 |

> 交付时请照 [`AGENTS.md`](AGENTS.md) §7 的**三态标注**来：
> 已验证（写出跑了哪条命令）/ 未验证（说明为什么没跑）/ 不适用。
>
> ⚠️ **"符号入库"不等于"能跑"**：`nm` 只能证明代码编进去了，
> 证明不了 Flash 真能读出 ID、卡真能识别。那必须上板。

---

## 9. 规范在哪

`AGENTS.md` 是骨架（≤110 行的硬预算），细则在 `docs/`：

| 我想… | 看 |
|---|---|
| 知道代码该放哪层 | [`docs/01`](docs/01_工程分层架构.md) |
| 新增模块 / 外设 / 任务 | [`docs/10`](docs/10_新增模块Checklist.md) |
| 写 `.c` `.h`（文件头 / include / 命名 / 注释 / 类型） | `docs/02` ~ `docs/06` |
| 找现成写法照抄 | [`docs/09`](docs/09_常见模式速查.md) |
| 构建 / 烧录 / 调试 / 崩溃定位 | [`docs/11`](docs/11_构建烧录调试.md) |
| **不确定某个操作能不能做** | [`docs/12`](docs/12_安全边界.md) ← 优先级最高 |
| 想改规范 | [`docs/13`](docs/13_规范提案流程.md) |
| 这套规范从哪来 | [`docs/00`](docs/00_规范来源与提炼.md) |

文档预算（硬约束）：骨架 ≤ 110 行 · 单篇 ≤ 300 行 · 规范文档 ≤ 14 篇。
**超了说明该合并，不是该再拆** —— 规则太复杂就会被弃用。

---

## 10. 派生新工程 / 换一块板子

**派生新工程**（同一块板子做新项目）—— **只改名，不碰硬件配置**：

```bash
cp -r <PROJECT_NAME> <新工程名> && cd <新工程名>
rm -rf build .git .workbuddy-ai
# 改 3 处：CMakeLists.txt 的 CMAKE_PROJECT_NAME
#         .vscode/launch.json 的 executable（2 处）
#         .ioc 的文件名 + 内部 2 行（ProjectManager.ProjectFileName / ProjectName）
git init && git add -A && git commit -m "chore: 从模板派生"
```

逐步清单与验收判据见 [`docs/10`](docs/10_新增模块Checklist.md) §E。
✅ 2026-09-26 实测：派生后 `build --clean-first` / `test` / `selftest` 全通过，
产物随新工程名命名（`derive_probe.elf`）。

**换一块板子 / 换芯片**：

1. 在 CubeMX 里改引脚 / 时钟 / 外设，生成；
2. 把**值**抄进 `Core/Inc/board_config.h`（只抄值，不抄代码）；
3. 换芯片还要同步 `CHIP_MODEL_FLASH.ld` 的 MEMORY 段、`startup_CHIP_MODEL.s`、
   `.ioc` 与 `cmake/stm32cubemx/CMakeLists.txt`（生成物）—— 清单见
   [`docs/10`](docs/10_新增模块Checklist.md) §E.3；
4. `python Tools/fw.py lint` 确认两边一致，再 `build --clean-first`。

⚠️ **器件名与内存容量只在 `board_config.h` 一处** —— `fw.py` 从
`build/<预设>/board.env`（CMake 读 `board_config.h` 生成）取它们，
烧录脚本里没有硬编码。


---

## 11. 参考板与「换板 / 换芯片」说明

**本模板附带的是一块具体参考板的真实缺省值**，不是空壳：

| 项 | 值 |
|---|---|
| 参考板 | **立创·梁山派·天空星 F407 开发板**（核心板 STM32F407VGT6） |
| 芯片 | `STM32F407VGTx` · 1024 KB Flash / 128 KB SRAM / 64 KB CCM · SYSCLK 168 MHz · HSE 8 MHz |
| 已配外设 | USART1(PA9/PA10 日志) · SPI1(PA5/6/7 + PA4 软件CS) · SPI2 · USB_OTG_FS(PA11/PA12) · SDIO(PC8-12/PD2) · 心跳灯 PB2 · 按键 PA0 · SWD |

**可直接构建、门禁 6 项全绿**（`env` / `build --clean-first` / `test` / `lint` / `sizecheck` / `selftest`）——
这样派生出的新工程**第一天就是绿的**。

### 唯一的占位符：工程名 `<PROJECT_NAME>`

改名最稳的方式是 `python Tools/derive.py <新工程名>` —— 它只认 `CMakeLists.txt` 的
`set(CMAKE_PROJECT_NAME ...)` 这一处权威，同时更新 `.vscode/launch.json` 与 `.ioc` 的内部元数据。

⚠️ **为什么工程名有两种写法**（实测，不是偏好）：`<` `>` 在 Windows 文件名里非法，CMake 也拒绝把它当目标名 ——
`project(<PROJECT_NAME>)` 直接报 `The target name "<PROJECT_NAME>" is reserved or not valid`，configure 退出码 1。
所以 `set(CMAKE_PROJECT_NAME ...)`、`.ioc` / `.ld` / `startup` 的**文件名**、`.vscode/launch.json` 的 elf 路径，
一律用不带尖括号的同名占位符。

> **历史**：早期版本的模板把**芯片型号、引脚、时钟、容量也做成占位符**（`<CHIP_MODEL>`、`BOARD_UNSET`）。
> 已废弃：占位值让 `fw.py lint` 与 `fw.py selftest` 在派生工程里**一出生就是红的**，
> 而工程本身完全正常 —— **假失败比没门禁更糟**（2026-10 实测）。现在只留工程名一个占位符。

### 换**板子**（同芯片）

改 `Core/Inc/board_config.h` 的引脚与时钟宏，然后：

```
fw.py lint        # 对账必须过 —— 这是唯一权威判据
fw.py build --clean-first
```

⚠️ 引脚/时钟改动后**必须重新上板验证** —— AI 无法替你判断接线。

### 换**芯片**（三处必须同步，漏一处**不会报错**，只会静默错）

| # | 位置 | 为什么必须一起改 |
|---|---|---|
| 1 | `cmake/gcc-arm-none-eabi.cmake` 的 `TARGET_FLAGS`（`-mcpu` / `-mfpu` / `-mfloat-abi`）（备用件 `cmake/starm-clang.cmake` 里还有一份） | 核与浮点 ABI 变了还用旧 flags ⇒ 编得出、跑不对 |
| 2 | `CMakeLists.txt` 引用的链接脚本（`STM32F407XX_FLASH.ld`）的 `MEMORY` 段 + 启动文件（`startup_stm32f407xx.s`） | 内存布局与向量表必须与芯片一致；链接脚本路径来自 CMake **CACHE 变量**，换完**必须清 `build/`**，否则"芯片名变了、链接脚本没变"照样编过（假成功，实测踩过） |
| 3 | `cmake/stm32cubemx/CMakeLists.txt` 的 `MX_Defines_Syms`（CMSIS 器件宏）、顶层 `CMakeLists.txt` 的 `freertos_headers` 里那个同名宏（另有 `.vscode/c_cpp_properties.json` 的 `defines` 副本） | 器件宏选错 ⇒ 直接编译失败；多处不一致 ⇒ 头文件与库的器件假设不同 |

还要同步（清单见 [`docs/10`](docs/10_新增模块Checklist.md) §E.3）：

- `Core/Inc/board_config.h` 的 `BOARD_MCU_NAME` / `BOARD_JLINK_DEVICE` / `BOARD_*_KB`（`fw.py` 与体积门禁的唯一来源）；
- `.ioc` 的 `Mcu.CPN` / `Mcu.Name` / `Mcu.UserName` / `ProjectManager.DeviceId`；
- `.mxproject`（CubeMX 的"上次生成状态"缓存）的 `CDefines`，以及它的 `LibFiles` /
  `SourceFiles` / `HeaderPath` 三张表 —— 表里还留着**当前器件**的路径（如 `...\Include\stm32f407xx.h`）；
  CubeMX 重新生成时会自己更新，**手工不用改**；
- `.vscode/launch.json` 的 `device`、`.vscode/c_cpp_properties.json` 的 `defines`。

### 厂商代码为什么不能删

`Drivers/`（ST HAL + CMSIS）、`Middlewares/Third_Party/FreeRTOS`、`Middlewares/RTT`、`Middlewares/ST/ARM/DSP`
是厂商代码，而 CMake 用**仓库内硬路径**引用它们（`add_library(segger_rtt STATIC Middlewares/RTT/SEGGER_RTT.c)`、
`cmake/stm32cubemx/CMakeLists.txt` 的 HAL / FreeRTOS 源文件清单、`cmsis_dsp` 的 `IMPORTED_LOCATION`）——
删掉就**配置阶段直接失败**。所以模板里保留，且 `.gitignore` **不忽略**它们（许可证见 [`NOTICE.md`](NOTICE.md)）。

⇒ 本副本是**「STM32F4 系族模板」**，不是「任意 MCU 模板」：`STM32F407xx` 这类器件宏与器件头要按上面第 3 处清单
**整体替换**，不能只改一个值。
