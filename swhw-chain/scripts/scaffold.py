#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scaffold.py —— 生成**一条链**的骨架（MD 给 agent 读 + HTML 给人看）。

产出链模型的空架子：一张链节表（主干）+ 五张附件表（R/F/I/J/K）。
结构见 `references/chain-model.md`；HTML 由 `chain.render_html` 生成（与 MD 同源，
不另立第二份模板）。

用法：
    python scaffold.py --topic G2026信号链 --out <工程根>/docs/chain [--date 20261007] [--force]

零依赖（只用标准库）。
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as RD  # noqa: E402  共用同一份渲染器（HTML 只有这一个来源）

MD_TMPL = """# {title} · 逻辑链（{date_dash}）

> 由 `swhw-chain` 产出。**这是一条链**：主干按顺序相扣，每个链节挂着它的附件。
> 链模型与断链判据见 `~/.ai-skills/swhw-chain/references/chain-model.md`。
> 证据分级：`已核`（直接读到）· `推导`（按物理数学算出）· `待确认`（两种读法都通）。
> 铁律：一手为准 · 先对口径再信数字 · 每个数字有来源 · 待确认必须闭环。

## 0 · 证据边界

| 类别 | 具体 |
|---|---|
| 源码 |  |
| 原理图网表 |  |
| 配置/生成物 |  |
| 跑过的验证 |  |

**明确没读什么**：-

## 1 · 主干是什么

<!-- 一份报告里通常有**两条链**，各画各的（揉在一张图上必然糊）：
       · 硬件链 —— 按**信号处理路径**（器件级）：输入 → 保护 → 滤波 → 放大 → 抗混叠 → 进 ADC
       · 软件链 —— 按**软件架构**（模块/任务级）：起机 → 采集 → 算法 → 呈现
     ID 前缀各自区分（H01… / S01…），附件按 ID 挂到对应链上。 -->

## 链节（硬件链）

> `阶段` = 画图时的横带，自上而下堆叠；`执行体` = 谁在跑这一节（Analog / Init / ISR / Engine / Ui / Driver），画图时按它上色。
> `人话` = 一句"为什么存在"的大白话，**画到节点正面**（"不配就反射"，不是"做端接"）。

| ID | 做什么 | 人话 | 上游 | 下游 | 载体 | 单位 | 阶段 | 执行体 | 证据 |
|---|---|---|---|---|---|---|---|---|---|
| H01 |  |  | — | — |  |  |  | Analog |  |

## 链节（软件链）

> 软件链要画**三层**（chain-model §九）：①结构 = 下面「分层 / 调用边」两张表；
> ②时间 = 本表 `阶段`/`执行体` + 回环 + 时序；③意图 = 本表 `人话` 列（**画到节点正面**，
> 写"为什么存在"，不是"做什么"的复述）。

| ID | 做什么 | 人话 | 上游 | 下游 | 载体 | 单位 | 阶段 | 执行体 | 证据 |
|---|---|---|---|---|---|---|---|---|---|
| S01 |  |  | — | — |  |  |  | Init |  |

## 分层（软件链 ① 结构层）

> **归谁管**：谁调用谁、谁**不许**调谁。`节点` 列填本链链节 ID（逗号分隔）；
> `不许做什么` 与"谁调谁"同等重要 —— 那才是设计意图。

| 层 | 归属（职责） | 不许做什么 | 节点 |
|---|---|---|---|
| 应用 |  | 不摸寄存器；不直接 include 硬件头 | S01 |
| 驱动 |  | 不做业务决策 |  |

## 调用边（软件链 ① 结构层）

> `从` / `到` 填**层名**（渲染成层间箭头）。跨层调用全工程只应有一处；写出第二处 = 分层漏了。

| 从 | 到 | 为什么允许 |
|---|---|---|
| 应用 | 驱动 | 经 bsp_* API；参数注入，不读硬件头 |

## 回环

> **不是单向链的一部分**，所以单列；画图时画在对应链的下方。

| 从 | 到 | 为什么 |
|---|---|---|
|  |  |  |

## 讲解

> **逐节从多个角度讲清楚** —— 链节表只写"是什么"，这里写"为什么 / 怎么做 / 边界 / 失效"。
> 每个链节一个小节：`### <ID> · 标题` + 一张 `| 角度 | 内容 |` 表。
> **角度是自由的**（写什么角度就有什么角度），建议覆盖：
> `是什么`（职责）· `为什么`（设计意图，不这么做会怎样）· `怎么做`（实现 + 参数）
> · `关键数字`（值与推导）· `边界`（什么条件下成立）· `失效`（错了会看到什么现象）。

### H01 · （填标题）

| 角度 | 内容 |
|---|---|
| 是什么 |  |
| 为什么 |  |
| 怎么做 |  |
| 关键数字 |  |
| 边界 |  |
| 失效 |  |

### S01 · （填标题）

| 角度 | 内容 |
|---|---|
| 是什么 |  |
| 为什么 |  |
| 怎么做 |  |
| 关键数字 |  |
| 边界 |  |
| 失效 |  |

## 附件

### 需求（R）

| ID | 内容 | 挂在链节 | 判据 | 证据 | 强度 |
|---|---|---|---|---|---|
| R1 |  |  |  |  |  |

### 功能（F）

| ID | 内容 | 落在链节 | 证据 |
|---|---|---|---|
| F1 |  |  |  |

### 交互（I）

| ID | 硬件实体 | 固件实体 | 落在链节 | 改了要连带什么 | 证据 |
|---|---|---|---|---|---|
| I1 |  |  |  |  |  |

### 判据（J）

| ID | 判据 | 守在链节 | 判错症状 | 失败语义 | 证据 |
|---|---|---|---|---|---|
| J1 |  |  |  |  |  |

### 风险（K）

| ID | 结论 | 挂在链节 | 强度 | 依据 |
|---|---|---|---|---|
| K1 |  |  |  |  |

## 2 · 冲突登记（一手 vs 文档）

<!-- 格式：
[冲突] <文档路径:行> 说「<原话>」
  一手：<文件:行 / 命令输出 / 网表节点>
  影响面：<会不会真的坏；能量化就写数>
  处置：<改文档 / 改实现 / 挂待确认>
-->

## 3 · 验证记录

| 跑了什么 | 命令 | 结果 | 跑不了的说明为什么 |
|---|---|---|---|
|  |  |  |  |

## 4 · 拷问清单（5~8 条，每条含推荐答案）

1.

## 5 · 附：命令与产物

```bash
```
"""


