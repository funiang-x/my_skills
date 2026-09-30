#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inject_nc.py — 给嘉立创EDA专业版原理图**批量打 NC（非连接标志）**

原理：NC 在页面源码里就是一条普通 ATTR 记录，直接构造并追加，再用
`sys_FileManager.setDocumentSource()` 整体写回。**全程不碰鼠标键盘。**

用法（默认只是干跑，打印计划，不动工程）：

    python inject_nc.py --page INT --pins EVK1.81,EVK1.83,EVK1.84
    python inject_nc.py --page INT --pins EVK1.81,EVK1.83,EVK1.84 --apply

    参数：
      --page   页名（模糊匹配，如 INT / PWR / AFE）或页 uuid
      --pins   逗号分隔的「位号.脚号」，如 EVK1.81,EVK1.83
      --apply  真的写回（不加则只干跑）
      --port   桥端口；不给则自动在 49620-49629 里探测
      --backup 备份目录；默认为 <temp>/eda_nc_backup

退出码：0 = 成功（含"无需改动"）；1 = 出错（未写回）；2 = 干跑发现异常。

安全设计：
  * 默认干跑；写回前先把原源码落盘为备份
  * 只**追加**记录，并 assert 新源码以旧源码为前缀（自证非破坏）
  * ticket / id 全局唯一性检查
  * 写回后**回读**源码与计划逐字节比对（EDA 只会改写 DOCHEAD 的 client/updateTime）

