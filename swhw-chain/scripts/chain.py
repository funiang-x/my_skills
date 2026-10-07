#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chain.py —— 把交付物读成**若干条链**，并回答"谁扣着谁、断在哪"。

一份报告里可以有多条链（典型：**一条硬件链**（按信号处理路径）+ **一条软件链**（按软件架构））。
每条链一张链节表，ID 前缀各自区分（`H01…` / `S01…`），附件按 ID 挂到对应的链上。

解析：
  若干张**链节表**（`## 链节（<链名>）`：ID / 做什么 / 人话 / 上游 / 下游 / 载体 / 单位 / 阶段 / 执行体 / 证据）
+ 五张**附件表**（R 需求 / F 功能 / I 交互 / J 判据 / K 风险）
+ 一张**回环表**（从 / 到 / 为什么）—— 按起点归到所属链
+ **分层表** + **调用边表**（软件链①结构层，`chain-model.md` §九）
+ **时序表**（②时间层）+ 若干**讲解块**（③意图层的展开）

做四件事：
  ① 断链检查（7 条，每条命中都是真发现）+ **软件链三层覆盖警告**（缺①分层/调用边、缺③人话）
  ② 热点：挂载附件最多的链节
  ③ 走链：从任一节点出发，打印它往上游/下游的路径
  ④ 出图：`--html` 交给 `render.py`

用法：
    python chain.py <报告.md> [--walk H06] [--json x.json] [--html x.html]
    python chain.py --selftest

零依赖（只用标准库）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HEAD_RE = re.compile(r"^(#{2,4})\s+(.*)$", re.M)
AUX_RE = re.compile(r"（([A-Z])）|\(([A-Z])\)\)?")
NODE_RE = re.compile(r"^[A-Za-z]+\d+$")
ATTACH_COLS = ("挂在链节", "落在链节", "守在链节")
DASH = ("", "—", "-", "–")


def parse_tables(text: str):
    """[(heading, header, rows)] —— 表归属到上方最近的标题。"""
    heads = [(m.start(), m.group(2).strip()) for m in HEAD_RE.finditer(text)]
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                if any(cells):
                    rows.append(cells)
                j += 1
            upto = "\n".join(lines[:i])
            head = ""
            for hp, ht in heads:
                if hp <= len(upto):
                    head = ht
                else:
                    break
            out.append((head, header, rows))
            i = j
            continue
        i += 1
    return out


def clean(s: str) -> str:
    return s.replace("`", "").replace("*", "").strip()


def split_ids(s: str):
    return [x for x in re.split(r"[,，、\s]+", clean(s)) if x]


def col(header, *words):
    for k, h in enumerate(header):
        if any(w in h for w in words):
            return k
    return -1


def chain_name(heading: str) -> str:
    """`## 链节（硬件链）` → `硬件链`；`## 链节（主干）` → `主干`。"""
    m = re.search(r"（([^）]+)）", clean(heading))
    return m.group(1) if m else "主干"


