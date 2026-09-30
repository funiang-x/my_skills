#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_sch.py -- EasyEDA Pro 原理图「几何法对账器」（只读，不改图）

为什么要有它：DRC 是「连没连上」的唯一权威，但有一类问题 DRC 报不出来 ——
    串联元件（0R / 串阻 / 磁珠）两端挂了同名旗标 -> EDA 按网名并网 -> 元件被自己两端的标签短路。
    电气上不算"错"，几何上两脚分属两个独立连通域，常规同网检测/短路扫描都抓不到。
    实测案例：判据 1b 抓到 R12(1k 串阻) 形同虚设。

判据（逐页 + 跨页）：
  1   两端几何同网        -- 2 脚元件两脚落在同一连通域（被导线短接）
  1b  两侧挂同名旗标      -- 2 脚元件两脚分属两域，但两域旗标名有交集 => 被并网短路  <- 本工具独有
  2   一域多旗标名        -- 同一连通域出现 >=2 个不同旗标名（隐性短路）
  3   匿名网              -- 含引脚却无任何旗标（信息级，内部节点正常长这样）
  4   孤儿旗标            -- 旗标未被任何导线端点咬住（DRC: 网络端口 X 没有连接导线）
  5   跨页命名网总表      -- net -> 各页成员，用来逐条比对设计表

用法：
    python audit_sch.py                     # 自动取当前工程所有原理图页
    python audit_sch.py --page INT --page PWR
    python audit_sch.py --port 49620
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict

try:                                   # Windows 控制台默认 GBK，会让中文输出变问号
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                      # noqa: BLE001
    pass

# 注意：getCurrentSchematicAllSchematicPagesInfo() 在"当前没打开原理图文档"时返回空数组，
# 所以用 getAllSchematicsInfo()：它返回 Schematic 列表，页在各自的 .page[] 里（2026-09-30 实测）。
PAGES_JS = ('const s = await eda.dmt_Schematic.getAllSchematicsInfo();'
            'return JSON.stringify(s);')


def find_port(explicit=None):
    for p in ([explicit] if explicit else range(49620, 49630)):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/health' % p, timeout=2) as r:
                if json.loads(r.read().decode('utf-8')).get('service') == 'easyeda-bridge':
                    return p
        except Exception:
            continue
    return None