⚠️ 铁律：读源码与写源码之间**不许有人/有操作改动该页**，否则写回的是旧快照，
会整份覆盖掉期间的人工改动。
"""

import argparse
import json
import os
import random
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request

PAGE_INFO_JS = 'return await eda.dmt_Schematic.getCurrentSchematicAllSchematicPagesInfo();'
NC_KEY = '"key":"NO_CONNECT"'
SRC_JS = 'const s = await eda.sys_FileManager.getDocumentSource(); return %s;'


# ---------------------------------------------------------------- 桥
def find_port(explicit=None):
    ports = [explicit] if explicit else range(49620, 49630)
    for p in ports:
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/health' % p, timeout=2) as r:
                body = json.loads(r.read().decode('utf-8'))
            if body.get('service') == 'easyeda-bridge':
                return p, body
        except Exception:
            continue
    return None, None


def make_exe(port):
    url = 'http://127.0.0.1:%d/execute' % port

    def exe(code, timeout=300):
        req = urllib.request.Request(
            url, data=json.dumps({'code': code}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return {'error': 'HTTP %d' % e.code,
                    'body': e.read().decode('utf-8', 'replace')[:400]}
        except Exception as e:                                   # noqa: BLE001
            return {'error': str(e)[:200]}

    def value(code, timeout=300):
        return exe(code, timeout).get('result')
    return exe, value


# ---------------------------------------------------------------- 源码
def read_source(value, chunk=40000):
    """整页源码分块取回（一次 return 大字符串会 HTTP 500）。"""
    n = value(SRC_JS % 's.length;')
    if not isinstance(n, int):
        raise RuntimeError('取源码长度失败: %r' % (n,))
    parts, i = [], 0
    while i < n:
        piece = value(SRC_JS % ('s.slice(%d, %d);' % (i, min(i + chunk, n))))
        if not isinstance(piece, str):
            raise RuntimeError('第 %d 块取回失败: %r' % (i, piece))
        parts.append(piece)
        i += len(piece)
    return ''.join(parts)


def nc_parents(src):
    return set(re.findall(r'"parentId":"([^"]+)"[^}]*?"key":"NO_CONNECT"', src))


def next_free_ids(src, want):
    used = set(re.findall(r'"id":"([0-9a-fA-F]{16})"', src))
    tickets = [int(m) for m in re.findall(r'"ticket":(\d+)', src)]
    zindex = [int(m) for m in re.findall(r'"zIndex":(\d+)', src)]
    t = max(tickets) if tickets else 0
    z = max(zindex) if zindex else 0
    out = []
    rnd = random.Random(20260928)
    for _ in range(want):
        while True:
            rid = ''.join(rnd.choice('0123456789abcdef') for _ in range(16))
            if rid not in used:
                used.add(rid)
                break
        t += 1
        z += 1
        out.append((t, rid, z))
    return out


# ---------------------------------------------------------------- 页面
def resolve_page(value, spec):
    if re.fullmatch(r'[0-9a-f]{16}', spec or ''):
        return spec
    info = value(PAGE_INFO_JS)
    pages = []
    if isinstance(info, list):
        for x in info:
            if isinstance(x, dict):
                pages.append((x.get('name') or x.get('title') or '',
                              x.get('uuid') or x.get('id')))
    for name, uuid in pages:
        if spec and spec.lower() in str(name).lower():
            return uuid
    return None


def open_page(exe, uuid):
    exe('await eda.dmt_EditorControl.openDocument("%s");'
        'await new Promise(r => setTimeout(r, 700)); return 1;', timeout=120)
    time.sleep(0.4)


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description='给 EDA 原理图批量打 NC（源码注入）')
    ap.add_argument('--page', required=True, help='页名（模糊）或页 uuid')
    ap.add_argument('--pins', required=True, help='位号.脚号，逗号分隔')
    ap.add_argument('--apply', action='store_true', help='真的写回（默认干跑）')
    ap.add_argument('--port', type=int, default=None)
    ap.add_argument('--backup', default=os.path.join(tempfile.gettempdir(), 'eda_nc_backup'))
    args = ap.parse_args()

    port, health = find_port(args.port)
    if not port:
        print('★ 找不到桥（49620-49629 均无响应）。先启动桥 + 在 EDA 里加载 Run API Gateway 扩展。')
        return 1
    if not health.get('edaConnected'):
        print('★ 桥在 %d，但 edaConnected=false —— EDA 未连上扩展。' % port)
        return 1
    print('桥端口 %d，EDA 已连接。' % port)
    exe, value = make_exe(port)

    uuid = resolve_page(value, args.page)
    if not uuid:
        print('★ 找不到页 %r。当前工程可用页见下面返回：' % args.page)
        print(' ', json.dumps(value(PAGE_INFO_JS), ensure_ascii=False)[:800])
        return 1
    open_page(exe, uuid)
    print('已切到页 %s' % uuid)

    wanted = [s.strip() for s in args.pins.split(',') if s.strip()]
    specs = []
    for w in wanted:
        if '.' not in w:
            print('★ 忽略非法规格 %r（应为 位号.脚号）' % w)
            continue
        d, n = w.rsplit('.', 1)
        specs.append((d, n))

    # 取引脚坐标
    js = ('const want = %s; const out = {};'
          'const comps = await eda.sch_PrimitiveComponent.getAll();'
          'const seen = [];'
          'for (const d of want) {'
          '  let c = null;'
          // 用 getState_Designator() 匹配：getAll() 的快属性 .designator 对 API 新建件会滞后
          '  for (const x of comps) {'
          '    if (c) break;'
          '    let dd = ""; try { dd = x.getState_Designator() || ""; } catch (e) { dd = x.designator || ""; }'
          '    if (dd) seen.push(dd);'
          '    if (dd === d && ((x.componentType||"") === "part")) c = x;'
          '  }'
          '  if (!c) { out[d] = null; out["__seen"] = seen; continue; }'
          '  const ps = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);'
          '  const m = {};'
          '  for (const p of ps) m[String(p.pinNumber)] ='
          '    {id: p.primitiveId, x: Math.round(p.x), y: Math.round(p.y)};'
          '  out[d] = m;'
          '}'
          'return out;' % json.dumps([d for d, _ in specs]))
    pinmap = value(js, timeout=400)
    if not isinstance(pinmap, dict):
        print('★ 取引脚失败: %r' % (pinmap,))
        return 1

    src = read_source(value)
    print('源码 %d 字符，现有 NO_CONNECT %d 条。' % (len(src), src.count(NC_KEY)))
    have = nc_parents(src)

    todo, skip, err = [], [], []
    for d, n in specs:
        m = pinmap.get(d)
        if not m:
            err.append('%s.%s：页上找不到该器件%s' % (
                d, n,
                ('（页上可用位号：%s）' % '、'.join(sorted(set(pinmap.get('__seen') or []))[:20]))
                if isinstance(pinmap.get('__seen'), list) else ''))
            continue
        p = m.get(n)
        if not p:
            err.append('%s.%s：器件上没有这个脚号' % (d, n))
            continue
        if p['id'] in have:
            skip.append('%s.%s：已有 NC，跳过' % (d, n))
            continue
        todo.append({'pin': '%s.%s' % (d, n), 'pinId': p['id'],
                     'x': p['x'], 'y': -p['y']})
    for e in err:
        print('  ★ ' + e)
    for s in skip:
        print('  - ' + s)
    if not todo:
        print('无需改动。')
        return 0 if not err else 2

    os.makedirs(args.backup, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    bpath = os.path.join(args.backup, 'source_%s_%s.txt' % (uuid, stamp))
    with open(bpath, 'w', encoding='utf-8', newline='') as f:
        f.write(src)
    print('原始源码已备份: %s' % bpath)

    ids = next_free_ids(src, len(todo))
    recs = []
    for job, (t, rid, z) in zip(todo, ids):
        rec = ('{"type":"ATTR","ticket":%d,"id":"%s"}||'
               '{"parentId":"%s","key":"NO_CONNECT","x":%d,"y":%d,"value":"yes","zIndex":%d}'
               % (t, rid, job['pinId'], job['x'], job['y'], z))
        recs.append(rec)
        print('  计划 %-12s parentId=%s  (x=%d, y=%d)' % (job['pin'], job['pinId'], job['x'], job['y']))

    new_src = src + '|\n' + '|\n'.join(recs)
    if not new_src.startswith(src):
        print('★ 自证失败：新源码没有以旧源码为前缀，中止。')
        return 2
    if new_src.count(NC_KEY) != src.count(NC_KEY) + len(recs):
        print('★ 计数自证失败，中止。')
        return 2

    if not args.apply:
        print('\n[干跑] 计划追加 %d 条记录（%d -> %d 字符）。'
              '加 --apply 才写回。' % (len(recs), len(src), len(new_src)))
        return 0

    print('\n写回中…')
    ok = exe('const s = JSON.parse(%s);'
             'try { return await eda.sys_FileManager.setDocumentSource(s); }'
             'catch(e) { return {err: String(e.message||e).slice(0,200)}; }'
             % json.dumps(json.dumps(new_src)), timeout=400).get('result')
    print('setDocumentSource ->', ok)
    if ok is not True:
        print('★ 写回未返回 true，未确认生效。')
        return 1
    time.sleep(1.5)

    back = read_source(value)
    same_len = len(back) == len(new_src)
    print('\n回读：%d 字符（计划 %d）%s' % (len(back), len(new_src), '长度一致' if same_len else '★长度不一致'))
    print('NO_CONNECT: %d -> %d（计划 %d）'
          % (src.count(NC_KEY), back.count(NC_KEY), src.count(NC_KEY) + len(recs)))
    back_have = nc_parents(back)
    lost = [j['pin'] for j in todo if j['pinId'] not in back_have]
    if lost:
        print('★ 这些引脚没落上，请人工复核: %s' % lost)
        return 1
    exe('try { await eda.sch_Document.save(); } catch(e) {} return 1;', timeout=120)
    print('✓ 全部落上，并已请求保存。请在 EDA 里按 Ctrl+S 确认在线工程同步。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
