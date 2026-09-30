---
name: stm32-hang-triage
description: 用 J-Link 在 STM32 裸机/FreeRTOS 固件上定位两类上板故障：(A) 卡死/死循环/无输出——板子能烧写但跑不起来、日志停在某一行、RTOS 下中断不响应，**包括"无 HardFault 的静默死锁"（库的断言处理器 while(1)：LVGL `LV_ASSERT_MALLOC`、FreeRTOS `configASSERT`、HAL `assert_failed`）**；(B) 功能静默失效——程序跑得好好的、日志一切正常，但外设就是不工作（PWM 没波形、GPIO 没配成复用、定时器寄存器全 0）。覆盖 PC 定位、栈帧还原、寄存器核查、反汇编核对（含从断言前的 `bl lv_log_add` 参数反查行号与断言消息）、静态变量读回，以及 FreeRTOS BASEPRI 永久屏蔽、TIM_CHANNEL_1==0 误判这类高频陷阱。
agent_created: true
---

# STM32 上板故障定位（J-Link 侧）：卡死 与 静默失效

**核心原则：不猜。** 每一步都要拿到可判定的证据（地址、寄存器值、反汇编），
再把地址翻译成源码行。凭"应该是 XX 问题"下结论是本流程要消灭的行为。

**两条最重要的判据（先记住这两条）**：

1. **CPU 停在哪条指令上** —— 决定是"卡死"还是"在跑但没干活"。
2. **寄存器里的真值** —— 日志会骗你（它打的是"意图值"），寄存器不会。

## 何时用

- 烧写成功但固件跑了没反应 / 日志停在某一行
- FreeRTOS 下任务不切换、`HAL_Delay()` 卡住、中断不响应
- 疑似 HardFault 但没有可用的串口输出
- **日志一路正常，但外设不工作**（无波形、无输出、无反应）→ 直接用步骤 7

## 步骤 0：先把"卡死"和"没输出"分开

```
J-Link halt 后读 PC
  ├─ IPSR != 0            → 在异常里，读 CFSR/HFSR/BFAR/MMFAR 定位故障类型
  ├─ CONTROL[1]==1 (PSP)  → 任务上下文（RTOS 已跑起来）
  └─ IPSR==0 且 PC 不动   → 普通死循环，走步骤 1
```

寄存器里必看：`PC` / `LR(R14)` / `SP(R13)` / `XPSR(IPSR)` / `CONTROL` /
`BASEPRI` / `PRIMASK` / `CFBP`。

## 步骤 1：用 J-Link 脚本取 PC（Windows 路径坑）

写 `.jlink` 脚本（脚本文件**必须放在 Windows 能打开的路径**，
MSYS 的 `/tmp` 路径 `JLink.exe` 打不开），脚本内容：

```
si SWD
speed 4000
device <器件名>
connect
h
regs
g
qc
```

调用：

```bash
"C:/Program Files/SEGGER/JLink_V936/JLink.exe" -NoGui 1 -ExitOnError 0 \
  -CommanderScript "C:\abs\path\to\probe.jlink"
```

输出里 grep `^PC =`。**收尾用 `g` 恢复运行再 `qc`**，别把板子留在 halt 状态。

## 步骤 2：PC → 源码行

```bash
BIN=<arm-gnu-toolchain>/bin
"$BIN/arm-none-eabi-addr2line.exe" -f -C -i -e build/Debug/x.elf 0x0800XXXX
# 同时看反汇编确认是"哪个循环"
"$BIN/arm-none-eabi-objdump.exe" -d --start-address=0x... --stop-address=0x... x.elf
```

`bcc.n`/`bne.n` 跳回自身的循环 + `bl HAL_GetTick` = `HAL_Delay` 自旋的典型形态。

## 步骤 3：栈帧还原调用链（没有调试器调用栈时的救命招）

```
mem32 <SP值> 72          # 从 SP 往后 dump 若干字
```

取出落在代码段（如 `0x0800_0000`~`0x0808_0000`）的字，
**地址 & ~1** 后逐个 addr2line，就是调用链（深浅顺序 = SP 递增顺序）。
栈里的常量（如 `0x64`=`100`、`0x1F4`=`500`）还能帮你认出是哪层帧。

## 步骤 4：区分"外设没配好"和"中断进不来"

读这些地址（STM32F4）：

