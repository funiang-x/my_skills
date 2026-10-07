#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""netlist.py —— 工作流 ②：取原理图网表（**必须带元件值**）。

为什么必须带值：只读"谁连谁"看不到 `10µF` 还是 `100nF`，而那两个值会改变整个结论。
本库的 `easyeda` 连接器里，**`sch read` 只给连接 + 料号，值在 `sch list` 的
`otherProperty.Value`** —— 所以本脚本取两路再合并。

用法（需 easyeda 连接器在线）：
    python netlist.py --project G2026 --pages INT,PWR,AFE --out netlist.md --raw _work/raw

降级（连接器不可用时）：
    python netlist.py --from-json _work/raw --out netlist.md
      ← 消费之前用 `easyeda sch read/list` 存下来的 read_<页>.json / list_<页>.json

零依赖（只用标准库；easyeda 是外部命令）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys


def run_cli(args, timeout=120):
    exe = shutil.which("easyeda")
    if exe is None:
        return None, "environment-missing: 找不到 easyeda 命令"
    try:
        p = subprocess.run([exe] + args, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout: easyeda %s 超时" % " ".join(args)
    if p.returncode != 0:
        return None, "exit=%d: %s" % (p.returncode, (p.stderr or "")[:200])
    try:
        return json.loads(p.stdout), None
    except json.JSONDecodeError as e:
        return None, "非 JSON 输出（连接器离线？）：%s" % e


def pages_of(proj):
    d, err = run_cli(["sch", "pages", "--project", proj])
    if err:
        return None, err
    res = d.get("result", d)
    out = []
    for p in res.get("pages", []):
        out.append((p.get("name", "?"), p.get("uuid")))
    return out, None


def fetch(proj, page_uuid, raw_dir):
    """取一页的 read + list，落盘后返回 (read, list)。"""
    rd, err = run_cli(["sch", "read", "--doc", page_uuid, "--project", proj])
    if err:
        return None, None, err
    ls, err = run_cli(["sch", "list", "--doc", page_uuid, "--project", proj])
    if err:
        return None, None, err
    if raw_dir:
        os.makedirs(raw_dir, exist_ok=True)
        for tag, d in (("read", rd), ("list", ls)):
            with open(os.path.join(raw_dir, "%s_%s.json" % (tag, page_uuid)),
                      "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=1)
    return rd, ls, None


def values_from_list(ls):
    """designator -> {value, mpn, mfr, lcsc, fp}。**注意 Value 可能与 MPN 矛盾** —— 原样抄，不判对错。"""
    meta = {}
    for c in (ls.get("result", ls).get("components") or []):
        des = c.get("designator")
        if not des:
            continue
        op = c.get("otherProperty") or {}
        meta.setdefault(des, {
            "value": (op.get("Value") or "").strip(),
            "mpn": (c.get("manufacturerId") or "").strip(),
            "mfr": (c.get("manufacturer") or "").strip(),
            "lcsc": (c.get("supplierId") or "").strip(),
            "fp": ((c.get("footprint") or {}).get("name") or "").strip(),
        })
    return meta


def render(page_name, rd, ls):
    r = rd.get("result", rd)
    meta = values_from_list(ls)
    o = io.StringIO()
    w = o.write
    w("### %s\n\n" % page_name)
    w("元件 %d · 网络 %d · 悬空脚 %d\n\n"
      % (r.get("componentCount", 0), r.get("netCount", 0), r.get("floatingPinCount", 0)))
    w("#### 元件（带值）\n\n| 位号 | 值 | 料号 | 封装 | 连接 |\n|---|---|---|---|---|\n")
    for c in r.get("components", []):
        d = c.get("designator")
        if not d or d == "?":
            continue
        m = meta.get(d, {})
        pins = ",".join("%s:%s" % (p.get("number"), p.get("net", "-"))
                        for p in c.get("pins", []))
        w("| `%s` | %s | `%s` | `%s` | %s |\n"
          % (d, m.get("value", ""), m.get("mpn", ""), m.get("fp", ""), pins))
    w("\n#### 网络表\n\n| 网名 | 节点 |\n|---|---|\n")
    for n in r.get("nets", []):
        plist = []
        for p in (n.get("pins") or []):
            plist.append("%s.%s" % (p.get("designator", "?"), p.get("pin", "?"))
                         if isinstance(p, dict) else str(p))
        w("| `%s` | %s |\n" % (n.get("net"), ", ".join(plist)))
    if r.get("floatingPins"):
        w("\n#### 悬空脚（**每条都要判：真 NC 还是漏画**）\n\n`%s`\n"
          % "`, `".join(str(x) for x in r["floatingPins"]))
    # 值/料号矛盾扫描 —— 这是最容易订错料的地方
    bad = []
    for d, m in meta.items():
        v, mpn = m["value"], m["mpn"]
        if not v or not mpn:
            continue
        # 常见编码：104=100nF / 103=10nF / 226=22µF / 106=10µF
        code = mpn[-3:] if mpn[-3:].isdigit() else ""
        want = {"104": "100n", "103": "10n", "226": "22u", "106": "10u"}.get(code)
        if want:
            vv = v.lower().replace("µ", "u").replace("μ", "u").replace("f", "")
            if want.rstrip("nuf") not in vv.replace(".", ""):
                bad.append((d, v, mpn, code))
    if bad:
        w("\n#### ⚠️ 值 / 料号可能矛盾（**不要自己判对错，进风险链**）\n\n"
          "| 位号 | Value | 料号 | 料号尾码含义 |\n|---|---|---|---|\n")
        for d, v, mpn, code in bad:
            w("| `%s` | %s | `%s` | %s |\n" % (d, v, mpn, code))
    return o.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description="取原理图网表（带元件值）")
    ap.add_argument("--project", default=None, help="EDA 工程名/uuid")
    ap.add_argument("--pages", default="", help="只取这些页（名字片段，逗号分隔）；空=全部")
    ap.add_argument("--out", default=None)
    ap.add_argument("--raw", default=None, help="原始 JSON 落盘目录（可复用）")
    ap.add_argument("--from-json", default=None, help="降级：消费已有的 raw 目录")
    a = ap.parse_args()

    blocks = []
    if a.from_json:
        d = a.from_json
        if not os.path.isdir(d):
            print("不是目录：%s" % d, file=sys.stderr)
            return 2
        uuids = sorted({f.split("read_", 1)[1][:-5]
                        for f in os.listdir(d) if f.startswith("read_") and f.endswith(".json")})
        if not uuids:
            print("在 %s 里没找到 read_*.json —— 先跑一次在线模式" % d, file=sys.stderr)
            return 2
        for u in uuids:
            rd = json.load(open(os.path.join(d, "read_%s.json" % u), encoding="utf-8"))
            lp = os.path.join(d, "list_%s.json" % u)
            ls = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else {"result": {"components": []}}
            blocks.append(render("页 %s" % u, rd, ls))
    else:
        if not a.project:
            print("要 --project（或用 --from-json 降级）", file=sys.stderr)
            return 2
        pages, err = pages_of(a.project)
        if err:
            print("取页面清单失败：%s" % err, file=sys.stderr)
            print("降级路径：① 确认 EasyEDA 客户端已打开该工程；② 或先手工跑\n"
                  "  easyeda sch read --doc <uuid> > raw/read_<页>.json\n"
                  "  easyeda sch list --doc <uuid> > raw/list_<页>.json\n"
                  "  再 python netlist.py --from-json raw --out netlist.md", file=sys.stderr)
            return 3
        want = [x.strip() for x in a.pages.split(",") if x.strip()]
        for name, uuid in pages:
            if want and not any(w.lower() in (name or "").lower() for w in want):
                continue
            rd, ls, err = fetch(a.project, uuid, a.raw)
            if err:
                print("取 %s 失败：%s" % (name, err), file=sys.stderr)
                return 3
            blocks.append(render(name, rd, ls))

    text = "# 原理图网表（带元件值）\n\n" + "\n".join(blocks)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("已写 %s（%d 页）" % (a.out, len(blocks)))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
