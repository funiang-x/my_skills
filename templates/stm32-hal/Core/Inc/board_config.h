#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H
/* ============================================================================
 *  board_config.h —— 板级事实的"唯一来源"（**手写文件 · 模板缺省值版**）
 *
 *  ⚠️ 本文件的值是**一块具体参考板**的真实缺省值，不是占位符。
 *      参考板：**立创·梁山派·天空星 F407 开发板**（MCU：STM32F407VGTx）
 *      为什么给具体值而不给占位：本库的工程契约要求「派生出的工程**首次构建零告警 +
 *      门禁 6 项全绿**」。占位值会让 `fw.py lint`（对账）与 `fw.py selftest`（门禁自检）
 *      在派生工程里**一出生就是红的**——**假失败比没门禁更糟**（实测踩过）。
 *
 *  ---- 换板子 / 换芯片时改哪里 ----
 *      · 换**板子**（同芯片）：改本文件的引脚与时钟宏，然后 `fw.py lint` 对账通过
 *      · 换**芯片**：还要同步链接脚本 / 启动文件 / `.ioc` 型号 —— 四处清单见
 *        `stm32-hal-cli-flow/板级差异.md`
 *      · 两个型号宏：BOARD_MCU_NAME（CubeMX 完整型号，带尾缀 x）
 *                    BOARD_JLINK_DEVICE（J-Link 短名，无尾缀；判据是"是 CPN 的前缀"）
 *
 *  ---- 与 project_config.h 的分工 ----
 *      Core/Inc/board_config.h（本文件）  引脚 / 时钟 / 外设实例（"这块板子上有什么"）
 *      project_config.h（工程根）          周期 / 阈值 / 功能开关（"产品要怎么做"）
 *      两者都**不许**在 .c 里散落魔法数字。
 *
 *  ---- 加一个外设时（三步）----
 *      1) 去 CubeMX 里配好该外设（引脚 / 时钟 / DMA），保存 .ioc 并生成
 *      2) 建 Device/Src/bsp_xxx.c 与 Device/Inc/bsp_xxx.h，并在 bsp.h 里加一行 include
 *      3) 在本文件新建一个小节，把**值**抄进来（只抄值，不抄代码）
 *      ⚠️ 完整流程与常见坑见 docs/10 §B
 *
 *  ---- 小节怎么写（照抄这个形状）----
 *      · 一个外设一节，节标题用分隔线拉满 76 列
 *      · 引脚写**端口号 + 引脚号两个宏**（`PORT` 是 0=GPIOA 的枚举值），
 *        不要写 "PA9" 这种字符串 —— 驱动里要的是数字
 *      · 时钟/分频这类值用**物理量**表述（Hz / 级数），推导值由它算出来
 *      · 会"改了不生效"的开关，加一道 `#if` + `#error` 闸门（见文件末尾的说明）
 *      · ⚠️ 引脚/时钟改动后**必须重新上板验证** —— AI 无法替你判断接线
 *
 *  ---- 谁读这个文件（改错了谁会疼）----
 *      CMakeLists.txt         读 BOARD_MCU_NAME / BOARD_JLINK_DEVICE / BOARD_*_KB
 *                             → 写进 build/<预设>/board.env → Tools/fw.py 与体积门禁
 *      Tools/cubemx_sync.py   拿它与 .ioc 对账（`fw.py lint`）
 *      Tools/selftest.py      注入式负向用例改的就是这里的宏
 *      Task/ · Device/        直接用下面的引脚宏
 * ==========================================================================*/

#include <stdint.h>

/* ------------------------------------------------------- 缺省值从哪来（须知）----
 * 本文件的引脚 / 时钟 / 容量是**参考板 STM32F407VGTx 的真实值**，可用、可编译、
 * 可过门禁（`fw.py lint` / `fw.py selftest` 都要求它们自洽）。
 * ⇒ 换板子就改这里，**不要改成"还没填"**：占位会让对账器与自检无法判定，
 *   结果是"门禁一片红"或"门禁形同不存在"，两种都比不改更糟。 */
/* 历史：旧版模板用过 `BOARD_UNSET (0xFFu)` 当"还没填"的占位。它已退役 ——
 * 0xFF 既不是有效端口也不是有效引脚，忘了替换**不会有编译错误**，只会
 * "配了却什么也不动"（最难查的一类静默失效）。具体缺省值没有这个毛病。 */

