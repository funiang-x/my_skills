#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_report.py —— 交付物自检：链够不够格。

分工：**链的结构（断链/孤儿/互指/缺挂载/回环）交给 `chain.py`** —— 本脚本不重复实现，
只做外围五件事：

  1. 调 `chain.py` 的检查，把它的失败项并进来
  2. **冲突登记段**存在（一条冲突都没有，通常意味着没真去核一手）
  3. **验证记录**表非空（跑过什么，或写明"跑不了 + 为什么"）
  4. **拷问清单** 5~8 条
  5. 引用的**本地路径真实存在**（引用即合同）

用法：
    python check_report.py <报告.md> [--root <工程根>] [--quiet]
    python check_report.py --selftest

零依赖（只用标准库）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain as CH  # noqa: E402

PATH_RE = re.compile(r"`([^`\n]+)`")


def check(md_path: str, root: str | None, quiet=False):
    fails, warns = [], []
    text = open(md_path, encoding="utf-8").read()

    # 1 链的结构（委托 chain.py，不重复实现）
    r = CH.report(md_path, quiet=True)
    fails.extend(r["fails"])
    warns.extend(r["warns"])
    if not r["chains"]:
        fails.append("一条链都没有（链节表缺失）")

    # 2 讲解覆盖：链节表只写"是什么"，讲解才写"为什么/怎么做/边界/失效"
    all_ids = [nid for c in r["chains"] for nid in c["nodes"]]
    miss = [nid for nid in all_ids if not r["talks"].get(nid)]
    if miss:
        if len(miss) == len(all_ids):
            fails.append("**一个链节都没写讲解** —— 只有链节表（是什么），没有多角度讲解")
        elif len(miss) > len(all_ids) * 0.3:
            warns.append("有 %d/%d 个链节没写多角度讲解（%s%s）"
                         % (len(miss), len(all_ids), ", ".join(miss[:6]),
                            " …" if len(miss) > 6 else ""))
    else:
        # 有讲解时，至少要有两个角度（一个角度等于没说）
        thin = [nid for nid in all_ids if len(r["talks"].get(nid) or []) < 2]
        if thin:
            warns.append("这些链节的讲解只有 1 个角度（等于没说）：%s" % ", ".join(thin[:6]))

    # 3 冲突登记
    if "[冲突]" not in text and "无冲突" not in text:
        warns.append("没有「冲突登记」段 —— 一条冲突都没有，通常意味着没真去核一手")

    # 3 验证记录非空
    m = re.search(r"验证记录(.*?)(?=\n##\s|\Z)", text, re.S)
    if not m:
        fails.append("没有「验证记录」段")
    else:
        n = len([ln for ln in m.group(1).split("\n")
                 if ln.lstrip().startswith("|") and not re.match(r"^\s*\|[\s:\-|]+\|\s*$", ln)])
        if n <= 1:
            fails.append("验证记录是空的（跑过什么 / 或写明跑不了的原因）")

    # 4 拷问清单条数
    m = re.search(r"拷问清单(.*?)(?=\n##\s|\Z)", text, re.S)
    if not m:
        fails.append("没有「拷问清单」段")
    else:
        n = len(re.findall(r"^\s*(?:\d+[\.、)]|[-*])\s+\S", m.group(1), re.M))
        if n == 0:
            fails.append("拷问清单是空的")
        elif n < 5:
            warns.append("拷问清单只有 %d 条（要求 5~8 条）" % n)
        elif n > 8:
            warns.append("拷问清单有 %d 条（要求 5~8 条，太多没人答）" % n)

    # 5 引用路径存在（只查"看着像相对路径"的：含分隔符 + 有扩展名 + 无通配符）
    if root:
        for p in sorted(set(PATH_RE.findall(text))):
            if p.startswith(("http://", "https://", "~")) or " " in p:
                continue
            if any(c in p for c in "*?<>{}"):
                continue
            if "/" not in p and "\\" not in p:
                continue
            if not re.search(r"\.(c|h|md|py|json|ioc|ld|txt|csv|html|cir|epro2)$", p):
                continue
            if not os.path.exists(os.path.join(root, p)):
                warns.append("引用的路径不存在（引用即合同）：%s" % p)

    if not quiet:
        for f in fails:
            print("FAIL  %s" % f)
        for x in warns:
            print("WARN  %s" % x)
        print("\n%s：失败 %d · 警告 %d" % (os.path.basename(md_path), len(fails), len(warns)))
    return fails, warns


