---
name: "stm32-hal-cli-flow"
description: "STM32 HAL 四层工程（Task / Operation / Device / Common，自研 Tools/fw.py + CMakePresets + J-Link + SEGGER RTT + CubeMX 生成链）的构建 / 烧录 / RTT 日志 / 固件体积 / PC 单元测试 / 闭环验证 CLI 流程。触发条件：工程根同时存在 Tools/fw.py 与 CMakePresets.json，且用户要求编译、构建、烧录、下载、看日志、查体积、跑单测、闭环验证、清理 build/、搬运 CubeMX 生成物、加外设骨架。本 skill 会明确阻止误用 st-flash / STM32_Programmer_CLI / openocd / ST-Link 等外部工具链。"
agent_created: true
---

# 本模板系工程的 CLI 工作流

> ★ **2026-09-17 同步**：工程做了三次大重构 —— ① 拆掉强制分层（HAL 对全工程可见）；
> ② 改成四层业务结构（`Task` / `Operation` / `Device` / `Common`），`App/` 与 `BSP/` 已不存在；
> ③ `Core/` 交给 CubeMX 生成，`Middlewares/` 的 FreeRTOS 也来自 CubeMX（V10.3.1），**LVGL 已移出**。
> 静态检查器从 5 个减到 1 个（只剩 CubeMX 对账）。若本文其他位置与 `AGENTS.md` 冲突，**以 `AGENTS.md` 为准**。

## 0. 先确认是不是这套工程

工程根**同时**存在 → 用本 skill：

- `Tools/fw.py`（一体化入口：build / flash / rtt / verify / size / sizecheck / clean / lint / env / **test**）
- `Task/` + `Operation/` + `Device/` + `Common/` **四层业务目录**（2026-09-17 起；旧的 `App/` + `BSP/` 已不存在）
- `CMakePresets.json`（Debug / Release / RelWithDebInfo / Debug-UART）
- `AGENTS.md`（给 AI 的硬约束）

任一项缺失 → 不是这套工程：先确认工程是不是用了别的模板/入口——**本 skill 只认上面这套
结构，别硬套**（套错的命令会烧错文件或读不到日志）。

---

## 1. 铁律（先读，避免烧错东西）

| # | 规则 | 原因 |
|---|------|------|
| 1 | **只用 J-Link + SEGGER RTT**。禁止改用 `st-flash` / `STM32_Programmer_CLI` / `openocd` / `st-info` | 本工程的探针路径、产物名、RTT 通道规划全收敛在 `Tools/fw.py`；ST-Link 路线的脚本与判据是另一套，混用会烧错文件或拿不到日志 |
| 2 | 硬件动作一律走 `python Tools/fw.py <子命令>` | 探针路径、器件名、产物名收敛在 fw.py + `build/<preset>/board.env`，不要在临时脚本里散落绝对路径 |
| 3 | 固件体积只认 `python Tools/fw.py size` | `arm-none-eabi-size` 的 section 求和 ≠ 真实占用（section 间有 ALIGN 间隙，`.data` 初值还在 Flash 里） |
| 4 | 改动后**零告警**是硬指标，禁止新增 `-Wno-*` | 见 AGENTS.md §2 |
| 5 | 动了 `Core/Inc/board_config.h` 的引脚/时钟 → 必须提示用户重新上板验证 | AI 无法判断硬件接线 |
| 6 | `clean` 只允许动 `build/` | 绝不能碰 `Drivers/`、源码、用户目录 |

---

## 2. 命令表（VS Code 任务面板里的 ①~⑦ 就是这些）

