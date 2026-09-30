#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eda_sch.py — 嘉立创EDA专业版原理图「三件事」的统一自动化入口

本机实测（2026-09-29，EDA V3.2.65）确立的三个一等公民操作：

  nc     批量打 NC（非连接标志）—— 走页面源码注入，全程不碰鼠标键盘
  drc    跑 DRC 并把结果**可观测**：面板计数徽标 + 面板「导出」按钮落盘的全量日志
  value  审计并回填元件「值」属性 —— 值来自 **EDA 库器件自身**（权威，不编造）

设计原则（与 skill SKILL.md / LESSONS.md 一致）：
  * 默认干跑，`--apply` 才写回；写回前先备份
  * 一切改动**回读自证**；DRC 计数**改前记基线、改后比对**
  * 桥端口自动在 49620-49629 探测；代码单行执行、不带 `//` 注释

用法示例：
    python eda_sch.py audit  --all
    python eda_sch.py drc    --all --export ./drc_logs
    python eda_sch.py value  --all                 # 干跑，只打印计划
    python eda_sch.py value  --all --apply         # 真的写回
    python eda_sch.py nc     --page INT --pins EVK1.81,EVK1.83 --apply

退出码：0 成功 / 1 出错 / 2 干跑发现异常
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

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

HERE = os.path.dirname(os.path.abspath(__file__))
INJECT_NC = os.path.join(HERE, 'inject_nc.py')

SRC_LEN = 'const s = await eda.sys_FileManager.getDocumentSource(); return s.length;'
SRC_SLICE = 'const s = await eda.sys_FileManager.getDocumentSource(); return s.slice(%d, %d);'
PAGE_INFO = 'return await eda.dmt_Schematic.getCurrentSchematicAllSchematicPagesInfo();'

# 只列「有位号的真器件」，并带上完整 otherProperty（用于审计「值」是否为空）
PARTS_JS = '''
const comps = await eda.sch_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  if ((c.componentType||"") !== "part") continue;
  const des = c.designator || "";
  if (!des) continue;
  let op = null, dev = "";
  try {
    const g = await eda.sch_PrimitiveComponent.get([c.primitiveId]);
    const f = Array.isArray(g) ? g[0] : g;
    op = (f && f.otherProperty) || null;
    dev = (f && f.component && f.component.name) || (f && f.name) || "";
  } catch (e) {}
  out.push({id: c.primitiveId, des: des, dev: dev, op: op});
}
return out;
'''


# ------------------------------------------------------------------ 桥
def find_port(explicit=None):
    for p in ([explicit] if explicit else range(49620, 49630)):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/health' % p, timeout=2) as r:
                b = json.loads(r.read().decode('utf-8'))
            if b.get('service') == 'easyeda-bridge':
                return p, b
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
        except Exception as e:                                        # noqa: BLE001
            return {'error': str(e)[:200]}

    def value(code, timeout=300):
        return exe(code, timeout).get('result')

    return exe, value


def connect(port=None):
    p, health = find_port(port)
    if not p:
        print('★ 找不到桥（49620-49629 均无响应）。先启动桥 + 在 EDA 里加载 Run API Gateway 扩展。')
        return None, None, None
    if not health.get('edaConnected'):
        print('★ 桥在 %d，但 edaConnected=false —— EDA 未连上扩展。' % p)
        return None, None, None
    exe, value = make_exe(p)
    return p, exe, value


def list_pages(value):
    info = value(PAGE_INFO)
    pages = []
    if isinstance(info, list):
        for x in info:
            if isinstance(x, dict):
                pages.append((x.get('name') or x.get('title') or '', x.get('uuid') or x.get('id')))
    return pages


def resolve_page(value, spec):
    if re.fullmatch(r'[0-9a-f]{16}', spec or ''):
        return spec
    for name, uuid in list_pages(value):
        if spec and spec.lower() in str(name).lower():
            return uuid
    return None