| 地址 | 寄存器 | 判据 |
|---|---|---|
| `0xE000ED28` | CFSR | 非 0 = 有硬件故障 |
| `0xE000ED2C` | HFSR | bit30 FORCED = 升级成 HardFault |
| `0xE000E100/104` | NVIC ISER | 目标 IRQ 的使能位 |
| `0xE000E200/204` | NVIC ISPR | **该 IRQ 的 pending 位** |
| `0xE000E400+n` | NVIC IPR | 优先级（高 4 位有效，`0xF0` = prio 15）|

**关键推理**：外设寄存器显示"定时器在计数、UIF 已置位" +
`ISPR` 里该 IRQ **pending 却一直不响应** + 外设时钟/使能都正常
→ 不是外设配置问题，是**中断被屏蔽**。此时看 `BASEPRI`。

## 步骤 5（高频陷阱）：FreeRTOS 的 BASEPRI 永久屏蔽

**症状**：`BASEPRI = configMAX_SYSCALL_INTERRUPT_PRIORITY（常为 0x50）`，
优先级 ≥5 的中断（含 HAL 的 TIM 时基）全部不响应，
`uwTick` 冻结 → `HAL_GetTick()` 恒定 → `HAL_Delay()` 死循环。

**机理**（`portable/GCC/ARM_CM4F/port.c`）：

```c
static UBaseType_t uxCriticalNesting = 0xaaaaaaaa;   // 初值不是 0！
// xPortStartScheduler():  uxCriticalNesting = 0;    // 只有这里归零
vPortEnterCritical():  portDISABLE_INTERRUPTS();  uxCriticalNesting++;   // → 0xaaaaaaab
vPortExitCritical():   uxCriticalNesting--;                              // → 0xaaaaaaaa
                       if (uxCriticalNesting == 0) portENABLE_INTERRUPTS();  // 永不成立！
```

**所以：调度器启动前调用任何 FreeRTOS 原语都会永久按住 BASEPRI。**
`xSemaphoreCreate*` 和 `xSemaphoreTake*` 都算——它们内部走
`xQueueGenericSend → taskENTER_CRITICAL()`。

**排查方法**：在 `main()` 里逐个注释掉"调度器启动前"的调用，
或直接全局搜 `xSemaphore` / `xQueueCreate` / `xTaskCreate` 的调用点，
看有没有哪个在 `vTaskStartScheduler()` 之前。

**修法**（不要改 FreeRTOS 源码）：
- 把"需要在任务上下文才合法/需要中断"的初始化**整体挪进第一个任务**
  （在 RTOS 下这才是正解：外设初始化 + delay 都不该在调度器前做）。
- 日志锁这类必需的同步原语，用 `xTaskGetSchedulerState() == taskSCHEDULER_NOT_STARTED`
  早退，改**惰性创建**（首次在任务里创建，用临界区保护赋值并回收竞态败者）。

**注意**：`xPortStartScheduler()` 的 SVC handler 会清 BASEPRI，
所以它之后能正常跑——但在此之前**任何依赖中断的代码已经死了**，
包括 `HAL_Delay()`。别被"SVC 会清掉"误导。

## 步骤 6：顺手要查的几件事

- `uxTaskGetStackHighWaterMark(t)`：**实测**栈余量（返回剩余字数）。
  配置小 + 开了 `configCHECK_FOR_STACK_OVERFLOW=2` 会直接报出来。
  经验判据：余量 <10% 就加栈。
- `xPortGetFreeHeapSize()`：堆余量。**跑 20s 看是否下降**才能判断有无泄漏。
- `CONTROL[1]` 判断当前是 MSP 还是 PSP（PSP = 在任务里）。

## 步骤 7：功能静默失效（代码在跑、外设不动）

**症状**：烧写成功、RTT 日志完整漂亮、任务心跳正常、返回值检查也做了——
但引脚上没有波形 / GPIO 不是复用态 / 外设寄存器读出来全是 0。

**这个场景最容易浪费时间，因为三条线索全在骗你**：

| 骗你的线索 | 为什么骗人 |
|---|---|
| 日志 | 打的是**上层算出的意图值**（`permille/10`），不是从寄存器读回的真值 |
| 返回值 | `(void)xxx()` 把错误吞掉了；或失败路径是**静默 return**，没打日志 |
| 源码阅读 | 逻辑看着完全正确——错的是**某个常量/哨兵值撞车**（见下） |

**唯一没被骗过的一环：直接读外设寄存器和静态变量内存。**

### 排查顺序

