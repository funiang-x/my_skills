#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render.py —— 把若干条链画成图（单文件 HTML，内嵌 SVG）。

**两条原则**（都是踩过的）：
  1. **一条链一张图。** 软硬件揉在一张图上必然糊 —— 硬件按信号处理路径画（器件级），
     软件按软件架构画（模块/任务级），各画各的。
  2. **默认一条附件线都不画。** 几十条汇聚线画出来没人看得懂。附件改成
     ① 节点上一个小圆点；② 点节点看详情；③ 点下方附件面板里的标签 → 高亮它挂的节点。

布局规则（`references/chain-model.md` §六）：
  · **阶段 = 横带**，自上而下堆叠；**带内左→右折行**（每行最多 `COLS` 个）
  · **主干连线**按 ID 顺序（不是坐标顺序）：同行直箭头，折行/跨带肘形
  · **执行体 = 颜色**（节点左侧色条 + 描边）⇒ 并发一眼看出
  · **回环画在下方**，红色虚线弧 + 一句"为什么"

零依赖（只用标准库）。
"""
from __future__ import annotations

import html
import json
import re

BOX_W, BOX_H = 176, 86
GAP_X, GAP_Y = 30, 24
COLS = 4
PAD_X, PAD_Y = 20, 16
TITLE_H = 26
BAND_GAP = 30
LOOP_H = 46            # 每条回环占的高度

ACTOR_COLOR = {
    "Analog": ("#b4530a", "#fff6ec"),
    "Init": ("#5a6675", "#f2f4f8"),
    "ISR": ("#b58900", "#fdf8e7"),
    "Engine": ("#1a5fb4", "#eef4fd"),
    "Ui": ("#0f7b6c", "#eaf7f4"),
    "Driver": ("#7a3fa8", "#f7f1fd"),
}
ACTOR_DEFAULT = ("#5a6675", "#f2f4f8")
ATT_COLOR = {"R": "#1a5fb4", "F": "#0f7b6c", "I": "#b4530a", "J": "#7a3fa8", "K": "#b3261e"}
ATT_NAME = {"R": "需求", "F": "功能", "I": "交互", "J": "判据", "K": "风险"}
BAND_TINT = ["#fcfdff", "#f7f9fc"]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def wrap_text(s: str, width: int, max_lines: int = 2):
    out, cur, w = [], "", 0
    for ch in str(s or ""):
        cw = 2 if ord(ch) > 0x2000 else 1
        if w + cw > width and cur:
            out.append(cur)
            cur, w = ch, cw
            if len(out) >= max_lines:
                break
        else:
            cur += ch
            w += cw
    if cur and len(out) < max_lines:
        out.append(cur)
    if len(out) == max_lines and len("".join(out)) < len(str(s or "")):
        out[-1] = out[-1][:-1] + "…"
    return out


def _order(nodes):
    import re as _re

    def key(nid):
        m = _re.match(r"^([A-Za-z]+)(\d+)$", nid)
        return (m.group(1), int(m.group(2))) if m else (nid, 0)
    return sorted(nodes, key=key)


def layout_chain(chain, loops):
    nodes = chain["nodes"]
    order = _order(nodes)
    stages, seen = [], set()
    for nid in order:
        st = nodes[nid].get("stage") or "主干"
        if st not in seen:
            seen.add(st)
            stages.append([st, []])
        stages[-1][1].append(nid)

    band_w = COLS * BOX_W + (COLS - 1) * GAP_X + 2 * PAD_X
    pos, y, bands = {}, 10, []
    for name, ids in stages:
        nrow = (len(ids) + COLS - 1) // COLS
        h = TITLE_H + nrow * BOX_H + (nrow - 1) * GAP_Y + 2 * PAD_Y
        bands.append(dict(name=name, y=y, h=h, ids=ids))
        for i, nid in enumerate(ids):
            r, c = divmod(i, COLS)
            pos[nid] = (PAD_X + c * (BOX_W + GAP_X),
                        y + PAD_Y + TITLE_H + r * (BOX_H + GAP_Y))
        y += h + BAND_GAP
    bottom = y - BAND_GAP
    my_loops = [lp for lp in loops if lp["src"] in nodes]
    height = bottom + (len(my_loops) * LOOP_H + 34 if my_loops else 12)
    return order, bands, pos, band_w + 2 * PAD_X, height, my_loops


def svg_chain(chain, loops, idx):
    nodes = chain["nodes"]
    order, bands, pos, W, H, my_loops = layout_chain(chain, loops)
    o = []
    w = o.append
    w('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx" '
      'xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,BlinkMacSystemFont,'
      'Segoe UI,Microsoft YaHei,sans-serif" data-chain="%s">' % (W, H, W, esc(chain["name"])))
    w('<defs>'
      '<marker id="ah%d" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
      '<path d="M0,0 L7,3 L0,6 z" fill="#9aa6b5"/></marker>'
      '<marker id="ahK%d" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
      '<path d="M0,0 L7,3 L0,6 z" fill="#b3261e"/></marker></defs>' % (idx, idx))
    w('<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>' % (W, H))

    # ---- 阶段带 ----
    for bi, b in enumerate(bands):
        w('<rect x="4" y="%d" width="%d" height="%d" rx="14" fill="%s" stroke="#e9edf3"/>'
          % (b["y"], W - 8, b["h"], BAND_TINT[bi % 2]))
        w('<text x="22" y="%d" font-size="12.5" font-weight="700" fill="#93a0b0" '
          'letter-spacing="1.4">%s</text>' % (b["y"] + 19, esc(b["name"])))
        w('<text x="%d" y="%d" font-size="11" font-family="monospace" fill="#c3cbd6" '
          'text-anchor="end">%d / %d</text>' % (W - 20, b["y"] + 19, bi + 1, len(bands)))

    # ---- 主干连线（按 ID 顺序）----
    def ctr(nid, which):
        x, y = pos[nid]
        return dict(top=(x + BOX_W / 2, y), bottom=(x + BOX_W / 2, y + BOX_H),
                    left=(x, y + BOX_H / 2), right=(x + BOX_W, y + BOX_H / 2))[which]

    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        ax, ay = pos[a]
        bx, by = pos[b]
        if ay == by and bx > ax:
            p1, p2 = ctr(a, "right"), ctr(b, "left")
            w('<path d="M%.1f,%.1f L%.1f,%.1f" stroke="#a7b2c0" stroke-width="1.7" fill="none" '
              'marker-end="url(#ah%d)"/>' % (p1[0], p1[1], p2[0] - 3, p2[1], idx))
        else:
            sx, sy = ctr(a, "bottom")
            tx, ty = ctr(b, "top")
            my = (sy + ty) / 2 if ty > sy else sy + 30
            w('<path d="M%.1f,%.1f V%.1f H%.1f V%.1f" stroke="#a7b2c0" stroke-width="1.7" '
              'fill="none" stroke-linejoin="round" marker-end="url(#ah%d)"/>'
              % (sx, sy, my, tx, ty - 3, idx))

    # ---- 节点 ----
    for nid in order:
        n = nodes[nid]
        x, y = pos[nid]
        stroke, fill = ACTOR_COLOR.get(n.get("actor") or "", ACTOR_DEFAULT)
        w('<g class="nd" data-id="%s" data-chain="%s" style="cursor:pointer">'
          % (esc(nid), esc(chain["name"])))
        w('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="9" fill="%s" stroke="%s" '
          'stroke-width="1.4"/>' % (x, y, BOX_W, BOX_H, fill, stroke))
        w('<rect x="%.1f" y="%.1f" width="4.5" height="%d" rx="2" fill="%s"/>'
          % (x, y + 9, BOX_H - 18, stroke))
        w('<text x="%.1f" y="%.1f" font-size="11" font-family="monospace" fill="#98a4b3">%s</text>'
          % (x + 13, y + 17, esc(nid)))
        # ★ 正面优先显示**人话**（大白话），没有才退回"做什么"
        face = n.get("human") or n.get("what") or ""
        for k, line in enumerate(wrap_text(face, 22, 3)):
            w('<text x="%.1f" y="%.1f" font-size="12.5" font-weight="600" fill="#1b2430">%s</text>'
              % (x + 13, y + 33 + k * 15, esc(line)))
        meta = " · ".join([s for s in (n.get("carrier"), n.get("unit")) if s and s != "—"])
        w('<text x="%.1f" y="%.1f" font-size="10.5" font-family="monospace" fill="#8a95a6">%s</text>'
          % (x + 13, y + BOX_H - 9, esc(wrap_text(meta, 27, 1)[0] if meta else "")))
        # 附件小圆点（只表示"有"，不画线）
        bx = x + BOX_W - 12
        for a in reversed(n.get("atts") or []):
            w('<circle class="dot" cx="%.1f" cy="%.1f" r="4.6" fill="%s" opacity=".92"/>'
              % (bx, y + BOX_H - 13, ATT_COLOR.get(a[0], "#999")))
            bx -= 11
        w('</g>')

    # ---- 回环 ----
    if my_loops:
        ly = max([b["y"] + b["h"] for b in bands] + [0]) + 16
        w('<text x="22" y="%d" font-size="11.5" font-weight="700" fill="#93a0b0" '
          'letter-spacing="1">回环（不属于单向主干）</text>' % ly)
        for i, lp in enumerate(my_loops):
            y = ly + 22 + i * LOOP_H
            src, dst = lp["src"], lp["dst"]
            x1 = pos[src][0] + BOX_W / 2 if src in pos else 120
            x2 = pos[dst][0] + BOX_W / 2 if dst in pos else x1 + 200
            lo, hi = min(x1, x2), max(x1, x2)
            w('<path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" stroke="#c9433a" '
              'stroke-width="1.6" fill="none" stroke-dasharray="6 4" '
              'marker-end="url(#ahK%d)"/>'
              % (hi, y, hi + 34, y + 20, lo - 34, y + 20, lo, y - 5, idx))
            w('<text x="%.1f" y="%.1f" font-size="11" fill="#c9433a" text-anchor="middle">%s</text>'
              % ((lo + hi) / 2, y + 17, esc(lp.get("why", ""))))
    w('</svg>')
    return "".join(o), W, H



def layers_svg(layers, calls, nodes, idx=0):
    """分层结构图：每层一个横带（层名 + 职责 + **不许做什么** + 该层的节点），层间画调用边。

    为什么单独一张：**软件链的本质是"结构归属"，不是"执行顺序"**。
    """
    if not layers:
        return "", 0, 0
    W = 1040
    LBL_W, PAD, CHIP_W, CHIP_H, CGAP = 214, 14, 158, 56, 10
    COLS_L = max(1, (W - LBL_W - 2 * PAD) // (CHIP_W + CGAP))
    TOP, GAPY = 30, 74
    o = []
    w = o.append
    bands, y = [], TOP
    for L in layers:
        ids = [n for n in L["nodes"] if n in nodes]
        nrow = max(1, (len(ids) + COLS_L - 1) // COLS_L)
        h = max(76, 2 * PAD + nrow * CHIP_H + (nrow - 1) * CGAP + 30)
        bands.append(dict(L=L, ids=ids, y=y, h=h, nrow=nrow))
        y += h + GAPY
    H = y - GAPY + 20
    w('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx" '
      'xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,BlinkMacSystemFont,'
      'Segoe UI,Microsoft YaHei,sans-serif">' % (W, H, W))
    w('<defs><marker id="lha%d" markerWidth="9" markerHeight="9" refX="7" refY="3" '
      'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#1a5fb4"/></marker>'
      '<marker id="lhk%d" markerWidth="9" markerHeight="9" refX="7" refY="3" '
      'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#b4530a"/></marker></defs>'
      % (idx, idx))
    w('<rect width="%d" height="%d" fill="#fff"/>' % (W, H))
    for bi, b in enumerate(bands):
        L = b["L"]
        stroke, fill = lane_color(L["name"])
        w('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="%s" stroke="%s" '
          'stroke-width="1.3"/>' % (LBL_W, b["y"], W - LBL_W - 12, b["h"], fill, stroke))
        w('<text x="%d" y="%d" font-size="15" font-weight="700" fill="%s">%s</text>'
          % (12, b["y"] + 26, stroke, esc(L["name"])))
        for k, ln in enumerate(wrap_text(L["duty"], 15, 2)):
            w('<text x="12" y="%d" font-size="11" fill="#4a5666">%s</text>'
              % (b["y"] + 44 + k * 14, esc(ln)))
        if L["forbid"]:
            for k, ln in enumerate(wrap_text("✗ " + L["forbid"], 16, 3)):
                w('<text x="12" y="%d" font-size="10.5" fill="#b3261e">%s</text>'
                  % (b["y"] + 74 + k * 13, esc(ln)))
        for i, nid in enumerate(b["ids"]):
            r, c = divmod(i, COLS_L)
            x = LBL_W + PAD + c * (CHIP_W + CGAP)
            yy = b["y"] + PAD + 26 + r * (CHIP_H + CGAP)
            n = nodes[nid]
            # 可点击：点结构图上的节点 = 右栏显示它的讲解与附件（不切页签）
            w('<g class="ndC" data-id="%s" style="cursor:pointer">' % esc(nid))
            w('<rect x="%.1f" y="%d" width="%d" height="%d" rx="7" fill="#fff" '
              'stroke="%s"/>' % (x, yy, CHIP_W, CHIP_H, stroke))
            w('<text x="%.1f" y="%d" font-size="10.5" font-family="monospace" '
              'fill="#98a4b3">%s</text>' % (x + 8, yy + 15, esc(nid)))
            txt = n.get("human") or n.get("what") or ""
            # 两行放完整意图句（单行会截断）；空文本（骨架未填）wrap 出空列表，不能取 [0]
            for k, ln in enumerate(wrap_text(txt, 22, 2)):
                w('<text x="%.1f" y="%d" font-size="11.5" fill="#1b2430">%s</text>'
                  % (x + 8, yy + 30 + k * 14, esc(ln)))
            w('</g>')
    # 调用边：画在层带之间的间隙里；跨层用虚线
    lname = [b["L"]["name"] for b in bands]
    for i, c in enumerate(calls):
        si = next((k for k, b in enumerate(bands) if b["L"]["name"] in c["src"]), None)
        di = next((k for k, b in enumerate(bands) if b["L"]["name"] in c["dst"]), None)
        if si is None or di is None or si == di:
            continue
        skip = abs(si - di) > 1
        x = LBL_W + 60 + (i % 6) * 150
        y1 = bands[si]["y"] + (bands[si]["h"] if di > si else 0)
        y2 = bands[di]["y"] + (0 if di > si else bands[di]["h"])
        col = "#b4530a" if skip else "#1a5fb4"
        w('<path d="M%.1f,%.1f L%.1f,%.1f" stroke="%s" stroke-width="1.6" fill="none" '
          '%s marker-end="url(#lh%s%d)"/>'
          % (x, y1, x, y2 + (6 if di > si else -6), col,
             'stroke-dasharray="5 3" ' if skip else '', 'k' if skip else 'a', idx))
        ly = (y1 + y2) / 2
        w('<text x="%.1f" y="%.1f" font-size="10.5" fill="%s" text-anchor="middle" '
          'transform="rotate(0)">%s</text>'
          % (x + 6, ly, col, esc("".join(wrap_text(c["why"], 26, 2)) if c["why"] else "")))
    w('</svg>')
    return "".join(o), W, H


def lane_color(lane):
    """车道配色：允许 `Engine 工作段` 这类带后缀的车道名复用 Engine 的色。"""
    for k, v in ACTOR_COLOR.items():
        if lane.startswith(k):
            return v
    return ACTOR_DEFAULT


def gantt_svg(rows, title="运行时序"):
    """按执行体分车道画甘特图。**每条车道按自己的周期归一化**（不是同一时间轴）。"""
    if not rows:
        return ""
    LANE_W, ROW_H, GAP = 96, 34, 12
    W, TOP = 1040, 34
    lanes, order = {}, []
    for r in rows:
        if r["lane"] not in lanes:
            lanes[r["lane"]] = []
            order.append(r["lane"])
        lanes[r["lane"]].append(r)
    plot_w = W - LANE_W - 24
    H = TOP + len(order) * (ROW_H + GAP) + 18
    o = []
    w = o.append
    w('<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx" '
      'xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,BlinkMacSystemFont,'
      'Segoe UI,Microsoft YaHei,sans-serif">' % (W, H, W))
    w('<rect width="%d" height="%d" fill="#fff"/>' % (W, H))
    # 时间刻度（按百分比，不是绝对时间 —— 各车道周期不同）
    for f in (0, .25, .5, .75, 1):
        x = LANE_W + f * plot_w
        w('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#eef1f5"/>'
          % (x, TOP - 8, x, H - 10))
        w('<text x="%.1f" y="%d" font-size="10" fill="#b9c1cd" text-anchor="middle">'
          '一个周期的 %d%%</text>' % (x, 14, int(f * 100)))
    y = TOP
    for lane in order:
        rs = lanes[lane]
        stroke, fill = lane_color(lane)
        period = max([r["period"] for r in rs] + [1.0]) or 1.0
        w('<text x="%d" y="%d" font-size="12.5" font-weight="700" fill="%s">%s</text>'
          % (6, y + 15, stroke, esc(lane)))
        w('<text x="%d" y="%d" font-size="10.5" font-family="monospace" fill="#a8b2c0">'
          '周期 %g ms</text>' % (6, y + 29, period))
        acc = 0.0
        for r in rs:
            x0 = r["start"] if r["start"] and re.search(r"\d", r["start"]) else acc
            try:
                x0 = float(re.search(r"-?\d+(?:\.\d+)?", str(x0)).group(0))
            except Exception:
                x0 = acc
            acc = x0 + r["dur"]
            x = LANE_W + max(0.0, min(1.0, x0 / period)) * plot_w
            wd = max(2.0, min(1.0, r["dur"] / period) * plot_w)
            w('<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="4" fill="%s" '
              'stroke="%s"/>' % (x, y, wd, ROW_H, fill, stroke))
            lbl = r["seg"]
            if wd > 74:
                w('<text x="%.1f" y="%d" font-size="11" fill="%s" font-weight="600">%s</text>'
                  % (x + 7, y + 21, stroke, esc(lbl[:int(wd / 7.6)])))
            else:
                w('<text x="%.1f" y="%d" font-size="10.5" fill="%s">%s</text>'
                  % (x + wd + 5, y + 21, stroke, esc(lbl)))
            if r["note"] and wd > 190:
                w('<text x="%.1f" y="%d" font-size="10" fill="#8a95a6">%s</text>'
                  % (x + 7, y + 31, esc(r["note"][:int(wd / 6.2)])))
        y += ROW_H + GAP
    w('</svg>')
    return "".join(o)


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · 逻辑链（{date}）</title>
<style>
:root{{--bg:#f5f6f8;--panel:#fff;--line:#e6eaf0;--tx:#1b2430;--tx2:#4a5666;--tx3:#8a95a6;
 --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 --R:#1a5fb4;--F:#0f7b6c;--I:#b4530a;--J:#7a3fa8;--K:#b3261e}}
*{{box-sizing:border-box}}
html,body{{height:100%}}
body{{margin:0;background:var(--bg);color:var(--tx);overflow:hidden;
 font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
 display:flex;flex-direction:column}}
header{{flex:0 0 auto;padding:13px 24px 11px;background:#fff;border-bottom:1px solid var(--line)}}
h1{{margin:0;font-size:16.5px;letter-spacing:.2px}}
.sub{{font-size:11.5px;color:var(--tx3);margin-top:4px}}
.strip{{flex:0 0 auto;padding:11px 24px 0;display:flex;flex-direction:column;gap:9px}}
.verdict{{border-left:4px solid var(--F);background:#eaf7f4;padding:8px 13px;
 border-radius:0 9px 9px 0;font-size:12.5px}}
.verdict.bad{{border-color:var(--K);background:#fdecea}}
.verdict ul{{margin:5px 0 0 18px;padding:0}}
.tabs{{display:flex;gap:8px}}
.tab{{border:1px solid var(--line);border-bottom-color:#fff;background:#fff;
 border-radius:10px 10px 0 0;padding:7px 17px;cursor:pointer;font-size:13px;font-weight:600;
 color:var(--tx2)}}
.tab.on{{color:var(--tx);box-shadow:0 -2px 0 var(--R) inset}}
.tab .n{{font:11px var(--mono);color:var(--tx3);font-weight:400;margin-left:6px}}
/* ---- 整屏锁定：两栏各自内部滚动，页面本身不滚（点节点不用拉）---- */
.split{{flex:1 1 auto;min-height:0;display:grid;
 grid-template-columns:minmax(0,1fr) 430px;gap:16px;padding:0 24px 16px}}
.split.solo{{grid-template-columns:minmax(0,1fr)}}
.split.solo .side{{display:none}}
.main{{min-height:0;overflow:auto}}
.side{{min-height:0;display:flex;flex-direction:column;gap:10px}}
.pane{{display:none;background:#fff;border:1px solid var(--line);border-radius:0 12px 12px 12px;
 padding:8px 12px}}
.pane.on{{display:block}}
.legend{{flex:0 0 auto;font-size:11.5px;color:var(--tx2);display:flex;flex-wrap:wrap;gap:10px;
 align-items:center;background:#fff;border:1px solid var(--line);border-radius:12px;
 padding:9px 13px}}
.lg{{display:inline-flex;align-items:center;gap:5px}}
.sw{{width:11px;height:11px;border-radius:3px;display:inline-block}}
#panel{{flex:1 1 auto;min-height:0;overflow:auto;background:var(--panel);
 border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
#panel h3{{margin:0 0 5px;font-size:14px}}
#panel .meta{{font:11.5px var(--mono);color:var(--tx3);margin-bottom:9px;line-height:1.75}}
#panel .empty{{color:var(--tx3);font-size:12.5px}}
#panel .tags{{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 9px}}
.tg2{{font:11px/1.6 var(--mono);background:#f2f4f8;border:1px solid var(--line);
 border-radius:999px;padding:0 8px;color:var(--tx2)}}
#panel .human{{background:#fffbe9;border-left:3px solid #e8b06a;border-radius:0 8px 8px 0;
 padding:9px 12px;font-size:13.5px;line-height:1.7;color:#3a3324;margin:0 0 10px}}
#panel .nav{{display:flex;gap:8px;margin:0 0 8px;flex-wrap:wrap}}
.jump{{font:11.5px/1.7 var(--mono);border:1px solid var(--line);background:#fff;
 border-radius:8px;padding:2px 9px;cursor:pointer;color:var(--R)}}
.jump:hover{{background:var(--R);color:#fff;border-color:var(--R)}}
#panel .nav .dim{{font-size:11.5px;color:#c3cbd6}}
#attbox{{flex:0 0 auto;max-height:38%;overflow:auto;background:#fff;border:1px solid var(--line);
 border-radius:12px;padding:9px 13px}}
#attbox summary{{cursor:pointer;font-size:12.5px;font-weight:600;color:var(--tx2);outline:none}}
@media (max-width:1040px){{
 body{{overflow:auto;display:block}}
 .split{{display:block;padding:0 18px 60px}}
 .main{{overflow:visible}}
 .side{{display:block}}
 #panel{{overflow:visible;max-height:none;margin-bottom:12px}}
 #attbox{{max-height:none}}
}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#f2f4f8;font-size:12px;white-space:nowrap}}
code{{font-family:var(--mono);font-size:12px;background:#f2f4f8;padding:1px 4px;border-radius:3px}}
.pill{{display:inline-block;font:11.5px/1.7 var(--mono);padding:2px 9px;border-radius:999px;
 border:1px solid;margin:0 5px 6px 0;cursor:pointer;user-select:none}}
.pill:hover{{filter:brightness(.95)}}
.pill.sel{{color:#fff !important}}
.grp{{margin:10px 0 4px;font-size:12px;color:var(--tx3);font-weight:600}}
.nd.dim{{opacity:.14}}
.nd.hit rect{{stroke-width:3.2}}
.nd.hit rect:first-of-type{{filter:drop-shadow(0 0 6px rgba(0,0,0,.25))}}
/* 结构图节点条（ndC）：可点击、参与高亮/淡出 */
.ndC{{cursor:pointer}}
.ndC.dim{{opacity:.14}}
.ndC.hit rect{{stroke-width:3}}
/* 逐节讲解 */
.ch{{font-size:15px;border-bottom:2px solid var(--line);padding-bottom:7px;margin:22px 0 4px}}
.ch:first-child{{margin-top:4px}}
.talk{{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0;
 background:#fcfdff}}
.talk .th{{font-size:13.5px;margin-bottom:8px}}
.talk .tg{{display:block;font:11px var(--mono);color:var(--tx3);margin-top:3px}}
table.tt{{margin:0;table-layout:fixed}}
table.tt th{{width:84px;background:#f2f4f8;font-weight:600;color:var(--tx2);
 white-space:nowrap;vertical-align:top;font-size:12px;padding:7px 8px}}
table.tt td{{color:var(--tx);word-break:break-word;overflow-wrap:anywhere;padding:7px 9px}}
</style></head><body>
<header><h1>{title} · 逻辑链</h1>
<div class="sub">{date} · 由 <code>swhw-chain</code> 从同目录 .md 生成 ·
 图：点链节看上下游与附件 ｜ 讲解：每个链节从多个角度讲清楚</div></header>
<div class="strip">
{verdict}
<div class="tabs">{tabs}</div>
</div>
<div class="split" id="split">
  <div class="main">{panes}</div>
  <div class="side">
    <div id="panel"><div class="empty">点左边链节 → 这里显示它的<b>多角度讲解</b>与全部附件。<br>
      点下面的附件标签 → 左边高亮它落在哪些链节。</div></div>
    <div class="legend" id="legend"></div>
    <details id="attbox"><summary id="attsum">附件索引</summary>
      <div id="attbody"></div></details>
  </div>
</div>
<script>
const ATTS = {atts_json};
const NODES = {nodes_json};
const TALKS = {talks_json};
const COL = {colors};
const NAME = {names};
const byId = id => NODES.find(n => n.id === id);
function showChain(name){{
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.c===name));
  document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.dataset.c===name));
  const sp=document.getElementById('split');
  if(sp) sp.classList.toggle('solo', name==='__talk__');  /* 讲解页签独占整宽 */
}}
function sideTop(){{const s=document.querySelector('.side'); if(s) s.scrollTop=0;}}
function clearHL(){{
  document.querySelectorAll('.nd,.ndC').forEach(e=>e.classList.remove('dim','hit'));
  document.querySelectorAll('.pill').forEach(p=>{{p.classList.remove('sel');p.style.background='';}});
}}
function pick(id,keep){{   /* keep=true：不切页签（结构图节点条用） */
  clearHL();
  const n = byId(id); if(!n) return;
  if(!keep) showChain(n.chain);
  const up=[],dn=[]; let c=id,g=0;
  while(c&&g++<80){{const x=byId(c); if(!x||!x.up||x.up==='—')break; up.unshift(x.up); c=x.up;}}
  c=id; g=0;
  while(c&&g++<80){{const x=byId(c); if(!x||!x.down||x.down==='—')break; dn.push(x.down); c=x.down;}}
  const path=new Set([...up,id,...dn]);
  document.querySelectorAll('.nd[data-chain="'+n.chain+'"],.ndC[data-id]').forEach(e=>
    e.classList.toggle('dim', !path.has(e.dataset.id)));
  const sel=document.querySelector('.nd[data-id="'+id+'"][data-chain="'+n.chain+'"]');
  if(sel) sel.classList.add('hit');
  const selC=document.querySelector('.ndC[data-id="'+id+'"]');
  if(selC) selC.classList.add('hit');
  const rows=ATTS.filter(a=>a.mounts.includes(id));
  const tk=TALKS[id]||[];
  const nm=p=>{{const x=byId(p); return x?(' · '+(x.what||'')):'';}};
  const human=n.human||(tk.filter(x=>x[0]==='人话')[0]||[])[1]||'';
  const rest=tk.filter(x=>x[0]!=='人话');
  const up1=up.length?up[up.length-1]:'', dn1=dn.length?dn[0]:'';
  /* 顺序：标题 → 标签 → **人话（大字）** → 上一节/下一节（可点） → 技术元信息 → 其余角度 */
  let h='<h3>'+id+' · '+(n.what||'')+'</h3>'+
    '<div class="tags"><span class="tg2">'+n.chain+'</span><span class="tg2">'+n.stage+
    '</span><span class="tg2">'+(n.actor||'—')+'</span></div>';
  if(human){{h+='<div class="human">'+human+'</div>';}}
  h+='<div class="nav">'+
     (up1?('<span class="jump" data-go="'+up1+'">← '+up1+nm(up1)+'</span>')
         :'<span class="dim">已是首节</span>')+
     (dn1?('<span class="jump" data-go="'+dn1+'">'+dn1+nm(dn1)+' →</span>')
         :'<span class="dim">已是末节</span>')+
     '</div>'+
    '<div class="meta">载体 <code>'+(n.carrier||'')+'</code> · 单位 <code>'+(n.unit||'')+
    '</code> · 证据 <code>'+(n.src||'')+'</code></div>';
  if(rest.length){{
    h+='<table class="tt">'+rest.map(x=>'<tr><th>'+x[0]+'</th><td>'+x[1]+'</td></tr>').join('')+'</table>';
  }}else{{
    h+='<div class="empty">这一节还没写多角度讲解（用 <code>### '+id+' · 标题</code> + '+
       '<code>| 角度 | 内容 |</code> 补上）。</div>';
  }}
  if(rows.length){{
    h+='<div style="margin-top:12px"><b style="font-size:13px">挂在它上面的附件</b>'+
      '<table><tr><th>ID</th><th>类型</th><th>内容</th></tr>';
    rows.forEach(a=>{{h+='<tr><td><code>'+a.id+'</code></td><td>'+a.type+'</td><td>'+
      a.cells.join(' · ')+'</td></tr>';}});
    h+='</table></div>';
  }}
  const pn=document.getElementById('panel');
  pn.innerHTML=h;
  pn.querySelectorAll('.jump').forEach(a=>a.onclick=()=>pick(a.dataset.go));
  sideTop();
}}
function pickAtt(aid){{
  clearHL();
  const a=ATTS.find(x=>x.id===aid); if(!a) return;
  const t=document.querySelector('.pill[data-id="'+aid+'"]');
  t.classList.add('sel'); t.style.background=COL[a.type]; t.style.borderColor=COL[a.type];
  document.querySelectorAll('.nd,.ndC').forEach(e=>
    e.classList.toggle('dim', !a.mounts.includes(e.dataset.id)));
  a.mounts.forEach(m=>{{
    const n=byId(m); if(!n) return;
    const el=document.querySelector('.nd[data-id="'+m+'"][data-chain="'+n.chain+'"]');
    if(el) el.classList.add('hit');
    const el2=document.querySelector('.ndC[data-id="'+m+'"]');
    if(el2) el2.classList.add('hit');
  }});
  const chains=[...new Set(a.mounts.map(m=>{{const n=byId(m);return n?n.chain:''}}).filter(Boolean))];
  if(chains.length===1) showChain(chains[0]);
  document.getElementById('panel').innerHTML =
    '<h3><span class="pill sel" style="background:'+COL[a.type]+';border-color:'+COL[a.type]+'">'+
    a.id+'</span> '+NAME[a.type]+'</h3>'+
    '<div class="meta">挂在：'+a.mounts.join(' , ')+'<br>落在链：'+(chains.join(' , ')||'—')+'</div>'+
    '<table><tr><th>内容</th></tr><tr><td>'+a.cells.join(' · ')+'</td></tr></table>';
}}
/* 图例 + 附件索引（折叠，默认收起 —— 右栏以"讲解"为主） */
(function(){{
  const lg=document.getElementById('legend');
  const actors=[...new Set(NODES.map(n=>n.actor).filter(Boolean))];
  lg.innerHTML='<b style="font-size:11.5px">执行体</b>'+
    actors.map(a=>'<span class="lg"><span class="sw" style="background:'+(COL[a]||'#999')+
    '"></span>'+a+'</span>').join('');
  const body=document.getElementById('attbody');
  let h='';
  ['R','F','I','J','K'].forEach(p=>{{
    const xs=ATTS.filter(a=>a.type===p);
    if(!xs.length) return;
    h+='<div class="grp">'+NAME[p]+'（'+xs.length+'）</div>';
    h+=xs.map(a=>'<span class="pill" data-id="'+a.id+'" style="color:'+COL[p]+
      ';border-color:'+COL[p]+'">'+a.id+'</span>').join('');
  }});
  body.innerHTML=h;
  document.getElementById('attsum').textContent='附件索引（'+ATTS.length+' 条，点开按类型查）';
  body.querySelectorAll('.pill').forEach(p=>p.onclick=()=>pickAtt(p.dataset.id));
}})();
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>showChain(t.dataset.c));
document.querySelectorAll('.nd').forEach(e=>e.onclick=()=>pick(e.dataset.id));
document.querySelectorAll('.ndC').forEach(e=>e.onclick=()=>pick(e.dataset.id,true));
</script></body></html>
"""