| 用途 | 命令（工程根执行） |
|------|-------------------|
| 配置 CMake | `python Tools/fw.py build`（缺 `build/<preset>/CMakeCache.txt` 时**自动先 configure**；2026-09-16 起）<br>或显式 `cmake --preset Debug` |
| 编译 Debug | `python Tools/fw.py build` |
| 编译 Release | `python Tools/fw.py build --preset Release` |
| 编译（串口日志版） | `python Tools/fw.py build --preset Debug-UART` |
| 烧录 + 闭环验证 | `python Tools/fw.py verify --duration 8` |
| 只烧录（不重编） | `python Tools/fw.py flash --no-build` |
| 抓 RTT 日志 | `python Tools/fw.py rtt --duration 10`（`--channel 1` 抓数据通道） |
| 固件体积 | `python Tools/fw.py size` |
| 资源预算门禁 | `python Tools/fw.py sizecheck` |
| 静态检查 | `python Tools/fw.py lint`（**现在只剩一项**：CubeMX 配置对账。分层 / 孤儿宏 / 文档引用 / 文档防腐四个检查器已于 2026-09-17 随强制分层一起删除） |
| **电脑上跑单测** | `python Tools/fw.py test`（host 编译 `Operation/` + `Test/`，**不需要板子**；秒级） |
| 搬 CubeMX 生成物进工程 | `python Tools/cmx_apply.py [--write]`（默认只预览；自动挑最新产物 + 合并工程里的 USER CODE） |
| 无人值守生成 CubeMX 代码 | `python Tools/cmx_gen.py`（**可选** —— 你手点 GUI 的 Generate 同样可以，见 `docs/guides/CubeMX生成链路.md`） |
| 加外设骨架 | `python Tools/new_peripheral.py adc1 --hal ADC --pin PA0`（生成 Device/ 骨架 + 挂进 `bsp.h` + **HAL 模块开关体检**） |
| 环境体检 | `python Tools/fw.py env` |
| 依赖体检 | `python Tools/fetch_deps.py --check` |
| 清理产物 | `python Tools/fw.py clean` |

`--preset X` 写在子命令前或后都行（fw.py 内部做了预处理）。

> **为什么"编译"一栏不再写 `cmake --build`**：`cmake --build --preset X` 在构建目录不存在时
> 直接非 0 退出，`fw.py` 会把它翻译成**"编译失败"** —— 看着像源码有问题，其实只是没 configure
> （实测确认过）。触发场景不止新工程：**换芯片时 `chip_profile.py` 会清空 `build/`**，
> 清完再跑 `verify` 同样会撞上。现在 `cmd_build` 检测到缺 `CMakeCache.txt` 会先 configure。
> ⚠️ 它**不**自动加 `--fresh`：需要 `--fresh` 的场景（改了 `CMAKE_*_FLAGS_INIT`）语义上要求显式表达。

---

## 2.5 换芯片 / 派生新工程（同一套工程）

```bash
python Tools/new_project.py my_board                 # 派生：复制骨架 + 成套改名
python Tools/new_project.py my_board --chip STM32F407VGTx   # 派生并切芯片
python Tools/chip_profile.py STM32F407VGTx           # 已有工程原地换芯片
```

| 规则 | 说明 |
|------|------|
| 芯片数据不凭记忆 | `chip_profile.py` 从 CubeMX 固件包（`~/STM32Cube/Repository/STM32Cube_FW_F4_*`）的**官方 ld** 现读 MEMORY 段，启动文件/器件头同源。不要手填容量数字 |
| 只支持带 CCMRAM 的 F4 | F401/F410/F411/F412/F446 **没有** CCM，脚本会拒绝并列出要人工改的三处（ld 的 `.ccmram` 段、`ccmram.c`、`main.c`） |
| 换完必须清 build/ | `LINKER_SCRIPT` 是 CMake CACHE 变量，不清会继续用旧内存布局 —— **芯片名变了、链接脚本没变、编译照样过**（假成功，实测踩过）。脚本已自动清 |
| 上板前改引脚 | 换芯片脚本改不了接线：`Core/Inc/board_config.h` 必须按新板子核对 |
| 判"切换是否真生效" | 首选**配置输出里的芯片名**（`芯片: STM32F407xx / 板卡 STM32F407VG`）与构建日志里编的启动文件（`startup_stm32f407xx.s`）。<br>⚠️ **不要只看 `fw.py size` 的内存数字**：同容量芯片之间可能**逐字段完全相同** —— 2026-09-16 实测 F405RG→F407VG，官方 ld 的 ROM 1024K / RAM 128K / CCM 64K 三项一模一样，只有 ETH 与 DCMI 两个外设不同。数字没变 **≠** 切换失败；换到 F429 才会看到 2 MB/192 KB/QSPI 16 MB 的变化 |

---

## 2.6 门禁自检（改完 `Tools/` 下任何检查器后**必跑**）

```bash
python Tools/selftest.py            # 静态用例，秒级
python Tools/selftest.py --full     # 追加编译期用例（需 configure + 编译 app，约 1 分钟）
python Tools/selftest.py --keep     # 保留副本目录，进副本手工复现
```

