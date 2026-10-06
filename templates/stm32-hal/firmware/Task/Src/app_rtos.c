/* ============================================================================
 *  app_rtos.c —— 任务体与节拍（Task 层）
 *
 *  ⚠️ 本文件**只 include `app.h`**，不直接碰 Device / HAL。
 *     取时间是组合根（app.c）内部的事 —— 那样"Task 里谁能碰硬件"
 *     就只有唯一答案，可以 grep 出来。
 *
 *  ⚠️ 本文件也不 include Operation 的头：任务只调 `app_poll()` 这一个入口。
 *     业务变复杂时，在 app.c 的 app_poll() 里挂更多显式入口，而不是在这里堆。
 *
 *  ★ 为什么循环体在本文件、而不在 `Core/Src/freertos.c`：
 *    见 app_rtos.h 的文件头（CubeMX 会强制重建 defaultTask，不跟它斗）。
 *
 *  ★ defaultTask 的定位（来自 G2026 派生实测，2026-09-27 回移）：
 *    CubeMX 会**强制保留** `.ioc` 里的 defaultTask（在 .ioc 里删掉它，
 *    下次 Generate Code 也会被补回来，实测过）；而且 CubeMX 6.15 对"静态任务"
 *    的代码生成有 bug（`xTaskCreateStatic` 会生成 `.cb_mem = &NULL`，编不过）。
 *    ⇒ 派生工程要做多任务时的推荐姿势：**defaultTask 就当最低优先级的
 *      Task_Sys**（心跳/喂狗/栈高水位），业务任务另建文件用
 *      `xTaskCreateStatic` 静态创建 —— 参考 G2026 工程的 Task/Src/app_tasks.c。
 * ==========================================================================*/
#include "app_rtos.h"

#include "app.h"
#include "project_config.h"

#include "cmsis_os.h"

void app_rtos_run(void) {
    /* ★ 循环体只负责"什么时候做"，不负责"做什么" ——
     *   周期逻辑一律做成**显式入口**（app_poll），见 docs/07 §周期逻辑做成显式入口。
     *   这样将来加任务 / 改节拍都在本层动，不用碰生成物。 */
    for (;;) {
        app_poll();
        (void)osDelay(APP_TICK_PERIOD_MS); /* 返回值不用 —— 挂起失败即是系统级故障 */
    }
}