/* --------------------------------------------------------------- 芯片身份 ----
 * ★ 这一节**不只是给 C 用的**：顶层 CMakeLists.txt 会按名字读这几个宏，
 *   写进 `build/<预设>/board.env`，`Tools/fw.py` 再从那里取器件名 / 内存容量。
 *   ⇒ "这块芯片是什么"全工程只有这一处；换芯片改这里，烧录脚本和体积门禁
 *     跟着变，不会漏改（docs/11 §2）。
 *
 * ⚠️ 改这里只是改"脚本怎么称呼它"，**不会改变链接脚本**。换芯片还必须同步
 *    `CHIP_MODEL_FLASH.ld` 的 MEMORY 段、`startup_CHIP_MODEL.s`、`.ioc` 与
 *    `cmake/stm32cubemx/CMakeLists.txt`（生成物）—— 清单见 docs/10 §D 与
 *    README §11「换芯片时这三处必须同步」。
 *
 * 填写说明：
 *   BOARD_MCU_NAME     ← CubeMX 里的**完整型号**（带尾缀，如 xxxVGTx）
 *   BOARD_JLINK_DEVICE ← SEGGER 的**短名**（无尾缀）—— 用 `python Tools/fw.py env`
 *                        打印的"器件"一行核对，写错的表现是烧录时才连不上
 *   BOARD_*_KB         ← 新芯片的 FLASH / RAM / CCM 容量，**必须与链接脚本的
 *                        MEMORY 段逐项一致**，否则体积门禁算的是假数
 *                        （填 0 = 未填，sizecheck 会因此报错 —— 这是故意的） */
#define BOARD_MCU_NAME "STM32F407VGTx"      /* ← 缺省：CubeMX 完整型号（带尾缀 x） */
#define BOARD_JLINK_DEVICE "STM32F407VG"  /* ← 缺省：J-Link 器件名（无尾缀） */

#define BOARD_FLASH_KB 1024U /* ← 缺省：与链接脚本 FLASH 段一致。0 = 未填 */
#define BOARD_RAM_KB 128U   /* ← 缺省：与链接脚本 RAM 段一致 */
#define BOARD_CCM_KB 64U   /* ← 缺省：与链接脚本 CCMRAM 段一致；无 CCM 的芯片填 0 */

/* ---------------------------------------------------------------- 时钟源 ----
 * 填写说明：外部晶振频率 + 目标主频。**PLL 参数不在这里** ——
 * 它们在 `Core/Src/main.c` 的 `SystemClock_Config()`（CubeMX 生成）。
 * 这里登记的只是"来源是多少 / 目标是多少"两个事实。
 *
 * ⚠️ 换晶振时，本文件与 CubeMX 的 RCC **必须同时改**，且 PLL 参数要重算。
 *     只改一处 ⇒ `python Tools/fw.py lint` 会报确定性矛盾（那正是它存在的理由）。
 * ⚠️ HSE 频率还必须与 `stm32f4xx_hal_conf.h` 的 HSE_VALUE 一致 ——
 *     那条一致性由 `fw.py lint` 的 CubeMX 对账（.ioc 的 RCC.HSE_VALUE）兜底，
 *     所以这里不写 `#error` 断言（HSE_VALUE 所在的头只有 HAL 消费者能 include）。 */
#define BOARD_HSE_VALUE 8000000U /* ← 缺省：外部晶振频率（Hz）。0 = 未填 */

/* ⚠️ 仅文档性常量：全工程无引用，运行时主频以 SystemCoreClock 为准。
 *    保留是为了让"目标是这个频率"这件事在配置里可见；
 *    它不是开关，改它不会改变任何行为。 */
#define BOARD_TARGET_SYSCLK_HZ 168000000U /* ← 缺省：目标 SYSCLK（Hz）。0 = 未填 */