def parse(md_path: str):
    text = open(md_path, encoding="utf-8").read()
    chains, atts = [], {k: [] for k in "RFIJK"}
    problems, loops, talks, timeline, layers, calls = [], [], {}, [], [], []

    for head, header, rows in parse_tables(text):
        h = clean(head)

        # ---- 讲解块：`### H13 · 标题` + `| 角度 | 内容 |` ----
        m0 = re.match(r"^([A-Za-z]+\d+)\b", h)
        if m0 and col(header, "角度") >= 0:
            ai, ci = col(header, "角度"), col(header, "内容")
            items = []
            for r in rows:
                if ai >= len(r):
                    continue
                k = clean(r[ai])
                v = clean(r[ci]) if 0 <= ci < len(r) else ""
                if k:
                    items.append((k, v))
            if items:
                talks.setdefault(m0.group(1), []).extend(items)
            continue

        # ---- 分层表：`## 分层` + `| 层 | 归属 | 不许做什么 | 节点 |` ----
        if "分层" in h and col(header, "层") >= 0:
            ci = {n: col(header, n) for n in ("层", "归属", "不许做什么", "节点")}
            for r in rows:
                k = ci["层"]
                if k < 0 or k >= len(r):
                    continue
                nm = clean(r[k])
                if not nm:
                    continue
                g = lambda key: (clean(r[ci[key]]) if 0 <= ci[key] < len(r) else "")
                layers.append(dict(name=nm, duty=g("归属"), forbid=g("不许做什么"),
                                   nodes=split_ids(g("节点"))))
            continue

        # ---- 调用边表：`## 调用边` + `| 从 | 到 | 为什么允许 |` ----
        if "调用边" in h and col(header, "从") >= 0:
            ci = {n: col(header, n) for n in ("从", "到", "为什么允许", "为什么")}
            for r in rows:
                k = ci["从"]
                if k < 0 or k >= len(r):
                    continue
                a = clean(r[k])
                if not a:
                    continue
                g = lambda key: (clean(r[ci[key]]) if 0 <= ci[key] < len(r) else "")
                calls.append(dict(src=a, dst=g("到"),
                                  why=g("为什么允许") or g("为什么")))
            continue

        # ---- 时序表：`## 时序` + `| 车道 | 周期 | 起点 | 段 | 时长 | 说明 |` ----
        if "时序" in h and col(header, "车道") >= 0:
            ci = {n: col(header, n) for n in ("车道", "周期", "起点", "段", "时长", "说明")}
            for r in rows:
                k = ci["车道"]
                if k < 0 or k >= len(r):
                    continue
                lane = clean(r[k])
                if not lane:
                    continue

                def num(key, default=0.0):
                    v = clean(r[ci[key]]) if 0 <= ci[key] < len(r) else ""
                    m = re.search(r"-?\d+(?:\.\d+)?", v)
                    return float(m.group(0)) if m else default
                g = lambda key: (clean(r[ci[key]]) if 0 <= ci[key] < len(r) else "")
                timeline.append(dict(lane=lane, period=num("周期"),
                                     start=g("起点"), seg=g("段"), dur=num("时长"),
                                     note=g("说明")))
            continue

        # ---- 回环表（全局；渲染时按起点归链）----
        if "回环" in h and "链节" not in h:
            ci = {n: col(header, n) for n in ("从", "到", "为什么")}
            for r in rows:
                k = ci["从"]
                if k < 0 or k >= len(r):
                    continue
                a = clean(r[k])
                if not NODE_RE.match(a):
                    continue
                g = lambda key: (clean(r[ci[key]]) if 0 <= ci[key] < len(r) else "")
                loops.append(dict(src=a, dst=g("到"), why=g("为什么")))
            continue

        # ---- 链节表（一条链）----
        if "链节" in h:
            keys = ("ID", "做什么", "人话", "上游", "下游", "载体", "单位",
                        "阶段", "执行体", "证据")
            ci = {n: col(header, n) for n in keys}
            nodes = {}
            for r in rows:
                k = ci["ID"]
                if k < 0 or k >= len(r):
                    continue
                nid = clean(r[k])
                if not NODE_RE.match(nid):
                    continue
                g = lambda key: (clean(r[ci[key]]) if 0 <= ci[key] < len(r) else "")
                nodes[nid] = dict(id=nid, what=g("做什么"), human=g("人话"),
                                  up=g("上游"), down=g("下游"),
                                  carrier=g("载体"), unit=g("单位"), src=g("证据"),
                                  stage=g("阶段") or "主干", actor=g("执行体"), atts=[])
            if nodes:
                chains.append(dict(name=chain_name(head), nodes=nodes))
            continue

        # ---- 附件表：标题形如 `需求（R）` ----
        m = AUX_RE.search(h)
        if not m:
            continue
        pfx = (m.group(1) or m.group(2))
        if pfx not in atts:
            continue
        ai = col(header, *ATTACH_COLS)
        if ai < 0:
            problems.append("附件表「%s」没有挂载列（%s）" % (h, " / ".join(ATTACH_COLS)))
            continue
        for r in rows:
            if not r:
                continue
            aid = clean(r[0])
            if not re.match(r"^%s\d+$" % pfx, aid):
                continue
            atts[pfx].append(dict(id=aid, mounts=split_ids(r[ai]) if ai < len(r) else [],
                                  row=[clean(c) for c in r],
                                  header=[clean(c) for c in header]))
    return chains, atts, problems, loops, talks, timeline, layers, calls