def open_page(exe, uuid):
    exe('await eda.dmt_EditorControl.openDocument("%s");'
        'await new Promise(r => setTimeout(r, 800)); return 1;' % uuid, timeout=120)
    time.sleep(0.5)


def read_source(value, chunk=40000):
    n = value(SRC_LEN)
    if not isinstance(n, int):
        raise RuntimeError('取源码长度失败: %r' % (n,))
    parts, i = [], 0
    while i < n:
        piece = value(SRC_SLICE % (i, min(i + chunk, n)))
        if not isinstance(piece, str):
            raise RuntimeError('第 %d 块取回失败: %r' % (i, piece))
        parts.append(piece)
        i += len(piece)
    return ''.join(parts)


# ------------------------------------------------------------------ 通用：取页清单
def target_pages(value, args):
    pages = list_pages(value)
    if not pages:
        return []
    if getattr(args, 'page', None):
        u = resolve_page(value, args.page)
        return [(n, x) for n, x in pages if x == u] if u else []
    if getattr(args, 'all', False):
        return pages
    return pages[:1]


# ------------------------------------------------------------------ audit
def cmd_audit(args):
    port, exe, value = connect(args.port)
    if not port:
        return 1
    print('桥端口 %d，EDA 已连接。' % port)
    rows, summary = [], []
    for name, uuid in target_pages(value, args):
        open_page(exe, uuid)
        src = read_source(value)
        nc = src.count('"key":"NO_CONNECT"')
        parts = value(PARTS_JS, timeout=400)
        if not isinstance(parts, list):
            print('  ★ %s 取器件失败: %r' % (name, parts))
            continue
        empty, has_key = [], 0
        for p in parts:
            op = p.get('op') or {}
            if 'Value' in op:
                has_key += 1
                if not str(op.get('Value') or '').strip():
                    empty.append(p)
        for p in empty:
            rows.append({'page': name, 'des': p['des'], 'dev': p['dev'],
                         'id': p['id'], 'op': p.get('op')})
        summary.append({'page': name, 'uuid': uuid, 'src_len': len(src), 'nc': nc,
                        'parts': len(parts), 'with_value_key': has_key,
                        'empty_value': len(empty)})
        print('  %-18s 源码 %6d  NC %2d  器件 %2d  有Value键 %2d  空值 %2d'
              % (name, len(src), nc, len(parts), has_key, len(empty)))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump({'summary': summary, 'empty_value': rows}, f, ensure_ascii=False, indent=1)
        print('已写 %s' % args.json)
    return 0


# ------------------------------------------------------------------ nc（委派 inject_nc.py）
def cmd_nc(args):
    if not os.path.exists(INJECT_NC):
        print('★ 找不到 %s' % INJECT_NC)
        return 1
    cmd = [sys.executable, INJECT_NC, '--page', args.page, '--pins', args.pins]
    if args.apply:
        cmd.append('--apply')
    if args.port:
        cmd += ['--port', str(args.port)]
    return subprocess.call(cmd)


# ------------------------------------------------------------------ drc
DRC_RUN = ('try { await eda.sch_Drc.check(false, true, false); }'
           'catch(e) { return "ERR " + String(e.message||e); }'
           'await new Promise(r => setTimeout(r, 3500));'
           'const el = document.getElementById("schDrcPrimaryLog");'
           'return el ? el.textContent : "NO_PANEL";')

DRC_EXPORT = '''
const p = document.getElementById("schDrcPrimaryLog");
if (!p) return "NO_PANEL";
const box = p.querySelector("[class*='log-btns']");
if (!box) return "NO_BTNS";
const btn = [...box.querySelectorAll("button")].filter(b => (b.textContent||"").trim() === "导出")[0];
if (!btn) return "NO_EXPORT_BTN";
btn.click();
return "CLICKED";
'''

CNT_RE = re.compile(r'全部\((\d+)\)致命错误\((\d+)\)错误\((\d+)\)警告\((\d+)\)信息\((\d+)\)')