/* ---------------------------------------------------------------- 日志出口 ----
 * 默认后端是 **RTT**（走调试探针，不占串口、不打断实时性）——
 * 所以下面这一节**默认不被用到**，它是 `--preset Debug-UART` 的后端配置。
 *
 * 填写说明（本板的日志串口）：
 *   BOARD_LOG_UART_PORT  ← 外设实例号（bsp_log.c 用它选 USARTx 实例）
 *   BOARD_LOG_UART_BAUD  ← 波特率；115200 是通用默认值，通常不用改
 *   TX_* / RX_* / AF     ← **接线事实的登记**，由 `fw.py lint` 与 .ioc 对账
 *                          （保证"登记的接线"和"CubeMX 实际配的"不会漂移）
 *
 * ⚠️ 引脚/复用/时钟**不是**由 Device 层配的 —— 是 CubeMX 生成的
 *    `Core/Src/usart.c` 里的 `HAL_UART_MspInit` 配的（那是 .ioc 的产物）。
 *    Device 层的 bsp_log.c 只调 `HAL_UART_Init`，**刻意不自己定义 MSP**
 *    （两边都定义会 multiple definition，实测链接失败 —— 见 bsp_log.c 说明）。
 *
 * ⇒ 下面这组宏分两类，用途不同，别混：
 *      · `PORT` / `BAUD`        —— **被 bsp_log.c 读**，是后端的行为参数
 *      · `TX_*` / `RX_*` / `AF` —— 登记项，**不参与驱动实现**：改它们不会改变引脚，
 *        改引脚要去 CubeMX 改，再回来更新这几个宏。
 *    ⚠️ 这一区分是实测出来的：原先 Device 层自己配引脚，与生成的 usart.c 撞了
 *       `HAL_UART_MspInit`，`Debug-UART` 预设直接链接失败。 */
#define BOARD_LOG_UART_PORT 1    /* ← 缺省：实例号（USART1 → 1） */
#define BOARD_LOG_UART_BAUD 115200U        /* 通用默认值；非常规波特率再改 */
#define BOARD_LOG_UART_TX_PORT 0 /* ← 缺省：0 = GPIOA … 7 = GPIOH */
#define BOARD_LOG_UART_TX_PIN 9
#define BOARD_LOG_UART_RX_PORT 0
#define BOARD_LOG_UART_RX_PIN 10
#define BOARD_LOG_UART_AF 7      /* ← 缺省：复用号（查数据手册 AF 表） */

/* ------------------------------------------------------------ 外设（登记）----
 * 下面每一节都是"这块板子上有什么"的登记。模板里给的是参考板缺省值（可直接用，换板子改这里）。
 *
 * 填写说明（每个外设都是同样的三步）：
 *   ① 在 CubeMX 里配好该外设（引脚 / 时钟 / DMA / NVIC），保存 .ioc 并生成；
 *   ② `Core/Src/<外设>.c` 由 CubeMX 生成，MSP（引脚 + 时钟）也在那里；
 *   ③ 回到本节把**值**抄进来 —— 引脚写"端口号 + 引脚号"两个宏，
 *      端口号 0=PA … 7=PH（与 `bsp_port_map.h`、`bsp_gpio_port_t` 同序）。
 *   ⚠️ 驱动实现在 `Device/Src/bsp_*.c`，只认这里的宏，不认 "PA9" 这种字符串。
 *   ⚠️ 这里的登记项与 .ioc 不一致 ⇒ `fw.py lint` 报确定性矛盾。
 *   ⚠️ 别留"没有代码读的宏"（孤儿宏）：定义存在、看着像开关，翻成 1 却什么都不
 *      发生。信息写注释里就够 —— 见本文件末尾那段。 */

/* ------------------------------------------------ USART（业务串口）· 登记 ----
 * ⚠️ 若你把日志后端改成 UART，它就**被日志占用了** —— 别再把同一个 USART 当
 *    业务串口用，否则两个消费者抢同一个外设。 */
#define BOARD_USART1_AF 7 /* ← 缺省：USART1 的复用号 */

/* ------------------------------------------------- 板载 SPI Flash（可选）----
 * 板上有 SPI Flash 时，`Device/Src/bsp_spi.c` 与 `Operation/Src/op_flash.c`
 * 可直接用（PC 侧可单测，不需要板子）。
 * 填写说明：SCK / MISO / MOSI 三个信号 + 一个 **软件 CS** ——
 *   CS 由驱动自己拉，所以 CubeMX 里它应配成 GPIO_Output，**不是** SPI 的硬件 NSS。
 * ⚠️ SPI 模式（CPOL / CPHA）必须与器件数据手册一致：CubeMX 默认是模式 0，
 *    而不少 Flash 例程用模式 3。两者器件都支持时能用，不一致会读到全 0 / 全 FF。 */
