try:                                   # Windows 控制台默认 GBK，中文输出会变问号
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                      # noqa: BLE001
    pass
# -*- coding: utf-8 -*-
"""扫除"旗标残骸"（正确版）。

正确判据：**从器件引脚出发做「导线级 BFS」**——
  seed = 有端点落在引脚上的导线；反复扩张 = 与已入选导线共点的导线；
  未被选中的导线 = 不接任何引脚的死线（只连旗标）；随之孤立的旗标 = 残骸。

（前两版都错在"把导线自己的端点也当锚点"，等于每条线都碰到自己 → 永远 0 死线。）
"""
import sys
import json
from bridge import run, pages          # 本 skill 的 scripts/ 目录内

# ── 开工闸门（与平台无关那层；实现见本库 tools/gate.py）─────────────
# 为什么在脚本里也做一道：平台钩子只覆盖支持钩子的客户端。而"改原理图"只能走本脚本，
# 闸门做进脚本 = 闸门做进操作本身，于是**任何客户端都绕不过**（含无钩子的）。
# 防御式：找不到本库就放行 —— skill 被单独拷走时不能因此跑不动。
def _gate_require(ops):
    import os
    cands = [os.environ.get("SKILLS_TOOLS"), os.environ.get("WORKBENCH_TOOLS")]
    # ① 从 cwd 向上找（兼容"工作台 / 项目内"布局）
    d = os.path.abspath(os.getcwd())
    while True:
        cands.append(os.path.join(d, "workbench", "tools"))
        nd = os.path.dirname(d)
        if os.path.isfile(os.path.join(d, "workbench", "tools", "gate.py")) or nd == d:
            break
        d = nd
    # ② 从脚本自身位置向上找本库 tools/（skill 在库里 = 永远可达）
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        cands.append(os.path.join(d, "tools"))
        nd = os.path.dirname(d)
        if os.path.isfile(os.path.join(d, "tools", "gate.py")) or nd == d:
            break
        d = nd
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "gate.py")):
            sys.path.insert(0, c)
            try:
                from gate import require
            except ImportError:
                return
            require(list(ops))
            return

PAGES = pages()          # 自动取全工程页（原来的 3 个 uuid 只属于 G2026 工程，已去掉）

SNAP = r'''
await eda.dmt_EditorControl.openDocument("__PG__");
await new Promise(r => setTimeout(r, 700));
const g = (o, fn) => { try { return fn(); } catch (e) { return null; } };
const out = { comps: [], wires: [], flags: [] };
const ids = await eda.sch_PrimitiveComponent.getAllPrimitiveId();
const cs = await eda.sch_PrimitiveComponent.get(ids);
for (const c of (Array.isArray(cs) ? cs : [cs])) {
  const des = g(c, () => c.getState_Designator());
  const rec = { id: c.getState_PrimitiveId(), des: des, nm: g(c, () => c.getState_Name()),
                x: g(c, () => c.getState_X()), y: g(c, () => c.getState_Y()), pins: [] };
  try { const ps = await c.getAllPins();
        for (const p of ps) rec.pins.push([p.getState_X(), p.getState_Y()]); } catch (e) {}
  if (des) out.comps.push(rec); else out.flags.push(rec);
}
const wids = await eda.sch_PrimitiveWire.getAllPrimitiveId();
for (const id of (wids || [])) {
  const w = await eda.sch_PrimitiveWire.get(id);
  const o = Array.isArray(w) ? w[0] : w;
  out.wires.push({ id: id, line: g(o, () => o.getState_Line()) });
}
return JSON.stringify(out);
'''

KILL = r'''
await eda.dmt_EditorControl.openDocument("__PG__");
await new Promise(r => setTimeout(r, 500));
const r = {};
if (__W__.length) r.wires = await eda.sch_PrimitiveWire.delete(__W__);
if (__F__.length) r.flags = await eda.sch_PrimitiveComponent.delete(__F__);
return JSON.stringify(r);
'''


def R(v):
    return int(round(float(v)))


def pts(line):
    L = line or []
    return [(R(L[i]), R(L[i + 1])) for i in range(0, len(L) - 1, 2)]


def scan(tag, pg, apply=True):
    s = json.loads(run(SNAP.replace("__PG__", pg), timeout=300))
    pin_pts = set()
    for c in s["comps"]:
        for p in c["pins"]:
            pin_pts.add((R(p[0]), R(p[1])))
    W = {w["id"]: pts(w["line"]) for w in s["wires"]}

    alive, frontier = set(), set()
    for wid, P in W.items():
        if any(q in pin_pts for q in P):
            alive.add(wid); frontier.add(wid)
    while frontier:
        nxt = set()
        live_pts = set()
        for wid in alive:
            live_pts |= set(W[wid])
        for wid, P in W.items():
            if wid in alive:
                continue
            if any(q in live_pts for q in P):
                nxt.add(wid)
        alive |= nxt
        frontier = nxt

    dead = [wid for wid in W if wid not in alive]
    live_pts = set(pin_pts)
    for wid in alive:
        live_pts |= set(W[wid])
    orphan = [f for f in s["flags"] if (R(f["x"]), R(f["y"])) not in live_pts]

    print("=== %s 器件 %d / 导线 %d(死 %d) / 旗标 %d(残骸 %d) ===" %
          (tag, len(s["comps"]), len(W), len(dead), len(s["flags"]), len(orphan)))
    for wid in dead:
        print("   死线", W[wid])
    for f in orphan:
        print("   残旗 %-10s @(%s,%s)" % (f["nm"], f["x"], f["y"]))
    if apply and (dead or orphan):
        print("   ->", run(KILL.replace("__PG__", pg).replace("__W__", json.dumps(dead))
                            .replace("__F__", json.dumps([f["id"] for f in orphan])), timeout=300))
    return len(dead), len(orphan)


if __name__ == "__main__":
    _gate_require(('硬件/审计', '硬件/落图'))   # 本脚本一定会改图
    tot = 0
    for tag, pg in PAGES.items():
        tot += sum(scan(tag, pg))
    print("\n合计清除 %d 项" % tot)
