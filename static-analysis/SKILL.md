---
name: static-analysis
description: "当需要对嵌入式 C/C++ 代码跑静态分析（cppcheck / clang-tidy）、检查告警与可疑缺陷、或在交付前做一轮代码质量扫描时使用。cppcheck 走目录扫描（自带排除 build/.git/node_modules），clang-tidy 走单文件 + compile_commands.json；工具缺失时明确报环境缺失并给安装指引。"
agent_created: true
---

# 静态分析（cppcheck / clang-tidy）

## [MUST] 开工前置

- **先 `--detect` 确认工具在位**；缺工具就是 `environment-missing`，不要假装跑过。
- **有发现 ≠ 要全改**：先分类（error/warning 先看，style/performance 批量看），逐条给"改/不改+理由"，别无声大改。
- 工具报告与实际冲突时以**编译器与工程门禁**为准，静态分析是补充证据。
- 工程自带 lint 入口（如 `Tools/fw.py lint`）时**优先用它**，本 skill 做补充扫描。

## 适用场景

- 交付前扫一遍告警（空指针、越界、未初始化、拷贝开销等）。
- 接手陌生代码，快速摸清"哪里脏"。
- 配合 MISRA/规范检查做第一轮筛选（最终以人工评审为准）。

## 命令

```bash
S=scripts/static_analyzer.py      # 本 skill 的执行入口（纯标准库，调外部工具）

python $S --detect                                   # 探测 cppcheck / clang-tidy
python $S --cppcheck src Device --include inc        # 目录扫描
python $S --cppcheck                                 # 扫当前目录
python $S --clang-tidy src/main.c --compile-commands build   # 单文件（需 compile_commands.json）
```

安装：cppcheck → 官网或系统包管理器；clang-tidy → LLVM 发行版自带。

## 失败分流（退出码）

| 码 | 分类 | 怎么办 |
|---|---|---|
| 0 | 无发现 | — |
| 1 | 有发现 | 逐条分类给结论（见 [MUST] 第 2 条） |
| 2 | `environment-missing` | 缺 cppcheck / clang-tidy：按提示安装 |
| 3 | 参数问题 | `--clang-tidy` 没给文件等 |

## 输出约定

- cppcheck：按严重度汇总条数 + 前 30 条原文（gcc 模板，可点击定位）。
- clang-tidy：逐文件列 warning/error 条数。
- 结论要落到"下一步做什么"：必修 / 可忽略（附理由） / 转人工评审。