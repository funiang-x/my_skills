#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inventory.py —— 工作流 ①：划范围。

只回答一件事：**这个工程里"自己写的"代码有多少、在哪、生成物有哪些。**
不读内容、不下结论 —— 先划边界再读，是这套流程的第一条纪律。

用法：
    python inventory.py <工程根> [--out scope.md] [--depth 3] [--extra-exclude a,b]

判据：能回答"自研代码多少个文件 / 几层目录 / 生成物单独有多少"。
零依赖（只用标准库）。
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from collections import Counter, defaultdict

# 默认排除：构建产物 / 缓存 / 版本库 / 第三方。**"生成物"不在这里** —— 它是一手资料。
EXCLUDE_DIRS = {
    "build", "out", "dist", "_work", "_archive", "_tmp", "__pycache__",
    ".git", ".svn", ".hg", ".vscode", ".idea", ".cache",
    "node_modules", "venv", ".venv", "env",
    # 第三方 / vendor（按本库的常见形态；工程自己的 AGENTS.md 若另有约定以工程为准）
    "Drivers", "Middlewares", "CMSIS", "Third_Party", "vendor", "third_party",
}

TEXT_EXT = {
    ".c", ".h", ".cpp", ".hpp", ".cc", ".s", ".S", ".py", ".js", ".ts",
    ".cmake", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".ld", ".ioc", ".cfg", ".mk", ".sh", ".ps1", ".bat", ".html", ".css",
}
# 生成物：不算"自研"，也不算"第三方" —— 单独一类（它们最容易推翻文档）
GENERATED_HINT = ("generated", "cubemx", "syscalls", "sysmem", "startup_")


def classify(rel: str, name: str) -> str:
    low = rel.lower() + "/" + name.lower()
    if any(h in low for h in GENERATED_HINT):
        return "generated"
    return "self"


def walk(root: str, depth: int):
    root = os.path.abspath(root)
    rows = []
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(cur, root)
        level = 0 if rel == "." else rel.count(os.sep) + 1
        if level > depth:
            dirs[:] = []
            continue
        for f in files:
            p = os.path.join(cur, f)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            rows.append((os.path.relpath(p, root).replace(os.sep, "/"), f, size))
    return rows


def count_lines(path: str):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="划范围：清点自研代码 / 生成物 / 第三方")
    ap.add_argument("root")
    ap.add_argument("--out", default=None, help="输出 md（不给则打屏）")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--extra-exclude", default="", help="额外排除的目录名，逗号分隔")
    a = ap.parse_args()

    for d in [x.strip() for x in a.extra_exclude.split(",") if x.strip()]:
        EXCLUDE_DIRS.add(d)

    if not os.path.isdir(a.root):
        print("不是目录：%s" % a.root, file=sys.stderr)
        return 2

    rows = walk(a.root, a.depth)
    by_ext = Counter()
    lines_by_ext = Counter()
    buckets = defaultdict(list)
    for rel, name, size in rows:
        ext = os.path.splitext(name)[1] or "(无扩展名)"
        by_ext[ext] += 1
        buckets[classify(rel, name)].append(rel)
        if ext in TEXT_EXT and size < 4 * 1024 * 1024:
            lines_by_ext[ext] += count_lines(os.path.join(a.root, rel))

    out = io.StringIO()
    w = out.write
    w("# 范围清点 · %s\n\n" % os.path.abspath(a.root))
    w("排除目录（%d 类）：%s\n\n" % (len(EXCLUDE_DIRS), ", ".join(sorted(EXCLUDE_DIRS))))
    w("## 总量\n\n| 类别 | 文件数 |\n|---|---|\n")
    for k in ("self", "generated"):
        w("| %s | %d |\n" % ("自研" if k == "self" else "生成物", len(buckets[k])))
    w("\n## 按扩展名（自研 + 生成物）\n\n| 扩展名 | 文件数 | 行数 |\n|---|---|---|\n")
    for ext, n in by_ext.most_common(20):
        w("| `%s` | %d | %s |\n" % (ext, n, lines_by_ext.get(ext, "-")))
    w("\n## 生成物（**单独列 —— 它们是一手资料，最容易推翻文档**）\n\n")
    for rel in sorted(buckets["generated"])[:60]:
        w("- `%s`\n" % rel)
    w("\n## 自研文件（前 200）\n\n")
    for rel in sorted(buckets["self"])[:200]:
        w("- `%s`\n" % rel)

    text = out.getvalue()
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("已写 %s（自研 %d / 生成物 %d 个文件）"
              % (a.out, len(buckets["self"]), len(buckets["generated"])))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