```
① 读外设寄存器，看"到底配上没有"
   └─ 全 0 / 复位值 → 初始化**根本没执行到写寄存器**那一步，往上看参数校验与提前返回

② 反汇编顶层函数，确认调用链真的存在
   objdump -d --disassemble=bsp_led_init x.elf
   └─ 机器码对 → 问题在运行时，不在编译/链接（也排除 gc-sections 裁掉符号）

③ 读模块的静态状态变量（nm 找地址 → mem32 读）
   └─ s_inited / s_htim.Instance 为 0 = init 提前返回了
   └─ ⚠️ 两个同名 static 符号 = 不同编译单元里的同名变量，别读错那个

④ 回头看 `init` 里的每一处 `return -1`
   └─ 重点查"哨兵值与合法值撞车"（下表第一条）
```

### 两个高频根因（都真实踩过）

**① 哨兵值撞上了合法值**

```c
/* ❌ 错：HAL 里 TIM_CHANNEL_1 的值就是 0x00U，CH1 被永远误判成非法参数 */
uint32_t ch = tim_channel(hw->channel);
if (inst == 0 || ch == 0U) return -1;

/* ✅ 对：校验"输入域"，不校验"映射后的常量" */
if (inst == 0 || hw->channel < 1U || hw->channel > 4U) return -1;
uint32_t ch = tim_channel(hw->channel);
```

同类陷阱：
- `GPIO_PIN_0` 也是 `0x0001`（这个不撞 0，但 `TIM_CHANNEL_1`、`LL_GPIO_PIN_0` 要小心）
- 枚举/宏定义里"第一个成员 = 0"的，一律不能拿来当"无效"标记

**② 该被调用却没人调的函数**

HAL 里有一批"约定名"函数**不属于 HAL 库**，需要你自己调用：

```bash
grep -rn "MspPostInit" Drivers/     # → F4 上零匹配！
```

`HAL_TIM_MspPostInit()` 是 **CubeMX 生成到 `tim.c` 的用户函数**，由 `MX_TIMx_Init()`
显式调用。HAL 只提供 `HAL_TIM_PWM_MspInit()`（弱函数）。
**以为"HAL 会回调"= GPIO 永远配不上 = 引脚没波形，而所有返回值都是 `HAL_OK`。**

判据：凡是名字带 `MspPostInit` / `_USER_CODE` 的，先在 HAL 库里搜一遍；
搜不到就说明调用责任在你。

**③（相关）外设时钟没使能**

写寄存器**静默失败**——不报错，读回全是复位值。所以"寄存器全 0"要同时怀疑
时钟没开。读 `RCC->APB1ENR` / `APB2ENR` / `AHB1ENR` 对应位确认。

### 修完之后必须做的两件事（防止下次再被骗）

1. **失败路径必须出声**：`init` 失败打 `LOG_E`，不要静默 `return`。
2. **日志改打真值**：从底层 `get_xxx()` 读回并打印，与意图值**成对**打印
   （如 `led req=100% act=1000`，`act=-1` 一眼看出没初始化成功）。
   验收标准：**故意让初始化失败一次，看日志能不能立刻指出问题。**

## 步骤 8：确认引脚"实际"输出（AF 模式下 ODR 不可信）

外设寄存器配对 ≠ 引脚电平对。要判"这个脚现在到底输出高还是低"：

| 想确认 | 读什么 | 说明 |
|---|---|---|
| **引脚实际电平** | `GPIOx->IDR`（GPIOC = `0x40020810`）| 复用模式下也能读到真实电平 ✅ |
| ❌ **不要用** | `GPIOx->ODR`（GPIOC = `0x40020814`）| **AF 模式下不反映复用输出的实际电平**，读到的是陈旧/复位值 |
| PWM 输出状态 | `CCR` 与 `ARR` 的关系 | mode1 + Polarity High：`CCR > ARR` → 恒高；`CCR == 0` → 恒低 |

⚠️ **真实踩过**：调 LCD 背光时读到 `ODR bit6 = 0`，据此断言"引脚为低、背光被压暗"，
**结论是错的** —— ODR 在 AF 模式下无意义。改用 `IDR` 才拿到真值。

**证据链闭合标准**：软件层（`CCR`/`ARR` 推出的输出状态）+ 硬件层（`IDR` 实际电平）
**两者一致**才算定案。PWM 那条尤其硬——mode1 的规则是确定的，不依赖任何读数。

### 同类变体：配置对了，但"极性/映射"与实际硬件相反

外设完全正常、寄存器全对、日志全对，**行为却反了**（该亮时灭、该快时慢）。
典型：`ACTIVE_LOW` 宏、PWM Polarity、SPI 字节序、编码器计数方向。

- 判据：读寄存器只能证明"写进去了"，证明不了"方向对不对"——**方向问题必须靠
  人眼/示波器/外部对照**，不要用寄存器读数假装验证过。