def _order(nodes):
    """按数字排序（H02 < H10），同号按字母。"""
    def key(nid):
        m = re.match(r"^([A-Za-z]+)(\d+)$", nid)
        return (m.group(1), int(m.group(2))) if m else (nid, 0)
    return sorted(nodes, key=key)


def check_chain(chain):
    """单条链的 3 条结构判据。返回 (fails, warns)。"""
    fails, warns = [], []
    nodes = chain["nodes"]
    order = _order(nodes)
    nm = chain["name"]
    if not order:
        return ["链「%s」是空的 —— 一个链节都没有" % nm], []
    # 1 从首节走到末节
    seen, cur, g = [], order[0], 0
    while cur and cur in nodes and g < len(nodes) + 2:
        seen.append(cur)
        cur = nodes[cur]["down"]
        g += 1
    if order[-1] not in seen:
        fails.append("[%s] 断链：从 %s 走不到末节 %s（走到 %s 就断了）"
                     % (nm, order[0], order[-1], seen[-1] if seen else "—"))
    # 2 孤儿
    for nid in order:
        n = nodes[nid]
        if nid not in (order[0], order[-1]) and n["up"] in DASH and n["down"] in DASH:
            fails.append("[%s] 孤儿链节：%s 既无上游也无下游，且不是首/末节" % (nm, nid))
    # 3 互指一致
    for nid in order:
        n = nodes[nid]
        d, u = n["down"], n["up"]
        if d in nodes and nodes[d]["up"] not in DASH and nodes[d]["up"] != nid:
            fails.append("[%s] 链写错了：%s 说下游是 %s，但 %s 说上游是 %s"
                         % (nm, nid, d, d, nodes[d]["up"]))
        if u in nodes and nodes[u]["down"] not in DASH and nodes[u]["down"] != nid:
            fails.append("[%s] 链写错了：%s 说上游是 %s，但 %s 说下游是 %s"
                         % (nm, nid, u, u, nodes[u]["down"]))
    return fails, warns


def check(chains, atts, problems, loops=None):
    fails, warns = list(problems), []
    all_nodes = {}
    for c in chains:
        f, w = check_chain(c)
        fails.extend(f)
        warns.extend(w)
        all_nodes.update(c["nodes"])
    if not chains:
        fails.append("一个链节表都没有")
        return fails, warns
    # 4~6 附件必须挂在存在的链节上
    for pfx, why in (("R", "没人保证这个需求"), ("J", "判据悬空：不知道它守什么"),
                     ("K", "风险没定位：不知道改哪里")):
        for a in atts[pfx]:
            if not [m for m in a["mounts"] if m in all_nodes]:
                fails.append("%s %s 没有挂到任何存在的链节（%s）" % (pfx, a["id"], why))
    for pfx in "RFIJK":
        for a in atts[pfx]:
            for m in a["mounts"]:
                if NODE_RE.match(m) and m not in all_nodes:
                    warns.append("%s %s 挂到了不存在的链节 %s" % (pfx, a["id"], m))
    # 7 回环两端
    for lp in (loops or []):
        if lp["src"] not in all_nodes:
            fails.append("回环起点 %s 不是链节" % lp["src"])
        if lp["dst"] and lp["dst"] not in all_nodes and not lp["dst"].startswith("—"):
            warns.append("回环终点 %s 不是链节（若指「下次上电」之类可忽略）" % lp["dst"])
    # 反向索引：链节 -> 附件
    for pfx in "RFIJK":
        for a in atts[pfx]:
            for m in a["mounts"]:
                if m in all_nodes:
                    all_nodes[m]["atts"].append(a["id"])
    return fails, warns


