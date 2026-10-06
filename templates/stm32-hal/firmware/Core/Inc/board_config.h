#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H
/* ============================================================================
 *  board_config.h —— 板级事实的"唯一来源"（**手写文件**）
 *
 *  换一块板子，只需要改这一个文件：时钟从哪来、日志往哪出、AI 闭环怎么判定。
 *  各层都从这里取值，**不允许再散落硬编码**。
 *
 *  ⚠️ 本文件在 `Core/Inc/` 下，但**不是 CubeMX 生成物** ——
 *     CubeMX 只写它自己清单里的文件，不会碰这里。放心手写。
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
 * ==========================================================================*/

#include <stdint.h>

/* --------------------------------------------------------------- 芯片身份 ----
 * ★ 这一节**不只是给 C 用的**：顶层 CMakeLists.txt 会按名字读这几个宏，
 *   写进 `build/<预设>/board.env`，`Tools/fw.py` 再从那里取器件名 / 内存容量。
 *   ⇒ "这块芯片是什么"全工程只有这一处；换芯片改这里，烧录脚本和体积门禁
 *     跟着变，不会漏改（docs/11 §2）。
 *
 * ⚠️ 改这里只是改"脚本怎么称呼它"，**不会改变链接脚本**。换芯片还必须同步
 *    `STM32F407XX_FLASH.ld` 的 MEMORY 段、`startup_*.s`、`.ioc` 与
 *    `cmake/stm32cubemx/CMakeLists.txt`（生成物）—— 完整清单见 docs/10 §D。 */
#define BOARD_MCU_NAME "STM32F407VGTx"   /* ST / CubeMX 的完整型号（带尾缀 x） */
#define BOARD_JLINK_DEVICE "STM32F407VG" /* J-Link 的器件名（无尾缀） */

/* 内存容量。★ 与 STM32F407XX_FLASH.ld 的 MEMORY 段**必须一致** ——
 * fw.py sizecheck 拿它当分母算占用率，写错了门禁就是假的。
 * F407VG 实际是 SRAM1(112K) + SRAM2(16K) + CCM(64K)；前两者地址连续，
 * 链接脚本合成一个 128K 的 RAM 段，CCM 单列。 */
#define BOARD_FLASH_KB 1024U /* FLASH 段 */
#define BOARD_RAM_KB 128U    /* RAM 段（SRAM1+SRAM2） */
#define BOARD_CCM_KB 64U     /* CCMRAM 段 */

/* ---------------------------------------------------------------- 时钟源 ----
 * 本板：**8MHz** 外部晶振（HSE）→ PLL → SYSCLK = 168MHz。
 *
 *  PLL 参数在 Core/Src/main.c 的 SystemClock_Config()（CubeMX 生成）：
 *      M=4 / N=168 / P=2 / Q=7
 *      VCOin  = 8/4    = 2.000MHz   （RM0090 要求 1~2MHz）
 *      VCOout = 2×168  = 336MHz     （要求 100~432MHz）
 *      SYSCLK = 336/2  = 168MHz
 *      USB    = 336/7  = 48.000MHz  （精确，USB_OTG_FS 需要）
 *
 *  ⚠️ 换晶振时，本文件与 CubeMX 的 RCC **必须同时改**，且 PLL 参数要重算。
 *     只改一处 ⇒ `python Tools/fw.py lint` 会报确定性矛盾（那正是它存在的理由）。 */
#define BOARD_HSE_VALUE 8000000U
#define BOARD_TARGET_SYSCLK_HZ 168000000U

/* ⚠️ 仅文档性常量：全工程无引用，运行时主频以 SystemCoreClock 为准。
 *    保留是为了让"目标是 168MHz"这件事在配置里可见；
 *    它不是开关，改它不会改变任何行为。 */

/* HSE 频率必须与 stm32f4xx_hal_conf.h 的 HSE_VALUE 一致。
 * ★ 不写 `#error` 断言的原因：HSE_VALUE 在 stm32f4xx_hal_conf.h 里，
 *   而那个头只能被 HAL 消费者 include（Common / Operation 拿不到）。
 *   所以这条一致性由 `fw.py lint` 的 CubeMX 对账（.ioc 的 RCC.HSE_VALUE）兜底。 */

