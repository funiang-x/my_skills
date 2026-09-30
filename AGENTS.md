# AGENTS.md — 给 agent 的入口（薄转发层）

> 本文件只指路，不装规则。**规则正文只有一份**：`ROUTE.md`。

## [MUST] 开工前置

任何任务动手前，按 `ROUTE.md` §1 走四步，然后**先输出 `[ROUTE]` 声明**再干活：

0. **拿证**：`python tools/preflight.py <类型>`（把该读的 skill 条款正文打印出来 + 发开工证）
1. **判类**：`ROUTE.md` §2 装配清单
2. **装 skill**：该类型**全部**必载 skill（全都要，不是挑一个）
3. **读参考**：按「必读」列打开文件

## 本仓库速览

- **这是什么**：嵌入式全流程的 skill 集（选型 → 原理图 → 固件 → 构建/烧录/调试 → 工程方法），见 `README.md`
- **两份文档分工**：`ROUTE.md` = **用哪个 skill**（任务视图）· `WORKFLOW.md` = **按什么阶段做**（阶段视图，含交付物与验收判据）
- **skill 位置**：仓库根级 `<name>/SKILL.md`（每个含 `SKILL.md` 的一级目录 = 一个 skill）
- **公开层 23 个**（2026-09-30 起含 6 个自研件：`build-cmake` / `flash-jlink` / `debug-jlink` /
  `serial-monitor` / `serial-shell` / `static-analysis`）；本地层只剩 2 个第三方大件（`easyeda-agent` / `ppt-master`，
  缺失时 `doctor` 只警告——降级路径见 `ROUTE.md` §2.7 与 `PREREQUISITES.md` §3）
- **三条命令**：`python tools/skillman.py install | sync | doctor`（装到各客户端 / 更新 / 体检）
- **加/改/退 skill**：按 `ROUTE.md` §2.3「环境/改技能」规程
- **硬闸门**（可选装）：`hooks/skill_gate.py`——没拿开工证就改本库 / 跑库内脚本，会被拦下