GOOD = """# X · 逻辑链（2026-01-01）
## 链节（硬件链）

| ID | 做什么 | 人话 | 上游 | 下游 | 载体 | 单位 | 阶段 | 执行体 | 证据 |
|---|---|---|---|---|---|---|---|---|---|
| H01 | 端接 | 配成50Ω，不配就反射 | — | H02 | a | mV | 输入 | Analog | s |
| H02 | 放大 | 补回前级损失 | H01 | — | b | mV | 放大 | Analog | s |

## 链节（软件链）

| ID | 做什么 | 人话 | 上游 | 下游 | 载体 | 单位 | 阶段 | 执行体 | 证据 |
|---|---|---|---|---|---|---|---|---|---|
| S01 | 起机 | 时钟不对一切都不对 | — | S02 | c | — | 起机 | Init | s |
| S02 | 采集 | 成块搬运，边采边算会丢样 | S01 | — | d | 码值 | 采集 | Engine | s |

## 分层（软件链 ① 结构层）

| 层 | 归属（职责） | 不许做什么 | 节点 |
|---|---|---|---|
| 应用 | 编排与算法 | 不摸寄存器 | S01,S02 |

## 调用边（软件链 ① 结构层）

| 从 | 到 | 为什么允许 |
|---|---|---|
| 应用 | 驱动 | 经 bsp_* API |

## 附件

### 需求（R）

| ID | 内容 | 挂在链节 | 判据 | 证据 | 强度 |
|---|---|---|---|---|---|
| R1 | 某需求 | H02,S02 | ±5mV | s | 已核 |

### 判据（J）

| ID | 判据 | 守在链节 | 判错症状 | 失败语义 | 证据 |
|---|---|---|---|---|---|
| J1 | x>0 | S02 | 恒 0 | 停机 | s |

### 风险（K）

| ID | 结论 | 挂在链节 | 强度 | 依据 |
|---|---|---|---|---|
| K1 | 某风险 | H02 | 已核 | s |

## 讲解

### H01 · 端接

| 角度 | 内容 |
|---|---|
| 是什么 | 把源阻抗配成 50Ω |
| 为什么 | 不配就有反射 |
| 失效 | 阻抗失配 ⇒ 幅值读数偏高 |

### H02 · 放大

| 角度 | 内容 |
|---|---|
| 是什么 | 放大 8 倍 |
| 为什么 | 补偿前面的分压 |

### S01 · 起机

| 角度 | 内容 |
|---|---|
| 是什么 | 配时钟 |
| 为什么 | 时钟不对一切都不对 |

### S02 · 采集

| 角度 | 内容 |
|---|---|
| 是什么 | 搬一帧 |
| 为什么 | 采集必须成块 |

## 2 · 冲突登记（一手 vs 文档）

[冲突] doc 说 85，ioc 是 12

## 3 · 验证记录

| 跑了什么 | 命令 | 结果 | 跑不了的说明为什么 |
|---|---|---|---|
| 单测 | `fw.py test` | 5/5 | — |

## 4 · 拷问清单（5~8 条，每条含推荐答案）

1. a
2. b
3. c
4. d
5. e
"""


def selftest() -> int:
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "good.md")

        def run(txt):
            open(p, "w", encoding="utf-8").write(txt)
            return check(p, None, quiet=True)

        f, _ = run(GOOD)
        if f:
            print("FAIL 好报告被判失败：%s" % f); ok = False
        # 链断掉（委托 chain.py）
        f, _ = run(GOOD.replace("| H02 | 放大 | 补回前级损失 | H01 |",
                                "| H02 | 放大 | 补回前级损失 | H09 |"))
        if not any("链写错了" in x for x in f):
            print("FAIL 断链没抓到：%s" % f); ok = False
        # 需求没挂载
        f, _ = run(GOOD.replace("| R1 | 某需求 | H02,S02 |", "| R1 | 某需求 |  |"))
        if not any("R R1 没有挂到" in x for x in f):
            print("FAIL 「需求没挂载」没抓到：%s" % f); ok = False
        # 验证记录空
        f, _ = run(GOOD.replace("| 单测 | `fw.py test` | 5/5 | — |", ""))
        if not any("验证记录是空的" in x for x in f):
            print("FAIL 空验证记录没抓到：%s" % f); ok = False
        # 拷问清单不足
        f, w = run(GOOD.replace("3. c\n4. d\n5. e\n", ""))
        if not any("拷问清单只有" in x for x in w):
            print("FAIL 拷问清单条数没被检查：%s" % w); ok = False
        # 只有一条链也算通过（不强制两条）
        f, _ = run(GOOD.replace("## 链节（软件链）", "## 链节（软件链·注释）"))
        if f:
            print("FAIL 单链报告被判失败：%s" % f); ok = False
        print("selftest: %s" % ("OK" if ok else "FAILED"))
        return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="链式交付物自检")
    ap.add_argument("report", nargs="?")
    ap.add_argument("--root", default=None)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.report or not os.path.isfile(a.report):
        print("用法：check_report.py <报告.md> [--root <工程根>]；或 --selftest", file=sys.stderr)
        return 2
    fails, _ = check(a.report, a.root, quiet=a.quiet)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