def walk(nodes, start):
    if start not in nodes:
        return None
    up, cur, g = [], start, 0
    while cur in nodes and nodes[cur]["up"] not in DASH and g < len(nodes) + 2:
        cur = nodes[cur]["up"]
        up.append(cur)
        g += 1
    dn, cur, g = [], start, 0
    while cur in nodes and nodes[cur]["down"] not in DASH and g < len(nodes) + 2:
        cur = nodes[cur]["down"]
        dn.append(cur)
        g += 1
    return list(reversed(up)), dn


def three_layer_warns(chains, layers, calls):
    """软件链三层覆盖（chain-model §九）：缺①结构（分层/调用边）、缺③人话 ⇒ 警告。

    为什么只是警告不是失败：老报告 / 纯硬件报告不该被拦。但软件链缺了①③，
    就等于"拿画硬件的方法画软件"—— 只剩②时间层，而读者要的恰恰是 ①+③。
    """
    warns = []
    sw = [c for c in chains if "软件" in c["name"]]
    if not sw:
        return warns
    if not layers:
        warns.append("[软件链] 缺①结构层：没有「## 分层」表（谁属于谁、谁不许调谁）"
                     "—— 只画了②时间层 = 拿画硬件的方法画软件")
    else:
        covered = set()
        for L in layers:
            covered.update(L["nodes"])
        for c in sw:
            ids = _order(c["nodes"])
            miss = [nid for nid in ids if nid not in covered]
            if ids and len(miss) == len(ids):
                warns.append("[软件链] 「分层」表没覆盖本链任何链节 —— ①结构层等于没有")
            elif miss:
                warns.append("[软件链] 这些链节没归层（分层表「节点」列没点它们）：%s"
                             % ", ".join(miss))
    if not calls:
        warns.append("[软件链] 缺①结构层：没有「## 调用边」表（谁调用谁、跨层例外在哪）")
    for c in sw:
        ids = _order(c["nodes"])
        miss = [nid for nid in ids if not c["nodes"][nid]["human"]]
        if ids and len(miss) * 2 > len(ids):
            warns.append("[软件链] %d/%d 节没有「人话」（③意图层缺，节点正面只能退回\"做什么\"）：%s"
                         % (len(miss), len(ids), ", ".join(miss[:8])))
    return warns