def make_exe(port):
    url = 'http://127.0.0.1:%d/execute' % port

    def exe(code, timeout=300):
        req = urllib.request.Request(url, data=json.dumps({'code': code}).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return {'error': 'HTTP %d' % e.code}
        except Exception as e:                                             # noqa: BLE001
            return {'error': str(e)[:200]}
    return exe


SNAP = '\n'.join([
    'await eda.dmt_EditorControl.openDocument("__PG__");',
    'await new Promise(r => setTimeout(r, 1500));',
    'const g = (o, fn) => { try { return fn(); } catch (e) { return null; } };',
    'const R = (v) => Math.round(v);',
    'const out = { comps: [], flags: [], wires: [] };',
    'const ids = await eda.sch_PrimitiveComponent.getAllPrimitiveId();',
    'const cs = await eda.sch_PrimitiveComponent.get(ids);',
    'for (const c of (Array.isArray(cs) ? cs : [cs])) {',
    '  const des = g(c, () => c.getState_Designator());',
    '  const rec = { id: c.getState_PrimitiveId(), des: des, nm: g(c, () => c.getState_Name()),',
    '                x: R(c.getState_X()), y: R(c.getState_Y()), pins: [] };',
    '  try { for (const p of await c.getAllPins())',
    '          rec.pins.push([String(p.getState_PinNumber()), R(p.getState_X()), R(p.getState_Y())]); }',
    '  catch (e) {}',
    '  (des ? out.comps : out.flags).push(rec);',
    '}',
    'const wids = await eda.sch_PrimitiveWire.getAllPrimitiveId();',
    'for (const id of (wids || [])) {',
    '  const w = await eda.sch_PrimitiveWire.get(id);',
    '  const o = Array.isArray(w) ? w[0] : w;',
    '  const L = g(o, () => o.getState_Line()) || [];',
    '  const P = [];',
    '  for (let i = 0; i + 1 < L.length; i += 2) P.push([R(L[i]), R(L[i + 1])]);',
    '  if (P.length) out.wires.push({ id: id, P: P });',
    '}',
    'return JSON.stringify(out);',
])


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', action='append', default=None, help='页名(模糊)或 uuid，可多次')
    ap.add_argument('--port', type=int, default=None)
    a = ap.parse_args()

    port = find_port(a.port)
    if not port:
        print('* 找不到桥（49620-49629 无响应）')
        return 1
    exe = make_exe(port)

    def val(code, timeout=300):
        r = exe(code, timeout)
        if 'error' in r:
            raise RuntimeError(r['error'])
        return r.get('result')

    pages = []
    info = val(PAGES_JS)
    if isinstance(info, str):        # 桥回传的是 JSON 字符串，必须先解析
        try:
            info = json.loads(info)
        except ValueError:
            info = None
    if isinstance(info, list):
        for sch in info:                      # Schematic
            if not isinstance(sch, dict):
                continue
            for pg in (sch.get('page') or []):  # Schematic Page
                if isinstance(pg, dict):
                    pages.append((pg.get('name') or pg.get('title') or '',
                                  pg.get('uuid') or pg.get('id')))
    if a.page:
        want = []
        for spec in a.page:
            for nm, uu in pages:
                if spec == uu or spec.lower() in str(nm).lower():
                    want.append((nm, uu))
                    break
            else:
                want.append((spec, spec))
        pages = want
    if not pages:
        print('* 取不到原理图页')
        return 1

    allnets = defaultdict(lambda: defaultdict(list))
    total_orphan = 0
    for tag, uuid in pages:
        s = json.loads(val(SNAP.replace('__PG__', uuid), timeout=400))
        uf = UF()
        for w in s['wires']:
            P = [('pt', p[0], p[1]) for p in w['P']]      # 坐标统一 tuple（回读是 list）
            for i in range(1, len(P)):
                uf.union(P[0], P[i])
        pin_at, flag_at = defaultdict(list), defaultdict(set)
        for c in s['comps']:
            for pn, x, y in c['pins']:
                pin_at[uf.find(('pt', x, y))].append('%s.%s' % (c['des'], pn))
        for f in s['flags']:
            flag_at[uf.find(('pt', f['x'], f['y']))].add(f['nm'])

        roots = set(list(pin_at) + list(flag_at))
        gflag = {r: set(flag_at.get(r, ())) for r in roots}
        wirepts = set()
        for w in s['wires']:
            for p in w['P']:
                wirepts.add((p[0], p[1]))

        print('=' * 68)
        print('%s   器件 %d / 导线 %d / 旗标 %d'
              % (tag, len(s['comps']), len(s['wires']), len(s['flags'])))

        print('-- 1 两端几何同网（被导线短接）--')
        hit = 0
        for c in s['comps']:
            if len(c['pins']) != 2:
                continue
            ra = uf.find(('pt', c['pins'][0][1], c['pins'][0][2]))
            rb = uf.find(('pt', c['pins'][1][1], c['pins'][1][2]))
            if ra == rb:
                print('   [!] %-6s 两脚同网 %s' % (c['des'], sorted(gflag.get(ra, ()))))
                hit += 1
        if not hit:
            print('   （无）')

        print('-- 1b 两侧挂同名旗标 => 被并网短路（本工具独有，DRC 报不出来）--')
        hit = 0
        for c in s['comps']:
            if len(c['pins']) != 2:
                continue
            ra = uf.find(('pt', c['pins'][0][1], c['pins'][0][2]))
            rb = uf.find(('pt', c['pins'][1][1], c['pins'][1][2]))
            if ra == rb:
                continue
            common = gflag.get(ra, set()) & gflag.get(rb, set())
            if common:
                print('   [!] %-6s 两脚分别挂同名旗标 %s => 被短路、失去作用 @(%d,%d)'
                      % (c['des'], sorted(common), c['x'], c['y']))
                hit += 1
        if not hit:
            print('   （无）')

        print('-- 2 一域多旗标名（隐性短路）--')
        hit = 0
        for r in roots:
            if len(gflag.get(r, ())) > 1:
                print('   [!] %s  含引脚 %s' % (sorted(gflag[r]), sorted(pin_at.get(r, []))[:10]))
                hit += 1
        if not hit:
            print('   （无）')

        print('-- 3 匿名网（含引脚、无旗标；内部节点属正常）--')
        for r in roots:
            if pin_at.get(r) and not gflag.get(r):
                print('   %s' % sorted(pin_at[r]))

        print('-- 4 孤儿旗标（未被任何导线咬住）--')
        hit = 0
        for f in s['flags']:
            if (f['x'], f['y']) not in wirepts:
                print('   [!] %-10s @(%d,%d) id=%s' % (f['nm'], f['x'], f['y'], f['id']))
                hit += 1
        if not hit:
            print('   （无）')
        total_orphan += hit

        for r in roots:
            for nm in gflag.get(r, ()):
                for p in pin_at.get(r, []):
                    allnets[nm][tag].append(p)

    print('=' * 68)
    print('跨页命名网总表')
    for nm in sorted(allnets):
        mem = []
        for tag, _ in pages:
            for m in sorted(set(allnets[nm].get(tag, []))):
                mem.append('%s.%s' % (tag, m))
        print('  %-14s : %s' % (nm, ' , '.join(mem)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