def parse_counts(text):
    m = CNT_RE.search(text or '')
    if not m:
        return None
    return {'all': int(m.group(1)), 'fatal': int(m.group(2)), 'error': int(m.group(3)),
            'warn': int(m.group(4)), 'info': int(m.group(5))}


def _downloads_dir():
    return os.path.join(os.path.expanduser('~'), 'Downloads')


def cmd_drc(args):
    port, exe, value = connect(args.port)
    if not port:
        return 1
    print('桥端口 %d，EDA 已连接。' % port)
    baseline = None
    if args.baseline and os.path.exists(args.baseline):
        baseline = json.load(open(args.baseline, encoding='utf-8'))
        print('基线: %s' % json.dumps(baseline, ensure_ascii=False))
    result, logdir = {}, args.export
    if logdir:
        os.makedirs(logdir, exist_ok=True)
    for name, uuid in target_pages(value, args):
        open_page(exe, uuid)
        panel = value(DRC_RUN, timeout=200)
        cnt = parse_counts(panel if isinstance(panel, str) else '')
        print('\n=== %s (%s) ===' % (name, uuid))
        if cnt:
            print('  全部(%d) 致命错误(%d) 错误(%d) 警告(%d) 信息(%d)'
                  % (cnt['all'], cnt['fatal'], cnt['error'], cnt['warn'], cnt['info']))
        else:
            print('  ★ 面板计数解析失败：%r' % (str(panel)[:160],))
        result[name] = cnt
        if logdir and args.click_export:
            dl = _downloads_dir()
            before = set(os.listdir(dl)) if os.path.isdir(dl) else set()
            value(DRC_EXPORT, timeout=120)
            time.sleep(3.0)
            after = set(os.listdir(dl)) if os.path.isdir(dl) else set()
            new = sorted(after - before)
            if new:
                src = os.path.join(dl, new[-1])
                dst = os.path.join(logdir, 'drc_%s_%s.txt'
                                   % (re.sub(r'[^\w]+', '_', name), time.strftime('%Y%m%d_%H%M%S')))
                shutil.copyfile(src, dst)
                print('  全量日志已存: %s（%d 字节，源 %s）' % (dst, os.path.getsize(dst), new[-1]))
            else:
                print('  ⚠ 点了「导出」但 %s 里没出现新文件 —— 该版本 EDA 会弹「另存为」对话框。' % dl)
                print('    → 请在 EDA 里点「保存」或「取消」；计数徽标已够用，全量日志属可选。')
        elif logdir:
            print('  （未点「导出」——避免弹对话框；需要全量日志时加 --click-export）')
    if args.baseline and not os.path.exists(args.baseline):
        json.dump(result, open(args.baseline, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\n基线已写 %s' % args.baseline)
    return 0


# ------------------------------------------------------------------ value
def strip_dev_suffix(dev):
    """0805W8F1002T5E_C17414 -> 0805W8F1002T5E；再兜底去 -xxx 后缀。"""
    d = re.sub(r'_C\d+$', '', dev or '')
    return d.strip()


LIB_LOOKUP = '''
const names = %s;
const out = {};
for (const n of names) {
  try {
    let s = await eda.lib_Device.search(n);
    if ((!s || !s.length) && n.indexOf("_") > 0) s = await eda.lib_Device.search(n.split("_")[0]);
    let value = "", supplier = "", mfrPart = "", libName = "", symDesc = "";
    if (s && s.length) {
      const g = await eda.lib_Device.get([s[0].uuid]);
      const f = Array.isArray(g) ? g[0] : g;
      const op = (f && f.property && f.property.otherProperty) || {};
      value = op["Value"] || ""; supplier = op["Supplier Part"] || "";
      mfrPart = op["Manufacturer Part"] || ""; libName = (f && f.name) || "";
    }
    if (!value) {
      const ss = await eda.lib_Symbol.search(n);
      if (ss && ss.length) symDesc = ss[0].description || "";
    }
    out[n] = {found: !!(s && s.length), uuid: (s && s[0] && s[0].uuid) || "",
              libName: libName, value: value, supplier: supplier,
              mfrPart: mfrPart, symDesc: symDesc};
  } catch (e) { out[n] = {found: false, err: String(e.message||e)}; }
}
return out;
'''

# 从库符号描述里抠出「值」：如 "22uF (226) ±10% 25V" / "1KΩ (1001) ±1%" / "470pF (471) ±5% 50V"
DESC_VAL_RE = re.compile(
    r'^\s*([0-9]+(?:\.[0-9]+)?\s*(?:[pnuµmμ]?F|[kKmM]?Ω|[unµmμ]?H|V|A))\b')


def value_from_desc(desc):
    m = DESC_VAL_RE.match(desc or '')
    return m.group(1).replace(' ', '') if m else ''



def cmd_value(args):
    port, exe, value = connect(args.port)
    if not port:
        return 1
    print('桥端口 %d，EDA 已连接。' % port)

    pages = target_pages(value, args)
    plan = []          # [{page,uuid,des,id,dev,old_op,new_value}]
    audit = []
    for name, uuid in pages:
        open_page(exe, uuid)
        parts = value(PARTS_JS, timeout=400)
        if not isinstance(parts, list):
            print('  ★ %s 取器件失败: %r' % (name, parts))
            continue
        n_key = n_empty = 0
        for p in parts:
            op = p.get('op') or {}
            if 'Value' not in op:
                continue
            n_key += 1
            if str(op.get('Value') or '').strip():
                continue
            n_empty += 1
            plan.append({'page': name, 'uuid': uuid, 'des': p['des'], 'id': p['id'],
                         'dev': p['dev'], 'op': op})
        audit.append((name, len(parts), n_key, n_empty))
        print('  %-18s 器件 %2d  有Value键 %2d  空值 %2d' % (name, len(parts), n_key, n_empty))

    if not plan:
        print('没有需要补「值」的元件。')
        return 0

    # 唯一器件名 -> 库值（**分批**：一次查 20+ 个型号会超时/响应过大）
    devs = sorted({strip_dev_suffix(p['dev']) for p in plan if p['dev']})
    print('\n查库：%d 个唯一型号（分批，每批 8 个）…' % len(devs))
    lib = {}
    BATCH = 8
    for i in range(0, len(devs), BATCH):
        chunk = devs[i:i + BATCH]
        got = value(LIB_LOOKUP % json.dumps(chunk), timeout=400)
        if not isinstance(got, dict):
            print('★ 库查询第 %d 批失败: %r' % (i // BATCH + 1, got))
            got = {}
        lib.update(got)
    if not lib:
        print('★ 库查询全部失败，中止。')
        return 1
    # 汇总：库器件 Value 优先，库符号描述兜底
    resolved = {}
    for d in devs:
        r = lib.get(d) or {}
        val, src = str(r.get('value') or '').strip(), 'lib.otherProperty.Value'
        if not val:
            val = value_from_desc(r.get('symDesc'))
            src = 'lib_Symbol.description' if val else ''
        resolved[d] = (val, src, r)
        print('   %-24s -> %-10s %s' % (d, val or '★无值', ('[%s]' % src) if val else ''))

    todo, skip = [], []
    for p in plan:
        d = strip_dev_suffix(p['dev'])
        val, src, _ = resolved.get(d, ('', '', {}))
        if val:
            p['new'] = val
            p['src'] = src
            todo.append(p)
        else:
            skip.append(p)

    print('\n--- 计划（%d 个可补，%d 个库中无值需人工）---' % (len(todo), len(skip)))
    for p in todo:
        print('  %-4s %-6s %-22s 值: (空) -> %s' % (p['page'][:4], p['des'], p['dev'], p['new']))
    for p in skip:
        print('  %-4s %-6s %-22s ★ 库中无 Value，留 [TBD]' % (p['page'][:4], p['des'], p['dev']))

    if not args.apply:
        print('\n[干跑] 加 --apply 才写回。')
        return 0 if todo else 2

    # 备份 + 写回
    bdir = args.backup or os.path.join(tempfile.gettempdir(), 'eda_value_backup')
    os.makedirs(bdir, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    bpath = os.path.join(bdir, 'value_plan_%s.json' % stamp)
    json.dump([{'page': p['page'], 'des': p['des'], 'id': p['id'], 'dev': p['dev'],
                'old': (p['op'] or {}).get('Value', ''), 'new': p['new']} for p in todo],
              open(bpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n计划已备份: %s' % bpath)

    print('写回中…（按页分组，写每页前先切到该页）')
    ok = fail = 0
    cur = None
    for p in todo:
        if p['uuid'] != cur:
            open_page(exe, p['uuid'])
            cur = p['uuid']
        newop = dict(p['op'] or {})
        newop['Value'] = p['new']
        js = ('try { await eda.sch_PrimitiveComponent.modify(%s, {otherProperty: %s});'
              ' return true; } catch(e) { return String(e.message||e); }'
              % (json.dumps(p['id']), json.dumps(newop, ensure_ascii=False)))
        r = value(js, timeout=120)
        if r is True:
            ok += 1
        else:
            fail += 1
            print('  ★ %s.%s 写回失败: %r' % (p['page'], p['des'], r))
    print('写回：成功 %d，失败 %d' % (ok, fail))

    # 回读自证
    print('\n回读自证…')
    bad = []
    for name, uuid in pages:
        open_page(exe, uuid)
        parts = value(PARTS_JS, timeout=400)
        got = {p['des']: (p.get('op') or {}).get('Value', '') for p in parts if isinstance(p, dict)}
        for p in todo:
            if p['page'] != name:
                continue
            v = str(got.get(p['des'], '')).strip()
            if v != p['new']:
                bad.append('%s.%s 期望 %r 实得 %r' % (name, p['des'], p['new'], v))
    if bad:
        print('  ★ 以下未落上：')
        for b in bad:
            print('    ' + b)
        return 1
    print('  ✓ 全部 %d 个已落上并回读一致。' % len(todo))
    exe('try { await eda.sch_Document.save(); } catch(e) {} return 1;', timeout=120)
    print('  已请求保存；请在 EDA 里 Ctrl+S 确认在线工程同步。')
    return 0


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description='嘉立创EDA原理图三件事：nc / drc / value')
    ap.add_argument('--port', type=int, default=None)
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('audit', help='只读体检：器件/NC/空值/DRC')
    a.add_argument('--page'); a.add_argument('--all', action='store_true')
    a.add_argument('--json'); a.set_defaults(func=cmd_audit)

    n = sub.add_parser('nc', help='批量打 NC（源码注入，委派 inject_nc.py）')
    n.add_argument('--page', required=True); n.add_argument('--pins', required=True)
    n.add_argument('--apply', action='store_true'); n.set_defaults(func=cmd_nc)

    d = sub.add_parser('drc', help='跑 DRC，报计数徽标，可导出全量日志')
    d.add_argument('--page'); d.add_argument('--all', action='store_true')
    d.add_argument('--export', help='全量日志落盘目录（需配合 --click-export 才会真的去点「导出」）')
    d.add_argument('--click-export', action='store_true',
                   help='去点 DRC 面板的「导出」按钮。⚠ EDA ≥V4.1.60 会弹「另存为」对话框，'
                        '默认不点；计数徽标已够用时不要加这个参数')
    d.add_argument('--baseline')
    d.set_defaults(func=cmd_drc)

    v = sub.add_parser('value', help='审计并回填元件「值」（值来自 EDA 库器件）')
    v.add_argument('--page'); v.add_argument('--all', action='store_true')
    v.add_argument('--apply', action='store_true'); v.add_argument('--backup')
    v.set_defaults(func=cmd_value)

    args = ap.parse_args()
    # 只有真的会改图的子命令才要开工证（audit / drc 是只读，不拦）
    if getattr(args, 'apply', False):
        _gate_require(('硬件/落图', '硬件/审计'))
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