def report(md_path, walk_from=None, quiet=False):
    chains, atts, problems, loops, talks, timeline, layers, calls = parse(md_path)
    fails, warns = check(chains, atts, problems, loops)
    warns = warns + three_layer_warns(chains, layers, calls)
    o = io.StringIO()
    w = o.write
    w("# 链检查 · %s\n\n" % os.path.basename(md_path))
    for c in chains:
        order = _order(c["nodes"])
        stages = []
        for nid in order:
            if c["nodes"][nid]["stage"] not in stages:
                stages.append(c["nodes"][nid]["stage"])
        w("## %s：%d 节 / %d 阶段（%s）\n\n"
          % (c["name"], len(order), len(stages), " → ".join(stages)))
        hs = sorted((n for n in c["nodes"].values() if n["atts"]),
                    key=lambda n: (-len(n["atts"]), n["id"]))[:6]
        if hs:
            w("| 热点链节 | 阶段 | 做什么 | 附件数 | 附件 |\n|---|---|---|---|---|\n")
            for n in hs:
                w("| `%s` | %s | %s | %d | %s |\n"
                  % (n["id"], n["stage"], n["what"][:30], len(n["atts"]), ", ".join(n["atts"])))
            w("\n")
    w("附件 %s（合计 %d）· 回环 %d 条 · 分层 %d 层 · 调用边 %d 条\n\n"
      % (" / ".join("%s%d" % (k, len(atts[k])) for k in "RFIJK"),
         sum(len(atts[k]) for k in "RFIJK"), len(loops), len(layers), len(calls)))
    if fails:
        w("## ❌ 断链 / 缺挂载（%d）\n\n" % len(fails))
        for f in fails:
            w("- %s\n" % f)
        w("\n")
    else:
        w("## ✅ 全部链完整：能从头走到尾，每个需求/判据/风险都有落点\n\n")
    if warns:
        w("## ⚠️ 警告（%d）\n\n" % len(warns))
        for x in warns:
            w("- %s\n" % x)
        w("\n")
    if walk_from:
        for c in chains:
            r = walk(c["nodes"], walk_from)
            if r is None:
                continue
            up, dn = r
            n = c["nodes"][walk_from]
            w("## 走链：%s（在「%s」里）\n\n" % (walk_from, c["name"]))
            w("- 上游：%s\n" % (" ← ".join(up) if up else "（已是首节）"))
            w("- 本节：**%s** %s（阶段 %s · 执行体 %s · 载体 %s · 单位 %s）\n"
              % (walk_from, n["what"], n["stage"], n["actor"] or "—", n["carrier"], n["unit"]))
            w("- 下游：%s\n" % (" → ".join(dn) if dn else "（已是末节）"))
            if n["atts"]:
                w("- 本节附件：%s\n" % ", ".join(n["atts"]))
            break
        else:
            w("## 走链\n\n没有链节 `%s`\n" % walk_from)
    txt = o.getvalue()
    if not quiet:
        sys.stdout.write(txt)
    return dict(chains=chains, atts=atts, fails=fails, warns=warns, text=txt,
                loops=loops, talks=talks, timeline=timeline,
                layers=layers, calls=calls)


# ---------------------------------------------------------------- 自检
GOOD = """# X
## 链节（硬件链）

| ID | 做什么 | 人话 | 上游 | 下游 | 载体 | 单位 | 阶段 | 执行体 | 证据 |
|---|---|---|---|---|---|---|---|---|---|
| H01 | 端接 | 配成50Ω，不配就反射 | — | H02 | a | mV | 输入 | Analog | s |
| H02 | 滤波 | 压带外噪声防混叠 | H01 | H03 | b | mV | 滤波 | Analog | s |
| H03 | 放大 | 补回前级损失的净增益 | H02 | — | c | mV | 放大 | Analog | s |

## 链节（软件链）

| ID | 做什么 | 人话 | 上游 | 下游 | 载体 | 单位 | 阶段 | 执行体 | 证据 |
|---|---|---|---|---|---|---|---|---|---|
| S01 | 起机 | 时钟不对一切都不对 | — | S02 | d | — | 起机 | Init | s |
| S02 | 采集 | 成块搬运，边采边算会丢样 | S01 | — | e | 码值 | 采集 | Engine | s |

## 分层（软件链 ① 结构层）

| 层 | 归属（职责） | 不许做什么 | 节点 |
|---|---|---|---|
| 应用 | 编排与算法 | 不摸寄存器 | S01,S02 |
| 驱动 | 寄存器封装 | 不做业务决策 |  |

## 调用边（软件链 ① 结构层）

| 从 | 到 | 为什么允许 |
|---|---|---|
| 应用 | 驱动 | 经 bsp_* API |

## 附件

### 需求（R）

| ID | 内容 | 挂在链节 | 判据 | 证据 | 强度 |
|---|---|---|---|---|---|
| R1 | 某需求 | H01,S02 | ±5mV | s | 已核 |

### 判据（J）

| ID | 判据 | 守在链节 | 判错症状 | 失败语义 | 证据 |
|---|---|---|---|---|---|
| J1 | x>0 | S02 | 恒 0 | 停机 | s |

### 风险（K）

| ID | 结论 | 挂在链节 | 强度 | 依据 |
|---|---|---|---|---|
| K1 | 某风险 | H03 | 已核 | s |

## 回环

| 从 | 到 | 为什么 |
|---|---|---|
| S02 | S01 | 重测通知 |
"""