#define BOARD_SPI1_SCK_PORT 0
#define BOARD_SPI1_SCK_PIN 5
#define BOARD_SPI1_MISO_PORT 0
#define BOARD_SPI1_MISO_PIN 6
#define BOARD_SPI1_MOSI_PORT 0
#define BOARD_SPI1_MOSI_PIN 7
#define BOARD_SPI1_AF 5           /* ← 缺省：SPI1 的复用号 */
#define BOARD_SPI_FLASH_CS_PORT 0 /* ← 缺省：软件 CS 的端口 */
#define BOARD_SPI_FLASH_CS_PIN 4

/* -------------------------------------------------------- SDIO / TF 卡（可选）----
 * 4-bit 模式（通过 SDIO 外设，**不是** SPI 模式）。
 * 填写说明：CLK / CMD / D0..D3 六个信号 + 一个卡检测脚（配 GPIO_Input）。
 * ⚠️ CubeMX 生成的 `MX_SDIO_SD_Init()` 里 `BusWide` 是 **1-bit** ——
 *    这是**对的**：SD 卡必须先 1-bit 初始化、识别后再由
 *    `HAL_SD_WideBusOperation_Config()` 切到 4-bit。别以为配错了。
 * ⚠️ 没插卡时 `HAL_SD_Init()` 必然失败：别让 `Error_Handler()` 因为它停机，
 *    否则"没插卡"会表现成"整块板子不启动"。正确写法是像 `app_init_failed()`
 *    那样**打日志后返回**。 */
#define BOARD_SDIO_CLK_PORT 2
#define BOARD_SDIO_CLK_PIN 12
#define BOARD_SDIO_CMD_PORT 3
#define BOARD_SDIO_CMD_PIN 2
#define BOARD_SDIO_D0_PORT 2
#define BOARD_SDIO_D0_PIN 8
#define BOARD_SDIO_D1_PORT 2
#define BOARD_SDIO_D1_PIN 9
#define BOARD_SDIO_D2_PORT 2
#define BOARD_SDIO_D2_PIN 10
#define BOARD_SDIO_D3_PORT 2
#define BOARD_SDIO_D3_PIN 11
#define BOARD_SDIO_AF 12      /* ← 缺省：SDIO 的复用号 */
#define BOARD_SDIO_DET_PORT 3 /* ← 缺省：卡检测脚的端口 */
#define BOARD_SDIO_DET_PIN 3  /* ← 缺省：卡检测脚；上下拉要与电路一致 */

/* ------------------------------------------------------ USB_OTG_FS（可选）----
 * Device Only 模式。板上器件通常是 USB 座（也常常兼作 DFU 烧录口）。
 * 填写说明：DM / DP 两个信号；**别漏 NVIC** —— 要在 `.ioc` 的 NVIC 里使能
 *   OTG_FS 中断，且 `Core/Src/usb_otg.c` 的 MSP 里要有 `HAL_NVIC_EnableIRQ`。
 *   只配了引脚和时钟而漏了 NVIC 时，现象是"引脚都对但枚举不会发生"。
 * ⚠️ 只做 PCD 层、没有应用层描述符（CDC / MSC）时，主机不会认它 —— 这不是 bug。 */
#define BOARD_USB_OTG_FS_DM_PORT 0
#define BOARD_USB_OTG_FS_DM_PIN 11
#define BOARD_USB_OTG_FS_DP_PORT 0
#define BOARD_USB_OTG_FS_DP_PIN 12

