#ifndef PROJECT_CONFIG_H
#define PROJECT_CONFIG_H
/* ============================================================================
 *  project_config.h —— 应用参数与功能开关（**与硬件无关**）
 *
 *  四层架构里的位置（见 docs/01）：
 *    · Task / Operation 都 include 它（本文件在工程根，两层都能看到）
 *    · **它里面不许出现任何 HAL 内容** —— Operation 层要在 PC 上编译，
 *      引了硬件头就编不过。硬件事实一律去 Core/Inc/board_config.h。
 *
 *  分工：
 *    Core/Inc/board_config.h   引脚、时钟、外设实例（"这块板子上有什么"）
 *    project_config.h（本文件）  周期、阈值、功能开关（"产品要怎么做"）
 *
 *  ⚠️ 写业务时把阈值 / 周期 / 开关放这里，**不要散落到 .c 里**（本工程禁止魔数）。
 *     加的时候照下面这条规矩：
 *
 *     · Operation 层的参数**不从本文件读** —— 由 Task 层在初始化时**注入**给
 *       Operation 实例（它是纯逻辑，配置也要当参数进来，那样才好在 PC 上单测）。
 *     · 本文件里**不许出现任何 HAL 内容**（Operation 要在 PC 上编译）。
 *     · 硬件事实（引脚/时钟）不在这儿，去 Core/Inc/board_config.h。
 * ==========================================================================*/

/* ---------------------------------------------------------------- 基本节拍 ---- */

/* 业务节拍：周期任务每次推进的间隔。
 * 模板用 100ms（无 GUI，够用）。⚠️ 派生教训（G2026 实测）：如果派生工程把
 * LVGL 的 `lv_tick_set_cb` 接到 `bsp_tick_ms()` 之外的轮询路径、或 UI 需要低延迟
 * 响应，这个节拍必须降到 10ms 量级 —— 100ms 的轮询粒度会让触摸"粘"、动画一顿一顿。 */
#define APP_TICK_PERIOD_MS 100U

/* 心跳日志周期（让 RTT 上能看出"系统还活着"）。 */
#define APP_HEARTBEAT_PERIOD_MS 5000U

/* ------------------------------------------------------------ FreeRTOS 参数 ----
 * ⚠️ 任务**不要用 CubeMX 的图形界面建** —— CubeMX 里只勾 FreeRTOS 内核（docs/01 规矩 4）。
 *
 * ★ 本工程只有**一个**周期任务，它就是 CubeMX 生成的 `defaultTask`：
 *     栈深 / 优先级   → `.ioc` 的 `FREERTOS.Tasks01`（256 words / 优先级 24）
 *                        ⚠️ 它由 CubeMX 生成，参数**只能在 CubeMX 里给**，
 *                           写在这里的宏不会被读 —— 所以这里不重复定义（避免孤儿宏）。
 *     循环体          → `Task/Src/app_rtos.c` 的 `app_rtos_run()`
 *     ⚠️ 栈深单位是 **word（4 字节）**，不是字节。256 words = 1 KiB。
 *
 * ⇒ **加新任务时**才在下面定义它的参数，并在 `Task/` 层用 `xTaskCreate` 建。
 *   例如：
 *       #define APP_SENSOR_TASK_STACK_WORDS 256U
 *       #define APP_SENSOR_TASK_PRIORITY    4U   // 比 defaultTask(24) 高才抢得到 CPU
 *   ⚠️ 优先级数值越大越优先；`configMAX_PRIORITIES` = 56。 */

/* ------------------------------------------------------- AI 闭环验证标记 ---- */

/* ⚠️ 启动自检**不在上电瞬间跑**，而是延迟这么久、在任务里跑一次。
 *
 * 为什么（实测踩过）：`fw.py verify` 的顺序是"先烧录复位放行、再启动 RTT 主机"。
 * 目标从复位到输出完的那一瞬间，主机**还没挂上**；而 RTT 上行缓冲只有 1024 B
 * 且满则**静默丢** ⇒ 主机挂上时只能读到最早那 1024 B，中间的输出全被丢掉。
 * 实测现象：153 个值只收到 18 个，日志在缓冲容量处直接跳到结束标记 ——
 * 看起来像"算错了"，其实是**采集端来晚了**。
 *
 * 延迟到主机已挂上再跑才是可复现的做法；顺带也不再用几百毫秒拖慢启动。 */
#define APP_TRACE_START_MS 3000U

/* RTT 上行缓冲默认只有 1024 B，模式是 NO_BLOCK_SKIP —— 满则**直接丢**。
 * 批量输出必须分块主动让路：每块留在缓冲容量内，块间延时。
 * ⚠️ 节奏必须按**每一行**计（含表头），否则表头会先灌满缓冲，
 *    后面几十行全被丢掉 —— 丢数据是**静默**的。 */
#define APP_TRACE_DRAIN_LINES 8U
#define APP_TRACE_DRAIN_MS 15U

/* ------------------------------------------------------------ 演示：心跳灯 ----
 * 用一个"纯逻辑"的参数演示四层的走法（docs/10 §A）：
 *     Operation/Inc/op_blink.h   ← 纯逻辑：给定时间，该亮还是该灭
 *     Test/test_op_blink.c       ← PC 单测，`fw.py test` 秒级跑完
 *     Task/Src/app_blink.c       ← 取时间 / 传时间 / 按结论驱动 Device
 *
 * ⚠️ `on_ms + off_ms` 必须 < 2^32（用无符号减法算周期，天然处理回绕）。 */
#define APP_BLINK_ON_MS 500U
#define APP_BLINK_OFF_MS 500U

/* ------------------------------------------------------- 演示：写 SPI Flash ----
 * 一次跨页写最多拆成几段 —— 决定组合根里那个段数组开多大。
 * W25Q128 页 = 256B；起始未对齐时首段不足一页，所以段数会多一个。
 * 按"一次最多写 1KB"给 8 段，够用又省栈（`op_flash_page_count()` 可以先问）。 */
#define APP_FLASH_MAX_SEGS 8

/* --------------------------------------------------------- 功能开关（闸门）----
 * 一个开关如果没有任何代码读它，就是"孤儿宏"（翻成 1 什么都不会发生）。
 * 所以每个开关都配一道编译期闸门 —— 见 docs/07 §功能开关要有闸门。 */

#define APP_ENABLE_IWDG 0
#if APP_ENABLE_IWDG
#error "APP_ENABLE_IWDG=1，但工程里没有 bsp_iwdg 实现：请先补模块再启用"
#endif

/* 置 1 = 上电自检末尾**故意触发 HardFault**，用来验证崩溃取证链路：
 *   HardFault_Handler → bsp_fault_report() → RTT 输出栈帧。
 * ⚠️ 触发后固件**会停机**（bsp_fault_report 是 noreturn，这是预期行为）
 *    ⇒ 默认必须是 0。验完**记得改回 0**，留着会让板子每次上电都死。 */
#define APP_SELFTEST_FAULT 0

#endif /* PROJECT_CONFIG_H */
