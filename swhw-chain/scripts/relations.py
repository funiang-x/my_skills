#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relations.py —— 工作流 ②：抽"关系"（函数定义 / 调用边 / include 依赖）。

⚠️ **它是定位器，不是阅读的替代品。** 抽出来的边用来回答"该去读哪几个文件"，
最终结论仍必须来自读全文。

解析是**启发式**的（不引 ctags/clang），已知边界写在本文件末尾。
抽不准时它会**少报**而不是瞎报 —— 少报可以人工补，瞎报会误导。

用法：
    python relations.py <源码根> [--out relations.json] [--md relations.md]
    python relations.py --selftest          # 自检：已知调用图必须抽对

零依赖（只用标准库）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict

SRC_EXT = {".c", ".h", ".cpp", ".hpp", ".cc"}
SKIP_DIRS = {"build", "out", "_work", "_archive", "__pycache__", ".git",
             "Drivers", "Middlewares", "CMSIS", "Third_Party", "vendor", "node_modules"}
# 常见关键字/宏：出现在 `xxx(` 里但不构成调用
NOT_CALLS = {
    "if", "for", "while", "switch", "return", "sizeof", "typeof", "do", "else",
    "defined", "assert", "static_assert", "_Static_assert", "case", "goto",
    "va_arg", "offsetof", "__attribute__", "__asm__", "__builtin_va_arg",
}
DEF_RE = re.compile(
    # 行首；可选的返回类型（必须跟一个空白），然后是函数名 + 参数表 + 函数体
    r"^(?:[A-Za-z_][A-Za-z0-9_ \t\*]*?\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;{}]*)\)\s*\{",
    re.M)
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
INC_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)


def strip_comments(src: str) -> str:
    """去注释与字符串/字符字面量，但**保留换行**（行号才对得上）。"""
    out = []
    i, n = 0, len(src)
    state = None  # None | 'line' | 'block' | 'str' | 'chr'
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state = "line"; out.append(" "); i += 2; continue
            if c == "/" and nxt == "*":
                state = "block"; out.append(" "); i += 2; continue
            if c == '"':
                state = "str"; out.append(" "); i += 1; continue
            if c == "'":
                state = "chr"; out.append(" "); i += 1; continue
            out.append(c); i += 1; continue
        if state == "line":
            if c == "\n":
                state = None; out.append("\n")
            else:
                out.append(" ")
            i += 1; continue
        if state == "block":
            if c == "*" and nxt == "/":
                state = None; out.append("  "); i += 2; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
        # str / chr
        if c == "\\":
            out.append("  "); i += 2; continue
        if (state == "str" and c == '"') or (state == "chr" and c == "'"):
            state = None; out.append(" "); i += 1; continue
        out.append("\n" if c == "\n" else " "); i += 1
    return "".join(out)