**它证明的事情**：检查器在违规时**真的会报错** —— 这是 `AGENTS.md` §2 硬约束 3
（"lint 退出码 0 不是有效判据"）的**自动化版本**。

| 要点 | 说明 |
|------|------|
| 在**工程副本**上做 | 原工程全程只读。副本隔离顺带根治了旧人工做法"注入忘了删"的老毛病 |
| **先跑基线** | 副本上无注入时 `fw.py lint` 必须全绿 —— 没有这一条，"永远报错"的假检查器能骗过所有负向用例 |
| 判据是**两件事** | 检查器必须**非 0 退出**，**且**输出里出现注入的那个标记串。只看退出码会被"脚本崩了"骗过 |
| 覆盖 | 1 条静态（CubeMX 对账）+ 1 条编译期（**App 能直接 include HAL 头**）。原 12 条针对 R1–R7 / 孤儿宏 / 文档死链的用例已随检查器删除而作废 |
| 什么时候用 | 改了 `Tools/` 检查器；发布/交接前跑 `--full`；怀疑"某门禁好像没在管"时 |

⚠️ 别把"`selftest.py` 通过"当成"工程没问题" —— 它验证的是**门禁本身有效**，
不是"你的代码合规"。合规看 `fw.py lint`。

完整流程 / 边界 / 回退 / IO 约定 / 反证实验见 `docs/guides/工作流与自检.md`。

---

## 2.7 四层结构与"从 0 加东西"落在哪（2026-09-17 起）

```
Task/            调度：只管"什么时候做"。唯一能同时用 RTOS、Device、Operation 的层
Operation/       纯逻辑：**吃数字、吐数字**。禁 HAL / 禁 FreeRTOS / 禁延时（时间由参数传入）
Device/          硬件：唯一直接调 HAL 的层。句柄 static 在 .c 内，.h 不外泄 HAL 类型
Common/          日志 + 错误码。零依赖，MCU 与 PC 两侧各有一份实现（同名符号链时二选一）
Core/            CubeMX 生成（改代码只写 USER CODE BEGIN/END 之间）
project_config.h 数量 / 阈值 / 功能开关（工程根）
```

| 想加什么 | 写哪里 | 怎么验 |
|---|---|---|
| 纯业务逻辑 | `Operation/{Src,Inc}/op_x.{c,h}` | `fw.py test` —— **不用板子** |
| 硬件操作 | `Device/{Src,Inc}/bsp_x.{c,h}`（脚手架 `new_peripheral.py`） | `fw.py build` + `sizecheck` |
| 调度 / 参数注入 | `Task/Src/app_rtos.c`（组合根 `Task/Src/app.c` 注入实例） | `fw.py build` |
| 新外设（引脚/时钟） | **先 CubeMX 里配** → Generate → `cmx_apply.py --write` | `fw.py lint`（对账） |

★ **规矩靠 CMake 强制，不靠自觉**：`operation` 目标只链 `common`，拿不到 HAL / FreeRTOS 的
include 路径 ⇒ 在 Operation 里 `#include "stm32f4xx_hal.h"` 或调 `vTaskDelay` **直接编译失败**。

⚠️ **本工程的头号坑（2026-09-17 实测）**：`.ioc` 里没配的外设，它的 HAL 模块宏**不会开**
（`Core/Inc/stm32f4xx_hal_conf.h`）⇒ 一旦用了那个类型就报
`error: unknown type name 'Xxx_HandleTypeDef'`（**编译期**，不是链接期）。
正确修法是去 CubeMX 里加一个该外设，**不是**手改 `hal_conf.h`（那是生成物，下次生成会覆盖）。
`new_peripheral.py` 会提前体检并警告。当前工程只开了：CORTEX DMA EXTI FLASH GPIO PWR RCC SPI TIM。

---

## 3. 改完代码的固定顺序

```
test → lint → Debug 构建 → （改到 Device/Core 再加）Release 构建 → sizecheck → verify
```

- **`test` 最便宜（秒级、不用板子）⇒ 先跑它。** 业务逻辑的错误应该在这一步就抓完，
  别留到烧板之后 —— 那是本工程四层结构存在的**唯一理由**。
- `lint` 现在只做 CubeMX 配置对账（`.ioc` ↔ `board_config.h` 的确定性矛盾）。
  它也是 `verify` 的前置 —— lint 不过就不会浪费一次烧录。