/* ---------------------------------------------------------------- 日志出口 ----
 * 默认后端是 **RTT**（走调试探针，不占串口、不打断实时性）——
 * 所以下面这一节**默认不被用到**，它是 `--preset Debug-UART` 的后端配置。
 *
 * 本板：USART1 = PA9(TX) / PA10(RX)，AF7。已由 CubeMX 配置（见 .ioc），
 * 所以 UART 后端是**可直接用**的（不是"宣称支持但没人用"）。
 *
 * ⚠️ 引脚/复用/时钟**不是**由 Device 层配的 —— 是 CubeMX 生成的
 *    `Core/Src/usart.c` 里的 `HAL_UART_MspInit` 配的（那是 .ioc 的产物）。
 *    Device 层的 bsp_log.c 只调 `HAL_UART_Init`，**刻意不自己定义 MSP**
 *    （两边都定义会 multiple definition，实测链接失败 —— 见 bsp_log.c 说明）。
 *
 *  ⇒ 所以下面这组宏分两类，用途不同，别混：
 *      · `PORT` / `BAUD`        —— **被 bsp_log.c 读**，是后端的行为参数
 *      · `TX_*` / `RX_*` / `AF` —— **接线事实的登记**，由 `fw.py lint` 与 .ioc 对账
 *        （保证"登记的接线"和"CubeMX 实际配的"不会漂移）。
 *        它们不参与驱动实现，改它们不会改变引脚 —— 改引脚要去 CubeMX 改。
 *    ⚠️ 这一区分是实测出来的：原先 Device 层自己配引脚，与生成的 usart.c
 *       撞了 `HAL_UART_MspInit`，`Debug-UART` 预设直接链接失败。 */
#define BOARD_LOG_UART_PORT 1     /* 1 = USART1（bsp_log.c 读它选外设实例） */
#define BOARD_LOG_UART_BAUD 115200U
#define BOARD_LOG_UART_TX_PORT 0  /* 0 = GPIOA —— 登记项，见上方说明 */
#define BOARD_LOG_UART_TX_PIN 9
#define BOARD_LOG_UART_RX_PORT 0
#define BOARD_LOG_UART_RX_PIN 10
#define BOARD_LOG_UART_AF 7       /* AF7 = USART1/2/3 —— 登记项 */

/* ------------------------------------------------------------ 外设（已配）----
 * 以下外设由 CubeMX 配置并生成（见 .ioc）。引脚宏列在这里是为了
 * 让"接线事实"有一个可查的地方 —— 驱动实现在 Device/ 下的 bsp_*.c。
 *
 * ✅ 驱动**已就位**（2026-09-23）：`bsp_spi.c` / `bsp_sd.c` / `bsp_rtc.c`
 *    都在 `Device/Src/` 下，且已挂进 `bsp.h` 能力总表。
 *    （本行原先写"还没有 bsp_spi.c / bsp_sd.c"，那是**过时描述**，已修正。）
 *
 * ⚠️ 但**尚未上板验证** —— 只过了"编译 + 符号入库"（`arm-none-eabi-nm` 查得到符号）。
 *    "能编过"证明不了"能跑通"：Flash 读不读得出 JEDEC ID、卡识不识别得了，
 *    必须插上探针实测。**符号入库 ≠ 能跑。**
 *
 * ⚠️ 按键（`BOARD_KEY_*`）目前**只有登记，没有应用** —— 对比 `BOARD_LED_*`
 *    被 `app.c` 用着，按键没有任何 `app_key` / `op_key` 在读它。 */

/* SPI1 —— **板载 SPI Flash（W25Q128，16MB）专用**。
 * 证据：官方例程 014 的 spi_flash.h（`BSP_SPI = SPI1`、`GPIO_AF_SPI1`、
 * `NSS = GPIO_Pin_4`）。**PA4 是软件 CS**，由驱动自己拉，
 * 不是 SPI1 的硬件 NSS（所以 .ioc 里 PA4 保持 GPIO_Output）。
 *
 * ⚠️ SPI 模式：官方例程用 CPOL=High / CPHA=2Edge（模式 3）；
 *    本工程 .ioc 里 SPI1 是 CubeMX 默认（模式 0）。
 *    W25Q128 两种模式都支持，所以能用；要严格对齐例程就改 .ioc。
 *
 * ✅ **已上板验证**（2026-09-23）：读 W25Q128 的 JEDEC ID 得 `0xEF18`
 *    （Winbond + 128Mbit），与期望值**完全一致**。这一个数字同时证明了
 *    引脚接法、AF5 复用、SPI 时钟、**PA4 软件 CS 时序**、命令层全部正确。
 * ⚠️ **读写擦未验证** —— 测试代码已写（`app_flash_rw_test()`，会擦末扇区
 *    并做跨页写读回），但那次烧录因探针 USB 掉线没成功。 */