/* ------------------------------------------------------- RTC（可选，无宏）----
 * 板上有 32.768 kHz 晶振（LSE）+ VBAT 电路时，`.ioc` 里激活 RTC 即可，
 * 引脚由 CubeMX 固定（OSC32_IN / OSC32_OUT），所以这里**不需要 BOARD_* 宏**。
 *
 * ⚠️ 配 RTC 的三个坑（缺一个就**静默不激活**：不报错、不生成 rtc.c）：
 *    ① 它的模式是**虚拟引脚** `VP_RTC_VS_RTC_Activate`，不是 `RTC.VirtualMode`；
 *    ② 那个虚拟引脚的 `Signal` 值**要带 IP 前缀** —— `RTC_VS_RTC_Activate`，
 *       不是 XML 里字面写的 `VS_RTC_Activate`；
 *    ③ 时钟源要写 `RCC.RTCClockSelectionARG`（带 `ARG` 后缀的才是代码生成用的，
 *       只写 `RTCClockSelection` 会生成 LSI）。
 *
 * ⚠️ **第四个坑（上板才暴露）**：RTC 要真正走 LSE，**可能必须走 GUI，改 `.ioc` 无效**。
 *    实测链：`HAL_RTC_SetTime` 失败 ⇒ 读 `RCC_BDCR` 见 `LSEON=0` 但 `RTCSEL=01`
 *    ⇒ 查 `SystemClock_Config` 发现压根没有 `RCC_OSCILLATORTYPE_LSE`。
 *    · `RCC.LSEUsed=1` 手写进 `.ioc` **有效**（让 LSE 振荡器被使能）；
 *    · 但 RTC 时钟源手写 `RCC.RTCClockSelectionARG` 可能**被静默忽略**
 *      ⇒ 要在 Clock Configuration 页把 `RTC Clock Mux` 点成 LSE，再 Generate Code。
 *    **判据（三项都要过）**：读 `RCC_BDCR` 得 `LSEON=1` · `LSERDY=1` · `RTCSEL=01`。
 *    ⚠️ **只看"走时正常"不够** —— LSI（±5%）也能走时，几分钟内看不出误差。
 *    ⚠️ **CubeMX 不报错、`fw.py lint` 也不报**（它只对账引脚，不对账时钟源）。
 *    ⚠️ **`.ioc` 不是 API，是 CubeMX 的内部状态快照**：有些字段只从 GUI 写。
 *       改完必须回读**生成代码**或**界面状态**，不能假定"写了就等于生效"。 */

/* ------------------------------------------------------- SWD 调试口（无宏）----
 * SWDIO / SWCLK 两个脚，由 CubeMX 的 `Serial_Wire` 模式固定。
 * **不要**复用为 GPIO，否则烧录/调试会失联（且症状是"探针连不上"，
 * 很容易误判成探针坏了）。 */

/* ---------------------------------------------------------------- 指示灯 ----
 * 心跳灯：`app_poll_at()` 靠它闪。
 * 填写说明：一个 GPIO_Output。
 * ⚠️ 初始电平**必须**与"点亮电平"自洽：既然"高电平点亮"，初始就要 RESET（上电灭），
 *    初始设 SET 等于上电就亮，与"初始应为灭"自相矛盾。 */
#define BOARD_LED_PORT 1 /* ← 缺省：0 = GPIOA … 7 = GPIOH */
#define BOARD_LED_PIN 2  /* ← 缺省：0..15 */

/* ---------------------------------------------------------------- 用户按键 ----
 * 填写说明：一个 GPIO_Input。上下拉**必须与电路一致**（按下为高 ⇒ PULLDOWN。
 *   反过来配成 PULLUP 时，现象是"一直读成按下"，不会报错）。
 * 判据：读 `GPIOx_IDR` 看未按时电平，再按一下看日志 —— 两件事都对才算可用。 */
#define BOARD_KEY_PORT 0
#define BOARD_KEY_PIN 0

/* ---------------------------------------------------------------- 闭环契约 ----
 * AI 自动验证靠这两行标记判定固件是否真的跑起来了（详见 docs/11 §5）。
 * ⚠️ 它们**不是板级事实**，模板不动。改标记必须同步改 `Tools/fw.py`、
 *    `.vscode/tasks.json` 与 `AGENTS.md`，否则自动化会静默失效 ——
 *    这是一条**跨文件契约**。 */
#define BOARD_BOOT_OK_MARKER "[AI_READY]"
#define BOARD_BOOT_FAIL_MARKER "[AI_FAIL]"

/* ============================================================================
 *  附：加"功能开关"时的一道闸门
 *
 *  一个 `#define BOARD_ENABLE_XXX 0` 如果**没有任何代码读它**，它是"孤儿宏"：
 *  定义存在、看着像个开关，翻成 1 却什么都不会发生 —— 这是最难查的一类静默失效。
 *
 *  把意图写成**编译期闸门**，它就不可能被误用：
 *
 *      #define BOARD_ENABLE_IWDG 0
 *      #if BOARD_ENABLE_IWDG
 *      #error "BOARD_ENABLE_IWDG=1，但工程里没有 bsp_iwdg 实现：请先补模块再启用"
 *      #endif
 *
 *  两个效果同时成立：① 记录了"我知道有这个需求，只是还没做"；
 *  ② 谁翻成 1 谁当场看到原因，而不是编译通过、运行无变化。
 *  顺带：宏被 `#if` 引用了，所以它不会变成"定义了却没人读"的孤儿宏。
 * ==========================================================================*/

#endif /* BOARD_CONFIG_H */