def selftest() -> int:
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "good.md")

        def run(txt, **kw):
            open(p, "w", encoding="utf-8").write(txt)
            return report(p, quiet=True, **kw)

        r = run(GOOD)
        if r["fails"]:
            print("FAIL 好报告被判失败：%s" % r["fails"]); ok = False
        if r["warns"]:
            print("FAIL 好报告有三层警告：%s" % r["warns"]); ok = False
        if len(r["layers"]) != 2 or len(r["calls"]) != 1:
            print("FAIL 分层/调用边没被解析：%d 层 %d 边" % (len(r["layers"]), len(r["calls"]))); ok = False
        if not r["chains"][1]["nodes"]["S01"]["human"]:
            print("FAIL 人话没被解析"); ok = False
        import render as RD
        _html = RD.render(r["chains"], r["atts"], r["loops"], talks=r["talks"],
                          layers=r["layers"], calls=r["calls"])
        if "__struct__" not in _html:
            print("FAIL 软件结构页签没出"); ok = False
        if "时钟不对一切都不对" not in _html:
            print("FAIL 人话没画到节点正面"); ok = False
        # 回归：骨架未填（做什么/人话全空）+ 分层指向它，渲染不炸
        # （layers_svg 曾对空文本取 wrap_text(...)[0] ⇒ IndexError）
        try:
            _empty = dict(name="软件链", nodes={"S01": dict(
                id="S01", what="", human="", up="—", down="—", carrier="", unit="",
                src="", stage="", actor="", atts=[])})
            RD.render([_empty], {k: [] for k in "RFIJK"}, [],
                      layers=[dict(name="应用", duty="", forbid="", nodes=["S01"])],
                      calls=[dict(src="应用", dst="驱动", why="")])
        except Exception as e:
            print("FAIL 空文本节点渲染炸了：%s" % e); ok = False
        # 缺①（分层 + 调用边整段删掉）
        r = run(re.sub(r"## 分层（软件链 ① 结构层）.*?(?=## 回环)", "", GOOD, flags=re.S))
        if not any("①结构层" in x for x in r["warns"]):
            print("FAIL 缺①结构层没告警：%s" % r["warns"]); ok = False
        # 缺③（软件链人话全空）
        r = run(GOOD.replace(" | 时钟不对一切都不对 |", " |  |")
                   .replace(" | 成块搬运，边采边算会丢样 |", " |  |"))
        if not any("人话" in x for x in r["warns"]):
            print("FAIL 缺③人话没告警：%s" % r["warns"]); ok = False
        if len(r["chains"]) != 2 or r["chains"][0]["name"] != "硬件链":
            print("FAIL 两条链没被解析：%s" % [c["name"] for c in r["chains"]]); ok = False
        if len(r["loops"]) != 1:
            print("FAIL 回环没被解析"); ok = False
        if r["chains"][0]["nodes"]["H01"]["stage"] != "输入":
            print("FAIL 阶段没被解析"); ok = False
        # 跨链挂载必须能通过（R1 同时挂 H01 与 S02）
        if any("R R1" in f for f in r["fails"]):
            print("FAIL 跨链挂载被误判"); ok = False
        # 互指不一致
        r = run(GOOD.replace("| H03 | 放大 | 补回前级损失的净增益 | H02 |",
                             "| H03 | 放大 | 补回前级损失的净增益 | H09 |"))
        if not any("链写错了" in f for f in r["fails"]):
            print("FAIL 互指不一致没抓到"); ok = False
        # 走不到末节
        r = run(GOOD.replace("| H01 | 端接 | 配成50Ω，不配就反射 | — | H02 |",
                             "| H01 | 端接 | 配成50Ω，不配就反射 | — | H09 |"))
        if not any("断链" in f for f in r["fails"]):
            print("FAIL 走不到末节没抓到"); ok = False
        # 需求没挂载
        r = run(GOOD.replace("| R1 | 某需求 | H01,S02 |", "| R1 | 某需求 |  |"))
        if not any("R R1 没有挂到" in f for f in r["fails"]):
            print("FAIL 需求没挂载没抓到"); ok = False
        # 孤儿链节（把中间那节的两端都掐断 —— 首/末节不算孤儿）
        r = run(GOOD.replace("| H02 | 滤波 | 压带外噪声防混叠 | H01 | H03 |",
                             "| H02 | 滤波 | 压带外噪声防混叠 | — | — |"))
        if not any("孤儿链节" in f for f in r["fails"]):
            print("FAIL 孤儿链节没抓到：%s" % r["fails"]); ok = False
        # 回环起点不存在
        r = run(GOOD.replace("| S02 | S01 | 重测通知 |", "| S99 | S01 | 重测通知 |"))
        if not any("回环起点" in f for f in r["fails"]):
            print("FAIL 回环起点没抓到"); ok = False
        # 走链
        r = run(GOOD, walk_from="S02")
        if "S01" not in r["text"]:
            print("FAIL 走链没输出上游"); ok = False
        print("selftest: %s" % ("OK" if ok else "FAILED"))
        return 0 if ok else 1