#define BOARD_SPI1_SCK_PORT 0 /* 0 = GPIOA */
#define BOARD_SPI1_SCK_PIN 5
#define BOARD_SPI1_MISO_PORT 0
#define BOARD_SPI1_MISO_PIN 6
#define BOARD_SPI1_MOSI_PORT 0
#define BOARD_SPI1_MOSI_PIN 7
#define BOARD_SPI1_AF 5           /* AF5 = SPI1/2 */
#define BOARD_SPI_FLASH_CS_PORT 0 /* PA4 · **软件 CS** */
#define BOARD_SPI_FLASH_CS_PIN 4

/* USART1 —— 与"日志出口"共用同一组引脚（见上）。板上**没有 CH340**，
 * 这组脚只引到 **H1 十脚调试座** ⇒ 走 UART 后端要自己接线。
 * ⚠️ 若你把日志后端改成 UART，它就**被日志占用了** ——
 *    别再把 USART1 当业务串口用，否则两个消费者抢同一个外设。 */
#define BOARD_USART1_AF 7

/* --------------------------------------------- 排针上的自由 IO（本模板未配）----
 * 本工程是**模板**：只保留板上真有器件的那些外设。下面这些脚在排针上是通的，
 * 但板上没有对应器件 ⇒ `.ioc` 里**没配**，这里也**不留 `BOARD_*` 宏**。
 *
 * 为什么不留宏：没有代码读的宏是**孤儿宏** —— 定义存在、看着像个开关，
 * 翻成 1 却什么都不会发生（见本文件末尾那段说明）。信息写注释里就够。
 *
 * 派生工程要用时，去 CubeMX 里配好，再回来按 docs/10 §B 加宏：
 *
 *   SPI2    全双工主机   PB10 = P1-23(SCK) · PC2 = P2-15(MISO) · PC3 = P2-17(MOSI)   AF5
 *   USART2  异步串口     PA2  = P1-1 (TX)  · PA3 = P1-6 (RX)                         AF7
 *
 * ⚠️ 这是**排针位置**，不是板载器件 —— 别以为板上有第二个 SPI / 第二个串口。
 * ⚠️ SPI2 是外接屏的常用选择（PB10–PB14 连续 5 脚，接线最短）。
 *    2026-09-26 按"模板只留板载器件"从 `.ioc` 移除；派生工程驱动 ILI9341
 *    那类屏时，先在 CubeMX 里把 SPI2 配回 Full-Duplex Master
 *    （SPI1 的 PA5/6/7 被板载 W25Q128 占了，用不了）。
 * --------------------------------------------------------------------------*/

/* USB_OTG_FS —— Device Only 模式，PA11(DM) / PA12(DP)。
 * 板上器件：**Type-C 座** —— 同时是 USB DFU 烧录口（按住 SW3/BOOT0 再复位
 * 进 ROM bootloader，见 docs/11 §4）。⚠️ DFU 只能烧录、**看不到日志**。
 *
 * ✅ `NVIC.OTG_FS_IRQn` 已使能（抢占优先级 5）⇒ `stm32f4xx_it.c` 里有
 *    `OTG_FS_IRQHandler`，`usb_otg.c` 的 MSP 里有 `HAL_NVIC_EnableIRQ`。
 *    （2026-09-22 之前这条是缺的，那时引脚时钟都配了但**枚举不会发生**。）
 * ⚠️ 仍未上板验证：能不能真的枚举成功，要插上 USB 才知道。 */
#define BOARD_USB_OTG_FS_DM_PORT 0 /* 0 = GPIOA */
#define BOARD_USB_OTG_FS_DM_PIN 11
#define BOARD_USB_OTG_FS_DP_PORT 0
#define BOARD_USB_OTG_FS_DP_PIN 12