- 做法：把极性收敛成**一个宏**，并在注释里写清"取反的现象是什么"，
  下次换接法只改一处。

## 步骤 9（静默死锁的真凶）：库自带的「断言处理器」是死循环

**症状**：烧写成功、编译零告警、**没有 HardFault**、RTT 日志停在某一行不再输出、
PC 多次采样恒定在同一地址、`CFSR / HFSR` 全 0 —— 看着像"卡住"但没有任何故障证据。

**机理**：很多嵌入式库把断言失败默认实现成 **`while(1);`**，既不报错也不复位：

| 库 | 位置 |
|---|---|
| LVGL | `lv_conf.h` 的 `#define LV_ASSERT_HANDLER while(1);`（`LV_USE_ASSERT_MALLOC=1` 时分配失败即走这里） |
| FreeRTOS | `configASSERT(x)` 若被定义成空/死循环同理 |
| ST HAL | `assert_failed()` 的用户实现常写成死循环 |

⇒ **"断言失败"在现场的表现是"静止"而不是"崩溃"**：画面停在半帧、日志断流、无 Fault。
正因如此它极易被误判成栈溢出 / 死锁 / 中断丢失 —— 白花好几轮去查错方向。

### 决定性判据：反汇编那一条指令

```bash
# ① 多次采样确认 PC 恒定，且 CycleCnt 在涨（时间在走，不是在等中断）
# ② 定位函数与行
arm-none-eabi-addr2line -f -C -i -e x.elf 0x080XXXXX
# ③ ★ 反汇编那一条，看是不是"跳自己"
arm-none-eabi-objdump -d --start-address=0x… --stop-address=0x… x.elf
```

**关键形态**（真实案例）：

```asm
801412a:  bl    801e4dc <lv_log_add>      ← 断言先打日志（参数含行号/级别）
801412e:  e7fe  b.n   801412e <…+0xa6>    ← ★ 跳自己 = while(1)
```

`b.n .` / `b .` **就是断言处理器**。但更值钱的是它**上一条 `bl …log…`**——
**寄存器参数能直接还原"哪一行、哪个断言"**：

- `r2` = 行号（如 `#106` → 源码第 106 行）
- `r0` = 日志级别（LVGL：3 = ERROR）
- `r1` 与栈上参数 = 格式串地址 → 用 `objdump -s` 或 J-Link `mem` 读出字符串

本例照此还原：`lv_draw_add_task` → `lv_draw.c:106` → `LV_ASSERT_MALLOC(new_task)`
→ 宏展开成 `"Out of memory"` ⇒ **根因是 LVGL 内存池不够，与栈/中断无关。**

### 常见触发源与对策

| 断言 | 触发源 | 对策 |
|---|---|---|
| `LV_ASSERT_MALLOC` | `LV_MEM_SIZE` 小于**渲染峰值**（≠ 控件常驻占用，实测可差 2 倍） | 加大池；**按 peak 定，别按 used 估** |
| `configASSERT` | 优先级/临界区用法错误、队列满 | 逐个核对调用点 |
| HAL `assert_failed` | 参数非法（常是哨兵值撞车，见步骤 7①） | 见步骤 7① |

> ★ **省一轮编译烧录的技巧**：调试期把 `LV_ASSERT_HANDLER` 临时改成
> "记录现场再停" —— 把 `lv_mem_monitor()` 的读数写进
> `volatile uint32_t g_diag[8]`，再用 J-Link `mem32 <addr> 8` 读出来。
> 比"看到死循环后回头猜"快得多，且不依赖日志后端（日志常已被冲掉）。
> 用完记得改回去。

---

## 反模式（别做）

- 别看到"没日志"就断定是串口/RTT 坏了——先确认 CPU 到底在哪条指令上。
- 别用 `arm-none-eabi-size` 的 section 求和当 Flash/RAM 占用。
- 别在块注释里嵌 `/* ... */`（会提前闭合，报一堆 `stray '\3xx'`）。
- 别改第三方库（FreeRTOS/LVGL/ST HAL）源码来"绕过"问题，
  优先在调用点修正使用方式。
- **别只看日志就下结论**。"日志正常"只证明**打日志那条路径**被执行了，
  不证明外设配置成功。功能类问题一律要读寄存器。
- **别把 `(void)函数调用;` 当成"我处理了返回值"**。忽略返回值等于放弃错误信号。
- 别在改完一行代码后就宣布修好——**同一份证据链要重跑一遍**
  （寄存器读数、日志真值），否则你只是换了个地方猜。