- 双预设都要过：`-Os`（Release）与 `-Og`（Debug）优化级别下都可能有各异的告警。

---

## 4. 判定与排错

`fw.py verify` 退出码（与 README §5 一致）：

| 码 | 含义 | 下一步 |
|----|------|--------|
| 0 | 抓到 `[AI_READY]` | 通过 |
| 1 | 固件报了 `[AI_FAIL]` | 读 RTT 输出定位（模板里在时钟自检失败时打） |
| 2 | 超时/无标记 | 看是否打了 `[FAULT]`（`bsp_fault_report()`），或改用调试器 |
| 3 | 编译失败 | 修编译错误 |
| 4 | 烧录失败 | 查探针连接 / 板子供电 / SWD 线序 |
| 5 | RTT 抓不到数据 | 确认 `LOG_BACKEND=RTT` |
| 6 | 环境不完整 | 缺依赖或找不到 J-Link，看 `fw.py env` 输出 |
| 7 | 静态检查未通过 | 只剩 CubeMX 对账一项（`cubemx_sync.py`）：报的是 `.ioc` 与 `Core/Inc/board_config.h` 的**确定性矛盾**（两边都有值且不等） |
| 8 | 资源超预算 | Flash/RAM 顶穿上限，或 CCM 利用率 / 落区不符 —— 看 `sizecheck` 输出里的落区核对行（`Tools/check_size.py` 是权威定义） |

失败时先读 `build/<preset>/rtt_verify.log`（verify 会把原始 RTT 输出留在那里）。

---

## 5. 本机环境事实（不要重新探测）

- `python` / `cmake` / `ninja` / `arm-none-eabi-gcc` / `JLink.exe` 都在 PATH 上。
- git 不在 PATH：用 `D:\Git\cmd\git.exe`。
- ⚠️ 本机 Bash 工具**缺 coreutils**（`ls` / `dirname` / `tail` 都不存在），
  凡是管道到这些命令的写法都会失败 → 要过滤就在 python 里做，或直接看原始输出。
- ⚠️ 本机 `git reset --hard` 不可靠（只更新 HEAD/索引，不回写工作区）→
  回退用 `git revert` 或 `git checkout <rev> -- <path>`。

---

## 6. 真相源（有冲突时以它们为准）

| 内容 | 文件 |
|------|------|
| 硬约束、踩过的坑 | `AGENTS.md` |
| 命令实现与退出码 | `Tools/fw.py` |
| 用法、体积口径、排错 | `README.md` |
| 派生新工程 / 换 F4 芯片 / 换 M7 | `docs/guides/新建工程指南.md`（场景 A~F，含边界与实测记录） |
| 内存整体规划 / 预算红线 | `docs/guides/内存整体规划-2026-09-15.md`、`docs/guides/资源预算上限表.md` |
| **CubeMX → 工程的完整链路**（改 .ioc 后怎么做） | `docs/guides/CubeMX生成链路.md` |
| 文档总索引 | `docs/README.md` |

⚠️ 查表时请确认文件真的存在再引用。本表曾长期指向 `docs/跨芯片移植清单.md`、
`docs/新建工程指南.md`（漏了 `guides/`）、`docs/工程体检报告-*.md`、`docs/顶级优化方案-*.md`
——**这四个路径全部不存在**，而 `check_doclinks.py` 只扫 `.md`/`.txt`，管不到 skill 文件，
所以这类死引用不会被任何门禁拦下（2026-09-16 逐条核实后修正）。

---

## 7. 编译期优化 / 对照实验怎么做得可信

用户问"优化""体积""性能"时，**不要凭经验给数字**——本工程有能力做真实 A/B 对照。
（2026-09-12 用这套方法实测出：`-ffunction-sections` 省 119.5 KB、CCM 搬堆再省 16 KB。）

### 7.1 方法（缺一步就会得到假结论）

