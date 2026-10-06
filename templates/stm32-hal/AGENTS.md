# AGENTS.md — 项目模板 templet（软件+硬件+文档 全格式骨架）

<!-- my_skills:project-door -->
[MUST] 开工前置：先读 skill 库的 `C:/Users/funiang/.ai-skills/ROUTE.md`，按其 §1 走四步
（拿证 → 判类 → 装 skill → 读参考），**先输出 `[ROUTE]` 声明**再干活。
拿证命令：`python C:/Users/funiang/.ai-skills/tools/preflight.py <任务类型>`。

## 本工程的状态落点

当前进度与门禁基线只认工程根的 `PROJECT.md`。**只在跨阶段或改基线时写它。**
<!-- /my_skills:project-door -->

> **这是模板母体**：新项目用 `tools/derive_project.py` 从这里派生（骨架+约定+工具+固件全带走）。
> firmware/ 内部的硬规则见 [`firmware/AGENTS.md`](firmware/AGENTS.md)（四层 R1~R6、门禁口径）。

## AI 工作产物落点（[MUST]）

- 会话临时产物（dump / 探针脚本 / JSON 证据 / 备份 / 缓存）**只许落 `<工程根>/_work/<任务名>/`**；
  禁止散落到工程根与任何源码目录。
- 只有**定稿结论**才写成编号文档进 `docs/` 或 `hardware/`，并到 `docs/INDEX.md` 登记——没登记=不存在。
- 文档口径：编号接续目录最大号；文件名 `NN-主题-YYYYMMDD.md`；H1 `# NN · 标题（日期）`；
  **引用的本地路径必须真实存在**（引用即合同）。
- `hardware/` 只放编号文档与 `data/`（被引用数据）；可复用工具写 `tools/`；历史证据进 `_archive/`。
- `_archive/` 被 git 忽略：`rg` 默认搜不到——搜证据加 `--no-ignore` 或读 `_archive/MANIFEST.md`
  （归位器每次运行自动重生成）。
- 清扫：`python tools/tidy_workspace.py`（默认 dry-run，`--apply` 执行；`_work` 产物 14 天自动过期）。