def render(chains, atts, loops, talks=None, timeline=None, layers=None, calls=None,
           title="逻辑链", date="", fails=None):
    talks = talks or {}
    timeline = timeline or []
    layers = layers or []
    calls = calls or []
    tabs, panes, nodes_json = [], [], []
    for i, c in enumerate(chains):
        svg, W, H = svg_chain(c, loops, i)
        cls = " on" if i == 0 else ""
        tabs.append('<div class="tab%s" data-c="%s">%s<span class="n">%d 节</span></div>'
                    % (cls, esc(c["name"]), esc(c["name"]), len(c["nodes"])))
        panes.append('<div class="pane%s" data-c="%s">%s</div>'
                     % (cls, esc(c["name"]), svg))
        for nid in _order(c["nodes"]):
            n = c["nodes"][nid]
            nodes_json.append(dict(id=nid, chain=c["name"], what=n.get("what", ""),
                                   human=n.get("human", ""),
                                   carrier=n.get("carrier", ""), unit=n.get("unit", ""),
                                   src=n.get("src", ""), stage=n.get("stage", ""),
                                   actor=n.get("actor", ""),
                                   up=n.get("up", ""), down=n.get("down", "")))

    # ---- 逐节讲解页签 ----
    tl = []
    for c in chains:
        tl.append('<h2 class="ch">%s · 逐节讲解</h2>' % esc(c["name"]))
        for nid in _order(c["nodes"]):
            n = c["nodes"][nid]
            angles = talks.get(nid) or []
            stroke = ACTOR_COLOR.get(n.get("actor") or "", ACTOR_DEFAULT)[0]
            tl.append('<div class="talk" data-id="%s">'
                      '<div class="th"><b>%s</b> · %s'
                      '<span class="tg">%s · %s · %s</span></div>'
                      % (esc(nid), esc(nid), esc(n.get("what", "")),
                         esc(n.get("stage", "")), esc(n.get("actor") or "—"), stroke))
            if angles:
                tl.append('<table class="tt">')
                for k, v in angles:
                    tl.append('<tr><th>%s</th><td>%s</td></tr>' % (esc(k), esc(v)))
                tl.append('</table>')
            else:
                tl.append('<div class="empty">（这一节还没写讲解 —— 用 `### %s · 标题` + '
                          '`| 角度 | 内容 |` 补上）</div>' % esc(nid))
            tl.append('</div>')
    tabs.append('<div class="tab" data-c="__talk__">逐节讲解<span class="n">%d 节</span></div>'
                % len(nodes_json))
    panes.append('<div class="pane" data-c="__talk__">%s</div>' % "".join(tl))

    # ---- 软件结构页签（分层 + 调用边）----
    if layers:
        allnodes = {}
        for c in chains:
            allnodes.update(c["nodes"])
        ls, LW, LH = layers_svg(layers, calls, allnodes, 9)
        sp = len(chains)   # 结构页签排在本链页签之后、逐节讲解之前
        tabs.insert(sp, '<div class="tab" data-c="__struct__">软件结构<span class="n">%d 层</span></div>'
                    % len(layers))
        panes.insert(sp, '<div class="pane" data-c="__struct__">'
                     '<p style="font-size:12.5px;color:#4a5666;margin:4px 0 10px">'
                     '<b>软件的本质是"结构归属"，不是"执行顺序"</b> —— 这张图回答'
                     '「谁属于哪一层、谁调用谁、谁<b>不许</b>调谁」。'
                     '层间箭头 = 允许的调用方向；橙色虚线 = 跳过中间层（向下跳层是编排常态）；'
                     '<b>向上的箭头应当数得出来</b> —— 通常只有启动入口那一跳。'
                     '点任一节点看它的讲解与附件。</p>'
                     + ls + '</div>')

    # ---- 运行时序页签 ----
    if timeline:
        lanes = []
        for r in timeline:
            if r["lane"] not in lanes:
                lanes.append(r["lane"])
        tp = len(chains) + (1 if layers else 0)
        tabs.insert(tp, '<div class="tab" data-c="__time__">运行时序<span class="n">%d 车道</span></div>'
                    % len(lanes))
        g = gantt_svg(timeline)
        panes.insert(tp, '<div class="pane" data-c="__time__">'
                     '<p style="font-size:12.5px;color:#4a5666;margin:4px 0 10px">'
                     '每条车道按<b>自己的周期</b>归一化（Engine 一圈 500ms、Ui 一圈 10ms）—— '
                     '这不是一条时间轴，而是"各转各的两条循环"。'
                     '横轴是一个周期的百分比。</p>' + g + '</div>')

    flat = []
    for pfx in "RFIJK":
        for a in atts.get(pfx, []):
            hd, row = a["header"], a["row"]
            cells = []
            for k, cc in enumerate(row):
                if k == 0:
                    continue
                h = hd[k] if k < len(hd) else ""
                if any(x in h for x in ("挂在链节", "落在链节", "守在链节")):
                    continue
                cells.append(cc)
            flat.append(dict(id=a["id"], type=pfx, mounts=a["mounts"], cells=cells))
    fails = fails or []
    if fails:
        verdict = ('<div class="verdict bad"><b>链检查：%d 处问题</b><ul style="margin:6px 0 0 18px">'
                   % len(fails)) + "".join("<li>%s</li>" % esc(f) for f in fails[:8]) + "</ul></div>"
    else:
        verdict = ('<div class="verdict"><b>链检查：通过</b> —— 每条链都能从头走到尾，'
                   '每个需求 / 判据 / 风险都有落点。</div>')
    colors = dict(ATT_COLOR)
    colors.update({k: v[0] for k, v in ACTOR_COLOR.items()})
    return HTML.format(title=esc(title), date=esc(date), verdict=verdict,
                       tabs="".join(tabs), panes="".join(panes),
                       atts_json=json.dumps(flat, ensure_ascii=False),
                       nodes_json=json.dumps(nodes_json, ensure_ascii=False),
                       talks_json=json.dumps(talks, ensure_ascii=False),
                       colors=json.dumps(colors, ensure_ascii=False),
                       names=json.dumps(ATT_NAME, ensure_ascii=False))
