try:                                   # Windows 控制台默认 GBK，中文输出会变问号
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                      # noqa: BLE001
    pass
# -*- coding: utf-8 -*-
"""通用「删件 + 清扇出」：删除指定位号的器件，连同其引脚上的短线与线外端旗标。

安全规则：只有当短线的**外端**没有别的器件引脚、也没有别的（未删）导线端点时，
才删除位于该点的旗标。
"""
import sys
import json, sys
from bridge import run, pages          # 本 skill scripts/ 内

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

SNAP = r'''
await eda.dmt_EditorControl.openDocument("__PG__");
await new Promise(r => setTimeout(r, 700));
const g = (o, fn) => { try { return fn(); } catch (e) { return null; } };
const out = { comps: [], wires: [], flags: [] };
const ids = await eda.sch_PrimitiveComponent.getAllPrimitiveId();
const cs = await eda.sch_PrimitiveComponent.get(ids);
for (const c of (Array.isArray(cs) ? cs : [cs])) {
  const des = g(c, () => c.getState_Designator());
  const rec = { id: c.getState_PrimitiveId(), des: des,
                x: g(c, () => c.getState_X()), y: g(c, () => c.getState_Y()),
                nm: g(c, () => c.getState_Name()), pins: [] };
  try {
    const ps = await c.getAllPins();
    for (const p of ps) rec.pins.push({ n: p.getState_PinNumber(),
      x: p.getState_X(), y: p.getState_Y(),
      rot: p.getState_Rotation(), len: p.getState_PinLength ? p.getState_PinLength() : null });
  } catch (e) {}
  if (des) out.comps.push(rec); else out.flags.push(rec);
}
const wids = await eda.sch_PrimitiveWire.getAllPrimitiveId();
for (const id of (wids || [])) {
  const w = await eda.sch_PrimitiveWire.get(id);
  const o = Array.isArray(w) ? w[0] : w;
  out.wires.push({ id: id, line: g(o, () => o.getState_Line()), net: g(o, () => o.getState_Net()) });
}
return JSON.stringify(out);
'''

KILL = r'''
await eda.dmt_EditorControl.openDocument("__PG__");
await new Promise(r => setTimeout(r, 500));
const res = {};
res.comps = await eda.sch_PrimitiveComponent.delete(__C__);
if (__W__.length) res.wires = await eda.sch_PrimitiveWire.delete(__W__);
if (__F__.length) res.flags = await eda.sch_PrimitiveComponent.delete(__F__);
return JSON.stringify(res);
'''


def pt(l, i):
    return (l[i], l[i + 1])


def delete(pg, des_list):
    snap = json.loads(run(SNAP.replace("__PG__", pg), timeout=300))
    tgt = [c for c in snap["comps"] if c["des"] in des_list]
    got = sorted(c["des"] for c in tgt)
    if got != sorted(des_list):
        print("  !! 位号不匹配：找到 %s，期望 %s" % (got, sorted(des_list)))
    pin_pts = set()
    for c in tgt:
        for p in c["pins"]:
            pin_pts.add((p["x"], p["y"]))

    keep_wire_pts = set()
    del_wires, far_pts = [], set()
    for w in snap["wires"]:
        L = w["line"] or []
        if len(L) < 4:
            continue
        p0, p1 = pt(L, 0), pt(L, len(L) - 2)
        if p0 in pin_pts or p1 in pin_pts:
            if len(L) == 4:                      # 只处理单段短线
                del_wires.append(w["id"])
                far_pts.add(p1 if p0 in pin_pts else p0)
            else:
                print("  ?? 多段线触到目标引脚，未删：", w["id"], L)
    for w in snap["wires"]:
        if w["id"] in del_wires:
            continue
        L = w["line"] or []
        if len(L) >= 4:
            keep_wire_pts.add(pt(L, 0))
            keep_wire_pts.add(pt(L, len(L) - 2))
    other_pin_pts = set()
    for c in snap["comps"]:
        if c["des"] in des_list:
            continue
        for p in c["pins"]:
            other_pin_pts.add((p["x"], p["y"]))

    del_flags = []
    for f in snap["flags"]:
        pos = (f["x"], f["y"])
        if pos in far_pts and pos not in keep_wire_pts and pos not in other_pin_pts:
            del_flags.append(f["id"])

    print("  删器件 %d（%s）/ 短线 %d / 旗标 %d" % (len(tgt), ",".join(got), len(del_wires), len(del_flags)))
    js = (KILL.replace("__PG__", pg)
              .replace("__C__", json.dumps([c["id"] for c in tgt]))
              .replace("__W__", json.dumps(del_wires))
              .replace("__F__", json.dumps(del_flags)))
    return json.loads(run(js, timeout=300))


if __name__ == "__main__":
    _gate_require(('硬件/审计', '硬件/落图'))   # 本脚本一定会改图
    jobs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    for pg, des in jobs:
        print("--- page %s : %s" % (pg, ",".join(des)))
        print("   ", delete(pg, des))