def find_functions(clean: str):
    """返回 [(name, def_line, body_start_idx, body_end_idx)]，1-based 行号。"""
    res = []
    for m in DEF_RE.finditer(clean):
        name = m.group(1)
        if name in NOT_CALLS:
            continue
        brace = m.end() - 1  # 正则已把 `{` 吃进匹配
        if brace < 0:
            continue
        depth, i = 0, brace
        while i < len(clean):
            if clean[i] == "{":
                depth += 1
            elif clean[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        res.append((name, clean.count("\n", 0, m.start()) + 1, brace, i))
    return res


def calls_in(body: str):
    return {m.group(1) for m in CALL_RE.finditer(body)} - NOT_CALLS


def layer_of(rel: str) -> str:
    parts = rel.replace(os.sep, "/").split("/")
    return parts[0] if len(parts) > 1 else "(根)"


def analyze(root: str):
    """一次走完，即时返回（不用生成器 —— 惰性会让 sink 为空）。"""
    files, defs, includes, calls = [], {}, {}, []
    for cur, dirs, fnames in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fnames:
            if os.path.splitext(fn)[1] not in SRC_EXT:
                continue
            p = os.path.join(cur, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                raw = open(p, "r", encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            clean = strip_comments(raw)
            files.append(rel)
            includes[rel] = sorted(set(INC_RE.findall(clean)))
            for name, line, bs, be in find_functions(clean):
                defs.setdefault(name, []).append({"file": rel, "line": line})
                calls.append((rel, name, calls_in(clean[bs:be + 1])))
    return files, defs, includes, calls


def run(root: str):
    files, defs, includes, calls = analyze(root)
    owner = {}
    for name, places in defs.items():
        owner[name] = places[0]["file"]  # 同名多处取第一处（报告里会标 ambiguous）

    edges = defaultdict(int)
    for src_file, fn, callees in calls:
        for c in callees:
            dst = owner.get(c)
            if dst and dst != src_file:
                edges[(src_file, dst)] += 1

    cross = {k: v for k, v in edges.items() if layer_of(k[0]) != layer_of(k[1])}
    return dict(root=os.path.abspath(root), files=sorted(files),
                functions={k: v for k, v in sorted(defs.items())},
                includes=includes,
                edges=sorted(({"from": a, "to": b, "calls": n} for (a, b), n in edges.items()),
                             key=lambda d: (-d["calls"], d["from"])),
                cross_layer=sorted(({"from": a, "to": b, "calls": n,
                                     "layers": [layer_of(a), layer_of(b)]}
                                    for (a, b), n in cross.items()),
                                   key=lambda d: (-d["calls"], d["from"])))


def to_md(r: dict) -> str:
    o = io.StringIO()
    w = o.write
    w("# 关系抽取 · %s\n\n" % r["root"])
    w("源文件 %d 个 · 函数 %d 个 · 跨文件调用边 %d 条（其中跨层 %d 条）\n\n"
      % (len(r["files"]), len(r["functions"]), len(r["edges"]), len(r["cross_layer"])))
    w("## 跨层调用边（**这些是要重点核的**）\n\n| 从 | 到 | 调用次数 | 层 |\n|---|---|---|---|\n")
    for e in r["cross_layer"][:80]:
        w("| `%s` | `%s` | %d | %s → %s |\n"
          % (e["from"], e["to"], e["calls"], e["layers"][0], e["layers"][1]))
    w("\n## 全部跨文件调用边（前 120）\n\n| 从 | 到 | 次数 |\n|---|---|---|\n")
    for e in r["edges"][:120]:
        w("| `%s` | `%s` | %d |\n" % (e["from"], e["to"], e["calls"]))
    amb = {k: v for k, v in r["functions"].items() if len(v) > 1}
    if amb:
        w("\n## ⚠️ 同名函数（抽边时只取了第一处，需人工确认）\n\n")
        for k, v in sorted(amb.items())[:40]:
            w("- `%s`：%s\n" % (k, " / ".join("%s:%d" % (x["file"], x["line"]) for x in v)))
    w("\n## 已知边界\n\n"
      "- 函数指针 / 回调 / 宏生成的调用**抽不到**（本工具只认字面 `name(`）。\n"
      "- 条件编译（`#if`）**不展开** —— 两个分支的调用会同时出现。\n"
      "- 同名函数只取第一处定义 ⇒ 见上面的「同名函数」节。\n"
      "- 结论**必须回读源码确认**；本表只用于定位。\n")
    return o.getvalue()


SELFTEST_SRC = """
#include "b.h"
static int helper(int x) { return x * 2; }
int mid(int v) { return helper(v) + helper(v); }
void top(void) { mid(1); helper(2); }
int unused(int q) { return q; }
"""


def selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "A"))
        os.makedirs(os.path.join(d, "B"))
        open(os.path.join(d, "A", "a.c"), "w", encoding="utf-8").write(SELFTEST_SRC)
        open(os.path.join(d, "B", "b.c"), "w", encoding="utf-8").write(
            "int helper(int x);\nint other(void){ return 0; }\n")
        r = run(d)
        names = set(r["functions"])
        ok = True
        for must in ("helper", "mid", "top", "unused", "other"):
            if must not in names:
                print("FAIL 没抽到函数 %s（抽到 %s）" % (must, sorted(names))); ok = False
        # helper 在 A/a.c 定义 → mid 与 top 都在同文件，边应为 0（同文件不算跨文件边）
        same = [e for e in r["edges"] if e["from"].endswith("a.c") and e["to"].endswith("a.c")]
        if same:
            print("FAIL 同文件调用不该产生跨文件边：%s" % same); ok = False
        # 注释/字符串里的调用不许被当成边
        open(os.path.join(d, "A", "c.c"), "w", encoding="utf-8").write(
            '/* mid(1); */\nconst char*s="top();";\nint z(void){ return 0; }\n')
        r2 = run(d)
        bad = [e for e in r2["edges"] if e["from"].endswith("c.c")]
        if bad:
            print("FAIL 注释/字符串里的调用被当成了边：%s" % bad); ok = False
        print("selftest: %s" % ("OK" if ok else "FAILED"))
        return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="抽函数定义 / 调用边 / include 依赖（启发式）")
    ap.add_argument("root", nargs="?")
    ap.add_argument("--out", default=None, help="JSON 输出")
    ap.add_argument("--md", default=None, help="Markdown 输出")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.root or not os.path.isdir(a.root):
        print("用法：relations.py <源码根> [--out x.json] [--md x.md]；或 --selftest", file=sys.stderr)
        return 2
    r = run(a.root)
    md = to_md(r)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        print("已写 %s" % a.out)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
        print("已写 %s" % a.md)
    if not a.out and not a.md:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
