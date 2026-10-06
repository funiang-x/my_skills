# Trae 项目规则 — 四层固件工程（f407vgt6 模板）

<!-- my_skills:project-door -->
[MUST] 开工前置：先读 skill 库的 `C:/Users/funiang/.ai-skills/ROUTE.md`，按其 §1 走四步
（拿证 → 判类 → 装 skill → 读参考），**先输出 `[ROUTE]` 声明**再干活。
拿证命令：`python C:/Users/funiang/.ai-skills/tools/preflight.py <任务类型>`。

## 本工程的状态落点

当前进度与门禁基线只认工程根的 `PROJECT.md`（字段定义见
`C:/Users/funiang/.ai-skills/framework/阶段状态.md`）。**只在跨阶段或改基线时写它。**
<!-- /my_skills:project-door -->

本目录是四层固件工程模板（STM32F407）。动手前**先读本目录的 `AGENTS.md`**
（工程级 AI 手册：硬规则 / 门禁口径 / 安全边界），规范细节在 `docs/00~13`。

- 写/改代码：最懒可用解（ponytail 风格），完成前过本工程 `Tools/fw.py` 七道门禁
  （零告警只在 `--clean-first` 后算数；不许加 `-Wno-*` 消错）。
- AI 边界：不烧录（先与人确认）、不下单、不 `git reset --hard`、不擦片、
  改 `.ioc` 引脚时钟前先问人。
- 全流程与分工背景见 `C:\Users\funiang\Desktop\Project\rules\AGENTS.md`。
- 本文件只指路，不复制规则。