/* SDIO —— **板载 TF 卡座 CARD1**，4-bit 模式（不是 SPI）。
 *
 * ✅ `NVIC.SDIO_IRQn` 已使能（抢占优先级 5）。
 * ✅ `PD3`（卡检测）已配成 GPIO_Input + 上拉。
 * ✅ **卡检测已上板验证**（2026-09-23）：未插卡时自检正确报出"TF 卡未插入"。
 * ⚠️ **卡的读写未验证** —— 手上没卡，插卡后跑 `bsp_sd_init()` 才知道。
 *
 * ⚠️ **「启动绑架」问题已修复**（2026-09-23 上板实测后）：
 *    `MX_SDIO_SD_Init()` 里的 `HAL_SD_Init()` 在**没插卡时必然失败**，
 *    而它原来调 `Error_Handler()` → `app_panic()` → **整块板子不启动**。
 *    实测调用栈：Reset_Handler → main → MX_SDIO_SD_Init → Error_Handler → app_panic。
 *    修法：`Error_Handler` 改调 `app_init_failed()`（打日志后返回，不停机）。
 *    ⇒ 现在没插卡也能正常启动，只是多一行 `[E]` 日志。
 *
 * ⚠️ 试过但**无效**的修法（别再试一遍）：
 *    把 SDIO 从 `.ioc` 的 `ProjectManager.functionlistsort` 里删掉，
 *    或把该条目末位改成 `HAL-false` —— 两者都试过，`MX_SDIO_SD_Init()`
 *    仍留在 `main.c`。CubeMX 那个「Initialize all configured peripherals」
 *    区块会把**所有已配外设**都列上，压根不看 `functionlistsort`。
 *
 * ⚠️ CubeMX 生成的 `MX_SDIO_SD_Init()` 里 `BusWide` 是 **1-bit** ——
 *    这是**对的**：SD 卡必须先 1-bit 初始化、识别后再由
 *    `HAL_SD_WideBusOperation_Config()` 切到 4-bit。别以为配错了。 */
#define BOARD_SDIO_CLK_PORT 2 /* 2 = GPIOC */
#define BOARD_SDIO_CLK_PIN 12
#define BOARD_SDIO_CMD_PORT 3 /* 3 = GPIOD */
#define BOARD_SDIO_CMD_PIN 2
#define BOARD_SDIO_D0_PORT 2
#define BOARD_SDIO_D0_PIN 8
#define BOARD_SDIO_D1_PORT 2
#define BOARD_SDIO_D1_PIN 9
#define BOARD_SDIO_D2_PORT 2
#define BOARD_SDIO_D2_PIN 10
#define BOARD_SDIO_D3_PORT 2
#define BOARD_SDIO_D3_PIN 11
#define BOARD_SDIO_AF 12 /* AF12 = SDIO */
/* PD3 = 卡检测（`.ioc` 里配成 GPIO_Input + 上拉，Label = SD_CARD_DET，
 * 所以 main.h 里有 `SD_CARD_DET_Pin` / `SD_CARD_DET_GPIO_Port`）。
 * 板上经 R20（47k）上拉到 3V3 ⇒ **插卡 = 低电平**。 */
#define BOARD_SDIO_DET_PORT 3 /* 3 = GPIOD */
#define BOARD_SDIO_DET_PIN 3

/* ---------------------------------------------------------------------- RTC ----
 * 板上有 32.768 kHz 晶振（LSE，PC14/PC15）+ VBAT 电路，`.ioc` 里已激活 RTC。
 * **时钟源 = LSE**（生成代码 `rtc.c` 的 `HAL_RTC_MspInit` 里
 * `RTCClockSelection = RCC_RTCCLKSOURCE_LSE`）—— 比内部 LSI 精度高得多。
 *
 * ⚠️ 配 RTC 的三个坑（2026-09-22 实测，缺一个就**静默不激活**：
 *    不报错、不生成 `rtc.c`）：
 *    ① 它的模式是**虚拟引脚** `VP_RTC_VS_RTC_Activate`，不是 `RTC.VirtualMode`；
 *    ② 那个虚拟引脚的 `Signal` 值**要带 IP 前缀** —— `RTC_VS_RTC_Activate`，
 *       不是 XML 里字面写的 `VS_RTC_Activate`；
 *    ③ 时钟源要写 `RCC.RTCClockSelectionARG`（带 `ARG` 后缀的才是代码生成用的，
 *       只写 `RTCClockSelection` 会生成 LSI）。
 *
 * ✅ **已上板验证**（2026-09-23）：设时间成功 + 5 秒内走了 5 秒。
 *
 * ⚠️ **第四个坑（上板才暴露，花了两轮才修对）**：RTC 要真正走 LSE，
 *    **必须走 GUI，改 `.ioc` 无效**。
 *
 *    现象链：`HAL_RTC_SetTime` 失败 ⇒ 读 `RCC_BDCR` 见 `LSEON=0` 但 `RTCSEL=01`
 *    ⇒ 查 `SystemClock_Config` 发现**压根没有 `RCC_OSCILLATORTYPE_LSE`**。
 *
 *    ① **`RCC.LSEUsed=1` 手写进 `.ioc` 有效** —— 它让 LSE 振荡器被使能。
 *    ② **但 RTC 时钟源不行**：手写 `RCC.RTCClockSelectionARG=RCC_RTCCLKSOURCE_LSE`
 *       **CubeMX 不接受**（不报错、不删、静默忽略，界面仍显示 LSI）。
 *       ⇒ **必须在 Clock Configuration 页把 `RTC Clock Mux` 点成 LSE**，
 *         再 Generate Code。（旧文档 `docs/guides/cubemx_clock_config.svg`
 *         已删除，控件位置以 CubeMX 界面为准。）
 *    ③ 改对之后 CubeMX 会自动去掉 LSI（生成代码里 `RCC_OSCILLATORTYPE_LSI` 消失）
 *       —— 这是正确的收敛，别以为它漏了。
 *
 *    **判据（三项都要过）**：读 `RCC_BDCR`（0x40023870）
 *      `LSEON=1` · `LSERDY=1` · `RTCSEL=01`
 *    修好后实测 `0x00008103` ✓（修之前是 `0x00008100`）。
 *    ⚠️ **只看"走时正常"不够** —— LSI（±5%）也能走时，5 秒内看不出误差。
 *       实测旁证：RTC 用 LSI 跑了 27 分钟，时间漂了 10 分钟。
 *
 *    ⚠️ **CubeMX 不报错、`fw.py lint` 也不报** —— 它只对账引脚，不对账时钟源。
 *    ⚠️ **`.ioc` 不是 API，是 CubeMX 的内部状态快照**：有些字段只从 GUI 写。
 *       改完必须回读**生成代码**或**界面状态**，不能假定"写了就等于生效"。 */