| 步 | 做法 |
|----|------|
| 1 | **在工程副本上做实验**（`shutil.copytree` 排除 `build/.git/.workbuddy/.cache/jobs`），不污染工作区 |
| 2 | 每个变体**独立 build 目录**：`cmake -S <副本> -B <副本>/build/<变体> -G Ninja -DCMAKE_TOOLCHAIN_FILE=.../Config/arm-none-eabi-gcc.cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS_RELEASE="..."` |
| 3 | **补丁后独立校验落盘**：读回文件确认目标字符串出现/消失次数（如 `printf_float` 出现次数、段名在不在 ld 里） |
| 4 | 每个变体必须**预期有可区分的差异**；若几个变体产出**字节相同的 elf** → 立刻怀疑补丁没生效 |
| 5 | 体积用 `Tools/stm32_size.py`（唯一口径）；落区用 `arm-none-eabi-nm -S <elf>` 反查地址判定：`0x1000_xxxx`=CCM、`0x2000_xxxx`=主 SRAM |
| 6 | 跑完清理实验目录 |

### 7.2 本工程实测过的坑（别再踩）

1. **`--gc-sections` 必须配 `-ffunction-sections -fdata-sections`**。只开前者时 GC 只能以"整个 `.o`"为粒度，文件内未引用函数全保留。加进 `Config/arm-none-eabi-gcc.cmake` 的 `ARCH_FLAGS` 即可（实测 Release 441,184 → 318,812 B，0 告警）。
2. **段名不得与已有段名前缀重叠**。`*(.ccmram*)` 会吞掉 `.ccmrambss*`（前缀重叠），而 `.ccmram` 是 `AT>FLASH` → 16 KB 零值被写进 Flash。放无初值大块请用 `.ccmnoload` 这类名字。
3. **CCM（0x1000_0000）DMA 摸不到**。显示缓冲（`s_draw_buf`/`s_fill_buf`）**必须留在主 SRAM**；可搬的是 FreeRTOS 堆、LVGL 内存池、静态任务栈。
4. ⚠️ **LVGL 已于 2026-09-17 整体移出本工程** ⇒ 下面第 4、6 条**当前不适用**，仅当重新引入 LVGL 时才需要：**`LV_MEM_ADR` 只能写裸字面量**（它被用在 `#if LV_MEM_ADR == 0` 里），写 `((uintptr_t)&sym)` 直接编译失败；而 `LV_ATTRIBUTE_LARGE_RAM_ARRAY` 经 `lv_conf.h` 覆盖**实测无效**（`gcc -E -dM` 查出来是空）。
5. **LTO 在本工程链接失败**（LTO 分区未解析引用 + `dangerous relocation: unsupported relocation`），即使 `-flto` 同时进编译与链接。别浪费时间。
6. （★ 同上，LVGL 已移出）**LVGL 源集不能按目录砍**：`lv_init.c` 里有**无 `#if` 保护**的无条件调用链（`lv_bin_decoder_init()` → `lv_sysmon_builtin_init()` …），砍完必链接失败。且体积已被第 1 条吃掉，裁剪只剩构建时间收益。
7. **`__FILE__` 绝对路径会进固件**（`vAssertCalled(__FILE__, __LINE__)` 等），导致**同源不同目录构建出的固件字节不同**（实测差 184 B == 路径长度差）。做对照实验要么固定路径，要么加 `-ffile-prefix-map=<前缀>=.`。
8. ⚠️ **`subprocess` 调 cmake 必须显式传 `cwd=<副本>` 或 `-S <副本>`**：只给 `-B <临时目录>` 时 CMake 以**当前工作目录**为源目录 → 对副本的源码补丁全部被忽略，产出"成功但没生效"的假结果。（本轮第一遍实验就因此全废：3 个变体 elf 字节相同却都报成功。）
9. **判"固件在不在板上"不要用 `JLink verifybin xxx.bin`**：链接脚本在 `.isr_vector` 与 `.text` 之间有 `ALIGN(4)` 间隙，`objcopy -O binary` 用 `0x00` 填充、Flash 里是擦除态 `0xFF` —— `verifybin` 会在该间隙**必然报 Verify failed**（实测 367,548 B 中仅 8 B 不同，全在 `0x188–0x18F`）。可信判据是 RTT 的 `[AI_READY]`（`fw.py verify` 退出码），或整片 `savebin` dump 后按 ELF 的 LOAD 段比对。
10. **`J-Link loadfile` 打印 `Skipped. Contents already match` 不等于没烧**，该消息不可当判据（实测两次打印该消息、实际都烧进去了）。要确认新固件生效，用**功能判别器**最可靠：改一个可观测的行为（如关掉 bringup 测试，看 RTT 里 `bringup:` 系列消失），或 dump 比对。
