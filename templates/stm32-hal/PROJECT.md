# f407vgt6（四层工程模板母体）

阶段: 模板维护（本工程是**全项目模板母体**——软件+硬件+文档骨架；新项目用 tools/derive_project.py 派生；G2026 即派生实例）

交付物: 模板本体 ✓（四层结构 + Tools 门禁 + docs/00~13 规范手册 + Tools/derive.py 一键派生 + 工作区治理）,
        派生验证 ✓（derive.py --verify 自带 build/test 验收）

门禁基线: （下次跑 `fw.py build --clean-first` 与 `fw.py test` 后回填数字与日期）

待办: 1. 模板演进项写在这里（改 AGENTS/docs 规范走 docs/13 提案流程）

回退点: git 5cada31（工作流重构 批次 4/4：三区迁移）

下一步判据: 派生一个新工程，`fw.py verify` 退出码 0