/* SWD 调试口 —— PA13(SWDIO) / PA14(SWCLK)。**不要**复用为 GPIO，
 * 否则烧录/调试会失联（且症状是"探针连不上"，很容易误判成探针坏了）。 */

/* ------------------------------------------------------------------ 指示灯 ----
 * **PB2 = 板上 LED2**，两条独立证据：① 原理图标 `PB2 LED&BOOT1`；
 * ② 官方例程 002 用 `GPIO_SetBits(GPIOB, GPIO_Pin_2)` 点灯 ⇒ **高电平点亮**。
 * CubeMX 里配成 GPIO_Output（推挽、无上下拉、低速），**初始电平 RESET（低）**，
 * 即上电是灭的。
 *
 * ⚠️ 初始电平**必须**是 RESET：既然"高电平点亮"，初始设 SET 就等于**上电就亮**，
 *    与"初始应为灭"自相矛盾。
 *    （2026-09-23 修正：本行原先误写成"初始电平 SET（高）"，与 `.ioc` 里的
 *      `PB2.PinState=GPIO_PIN_RESET` 不符。**代码一直是对的，错的是这条注释** ——
 *      这类"文档与实现不符"比代码 bug 更危险，因为它会误导后续判断。）
 *
 * ⚠️ PB2 同时是 **BOOT1**，板上带 10k 下拉（保证默认从 Flash 启动）。
 *    `BOOT0 = 0` 时 PB2 不参与启动模式判定，所以当 LED 用没有副作用。
 * ⚠️ 引脚事实已交叉核对，但**点灯本身未上板实测**。 */
#define BOARD_LED_PORT 1 /* 1 = GPIOB */
#define BOARD_LED_PIN 2

/* ---------------------------------------------------------------- 用户按键 ----
 * **PA0 = 板上 SW2**，**按下 = 高电平**。两条独立证据：
 * ① 原理图 SW2 上端接 +3V3、且配 10k 下拉；② 官方例程 006 读 `== SET` 判为按下。
 * CubeMX 里配成 GPIO_Input + **PULLDOWN**（与"按下为高"一致）。
 *
 * ✅ **已上板验证**（2026-09-23）：
 *    · 读 `GPIOA_IDR` 得 PA0 = 0（未按 + 下拉生效）
 *    · RTT 捕获到 `[SELFTEST] 按键 按下` 与 `按键 松开`
 *    ⇒ 电路、上下拉、GPIO 配置、状态变化检测全部正确。 */
#define BOARD_KEY_PORT 0 /* 0 = GPIOA */
#define BOARD_KEY_PIN 0

/* ---------------------------------------------------------------- 闭环契约 ----
 * AI 自动验证靠这两行标记判定固件是否真的跑起来了（详见 docs/11 §5）。
 * 改标记必须同步改 `Tools/fw.py`、`.vscode/tasks.json` 与 `AGENTS.md`，
 * 否则自动化会静默失效 —— 这是一条**跨文件契约**。 */
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