def check_html_js(html_text: str, quiet=False):
    """出图后验一次内嵌 JS 的语法。

    为什么值得固化：**JS 语法错会让整个交互静默失效**（页面照常显示、点谁都没反应），
    而 HTML 本身"看着是对的" —— 肉眼看不出。有 node 就验，没有就跳过（不报错）。
    """
    import shutil, subprocess, tempfile
    node = shutil.which("node")
    if node is None:
        if not quiet:
            print("[js] 跳过语法检查（没找到 node）")
        return None
    blocks = re.findall(r"<script>(.*?)</script>", html_text, re.S)
    if not blocks:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("\n".join(blocks))
        tmp = fh.name
    try:
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True,
                           timeout=60)
        if r.returncode != 0:
            print("[js] ❌ 内嵌 JS 语法错 —— 页面会显示正常但点谁都没反应：\n%s"
                  % (r.stderr or "")[:600], file=sys.stderr)
            return False
        if not quiet:
            print("[js] 内嵌 JS 语法 OK（%d 块）" % len(blocks))
        return True
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="把交付物读成若干条链并检查")
    ap.add_argument("report", nargs="?")
    ap.add_argument("--walk", default=None, help="从某个链节走链（如 H06 / S12）")
    ap.add_argument("--json", default=None)
    ap.add_argument("--html", default=None, help="渲染成单文件 HTML（数据从 .md 生成，同源）")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.report or not os.path.isfile(a.report):
        print("用法：chain.py <报告.md> [--walk H06] [--json x.json] [--html x.html]；或 --selftest",
              file=sys.stderr)
        return 2
    r = report(a.report, a.walk, quiet=a.quiet)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(dict(chains=r["chains"], atts=r["atts"], loops=r["loops"],
                           talks=r["talks"], timeline=r["timeline"],
                           layers=r["layers"], calls=r["calls"],
                           fails=r["fails"], warns=r["warns"]), fh,
                      ensure_ascii=False, indent=1)
        print("已写 %s" % a.json)
    if a.html:
        import render as RD
        base = os.path.basename(a.report)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", base)
        out = RD.render(r["chains"], r["atts"], r["loops"], talks=r["talks"],
                        timeline=r["timeline"], layers=r["layers"], calls=r["calls"],
                        title=os.path.splitext(base)[0],
                        date=m.group(1) if m else "", fails=r["fails"])
        with open(a.html, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("已写 %s" % a.html)
        check_html_js(out, quiet=a.quiet)
    return 0 if not r["fails"] else 1


if __name__ == "__main__":
    sys.exit(main())