def slug(s: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "-", s.strip()).strip("-") or "chain"


def main() -> int:
    ap = argparse.ArgumentParser(description="生成一条链的骨架（MD + HTML）")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--out", required=True, help="输出目录，通常 <工程根>/docs/chain")
    ap.add_argument("--date", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    today = a.date or datetime.date.today().strftime("%Y%m%d")
    dash = "%s-%s-%s" % (today[:4], today[4:6], today[6:8])
    title = a.title or a.topic
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, "%s-%s" % (slug(a.topic), today))

    made = []
    md_path, html_path = base + ".md", base + ".html"
    if os.path.exists(md_path) and not a.force:
        print("跳过（已存在，加 --force 覆盖）：%s" % md_path)
    else:
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(MD_TMPL.format(title=title, date_dash=dash))
        made.append(md_path)
    if os.path.exists(html_path) and not a.force:
        print("跳过（已存在，加 --force 覆盖）：%s" % html_path)
    else:
        # 空链：一个占位节点，等填完 MD 后用 `chain.py --html` 重生成
        empty = {"name": "（空）",
                 "nodes": {"H01": dict(id="H01", what="（先填 MD 的链节表，再用 chain.py --html 重生成）",
                                       up="—", down="—", carrier="—", unit="—", src="—",
                                       stage="主干", actor="Analog", atts=[])}}
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(RD.render([empty], {k: [] for k in "RFIJK"}, [],
                               title=title, date=dash, fails=["链是空的 —— 还没填"]))
        made.append(html_path)
    for p in made:
        print("已写 %s" % p)
    print("\n下一步：定主干 → 填链节（含人话）→ 挂附件 → 软件链补齐三层（分层 + 调用边），然后\n"
          "  python chain.py %s            # 查断链\n"
          "  python chain.py %s --html %s   # 从 MD 重生成 HTML"
          % (md_path, md_path, html_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
