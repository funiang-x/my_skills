# 项目门 — 项目级规则片段

放进某个**项目**根目录的 `AGENTS.md`（或 `.trae/rules/project_rules.md` / `CLAUDE.md`）。
项目门和全局门一样：**薄转发层**——只指路，不复制正文。

---

<!-- my_skills:project-door -->
[MUST] 开工前置：先读本机 skill 库的 `ROUTE.md`（默认 `~/.ai-skills/ROUTE.md`），
按其 §1 四步执行（拿证 → 判类 → 装 skill → 读参考），先输出 `[ROUTE]` 声明再干活。

## 本项目任务类型（按需增删）

- <示例：`软件/编码`——本仓是 STM32 固件工程，写代码必载 `ponytail`>
- <示例：`硬件/落图`——本项目原理图在嘉立创 EDA，先确认桥连通>
<!-- /my_skills:project-door -->

---

**用法建议**：项目门里最有价值的是"本项目常用任务类型"这一小节——它把通用装配表
（`ROUTE.md` §2）收窄到本项目，AI 判类更快更准。任务类型名必须与 `ROUTE.md` 一致。
