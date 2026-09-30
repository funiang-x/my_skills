# 全局门 — 用户级规则片段

把下面这一段放进你常用 AI 客户端的**用户级规则文件**（全局 `AGENTS.md` / `CLAUDE.md` 一类）。
`python tools/skillman.py install --apply` 会对你机器上探测到的候选文件自动写入（幂等、带标记块、先备份）。

---

<!-- my_skills:global-door -->
[MUST] 开工前置：任何任务动手前，先读本机 skill 库的 `ROUTE.md`（默认 `~/.ai-skills/ROUTE.md`，
若本仓库 clone 在别处请替换为实际路径），按其 §1 走四步（拿证 → 判类 → 装 skill → 读参考），
**先输出 `[ROUTE]` 声明**再干活。拿证命令：`python ~/.ai-skills/tools/preflight.py <类型>`。
<!-- /my_skills:global-door -->

---

**为什么必须这么短**：全局规则每轮对话都占上下文，写多了反而稀释注意力——
细节都在 `ROUTE.md` 里，这里只放"指针"。

**注意**：如果你把仓库 clone 到别的位置，把上面两个路径都改成实际位置。
