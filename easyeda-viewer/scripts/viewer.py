#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""viewer.py — 用 easyeda-viewer 看图纸 / 做落图视觉复核

三个子命令：
  dump    从运行中的 EDA 拉取页面源码 -> <out>/*.esch2（viewer 可直接读）
  serve   组一个预览目录（viewer 的 dist/index.html + 那些 .esch2）并**前台**起本地服务
  render  无头渲染自检：报每页的渲染对象数与未知类型数

依赖：viewer 仓库（默认 ~/easyeda-viewer，可用环境变量 EASYEDA_VIEWER_DIR 覆盖）
      dump 还需要 easyeda-api 桥（EDA 客户端 + Run API Gateway 扩展）。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VIEWER_DIR = os.path.expanduser(os.environ.get('EASYEDA_VIEWER_DIR', '~/easyeda-viewer'))
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), 'assets')
RENDER_ASSET = os.path.join(ASSETS, 'render_headless.mjs')
SHOT_ASSET = os.path.join(ASSETS, 'shot_esch2.mjs')
SHOT_DOC_ASSET = os.path.join(ASSETS, 'shot_doc.mjs')
HARNESS_ASSET = os.path.join(ASSETS, 'harness.html')

PY = sys.executable
NODE = (os.environ.get('EASYEDA_VIEWER_NODE')
        or shutil.which('node') or 'node')

# 注：getCurrentSchematicAllSchematicPagesInfo() 在"当前没打开原理图文档"时返回空数组，
# 改用 getAllSchematicsInfo()（返回 Schematic 列表，页在各自 .page[] 里）—— 2026-09-30 实测
PAGE_INFO = ('const s = await eda.dmt_Schematic.getAllSchematicsInfo();'
             'return JSON.stringify(s);')
CUR_DOC = ('const d = await eda.dmt_EditorControl.getCurrentDocumentInfo();'
           'return JSON.stringify(d || null);')
SRC_LEN = 'const s = await eda.sys_FileManager.getDocumentSource(); return s.length;'
SRC_SLICE = 'const s = await eda.sys_FileManager.getDocumentSource(); return s.slice(%d, %d);'


# ---------------------------------------------------------------- 桥（与 eda_sch.py 同源，保持本 skill 自包含）
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


def connect(port=None):
    p, health = find_port(port)
    if not p:
        print('★ 找不到桥（49620-49629 无响应）。dump 需要 EDA 客户端 + Run API Gateway 扩展。')
        return None, None, None
    if not health.get('edaConnected'):
        print('★ 桥在 %d，但 edaConnected=false。' % p)
        return None, None, None
    url = 'http://127.0.0.1:%d/execute' % p

    def exe(code, timeout=300):
        req = urllib.request.Request(
            url, data=json.dumps({'code': code}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return {'error': 'HTTP %d' % e.code}
        except Exception as e:                                       # noqa: BLE001
            return {'error': str(e)[:200]}

    def value(code, timeout=300):
        return exe(code, timeout).get('result')

    return p, exe, value


def read_source(value, chunk=40000):
    n = value(SRC_LEN)
    if not isinstance(n, int):
        raise RuntimeError('取源码长度失败: %r' % (n,))
    parts, i = [], 0
    while i < n:
        piece = value(SRC_SLICE % (i, min(i + chunk, n)))
        if not isinstance(piece, str):
            raise RuntimeError('第 %d 块取回失败' % i)
        parts.append(piece)
        i += len(piece)
    return ''.join(parts)


# ---------------------------------------------------------------- dump
def cmd_dump(args):
    port, exe, value = connect(args.port)
    if not port:
        return 1
    print('桥端口 %d，EDA 已连接。' % port)
    info = value(PAGE_INFO)
    if isinstance(info, str):                 # 桥回传 JSON 字符串
        try:
            info = json.loads(info)
        except ValueError:
            info = None
    pages = []
    for sch in (info or []):                  # Schematic -> 逐页展开
        if not isinstance(sch, dict):
            continue
        for pg in (sch.get('page') or []):
            if isinstance(pg, dict):
                pages.append((pg.get('name') or pg.get('title') or '',
                              pg.get('uuid') or pg.get('id')))
    if not pages:
        print('★ 没取到页清单: %r' % (info,))
        return 1
    if args.page:
        pages = [(n, u) for n, u in pages if args.page.lower() in n.lower()]
    if not args.all and not args.page:
        pages = pages[:1]
    os.makedirs(args.out, exist_ok=True)
    for name, uuid in pages:
        # 换页必须「等足 + 回读确认」，否则会读到上一页的源码（典型症状：两页导出长度一模一样）
        for attempt in range(3):
            exe('await eda.dmt_EditorControl.openDocument("%s");'
                'await new Promise(r => setTimeout(r, 1500)); return 1;' % uuid, timeout=180)
            time.sleep(0.6)
            cur = value(CUR_DOC)
            if isinstance(cur, str):
                try:
                    cur = json.loads(cur)
                except ValueError:
                    cur = None
            cur_uuid = ((cur or {}).get('uuid') or (cur or {}).get('id') or '') \
                if isinstance(cur, dict) else ''
            if not cur_uuid or cur_uuid == uuid:
                break
            print('  （换页未就绪，重试 %d/3：当前 %s，期望 %s）' % (attempt + 1, cur_uuid, uuid))
        src = read_source(value)
        safe = re.sub(r'[^\w\u4e00-\u9fff]+', '_', name.split('-')[0] or uuid)
        p = os.path.join(args.out, '%s.esch2' % safe)
        with open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(src)
        print('  %-18s -> %s  (%d 字符)' % (name, p, len(src)))
    print('提示：改完图要重新 dump，否则 serve 出来的是旧快照。')
    return 0


# ---------------------------------------------------------------- serve
def cmd_serve(args):
    idx = os.path.join(VIEWER_DIR, 'dist', 'index.html')
    if not os.path.exists(idx):
        print('★ 找不到 %s —— 先在 %s 里跑 npm run build。' % (idx, VIEWER_DIR))
        return 1
    os.makedirs(args.dir, exist_ok=True)
    # dist 产物不支持 ?file=，故用 harness 包装：viewer.html + index.html(包装层)
    shutil.copyfile(idx, os.path.join(args.dir, 'viewer.html'))
    shutil.copyfile(HARNESS_ASSET, os.path.join(args.dir, 'index.html'))
    files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith(('.esch2', '.epcb2', '.epan2', '.epro2', '.zip', '.esym2')))
    print('预览目录: %s' % os.path.abspath(args.dir))
    print('可用文件: %s' % (', '.join(files) or '(无 —— 先跑 dump)'))
    print('\n打开地址（把它交给 present_files 或浏览器）:')
    for f in files or ['']:
        print('  http://127.0.0.1:%d/index.html?file=%s' % (args.port, urllib.parse.quote(f)))
    print('\n前台起服务（建议用 run_in_background）…')
    sys.stdout.flush()
    os.chdir(args.dir)
    return subprocess.call([PY, '-m', 'http.server', '--bind', '127.0.0.1', str(args.port)])


# ---------------------------------------------------------------- shot
def cmd_shot(args):
    """无头 Chrome 截图（AI 的"眼睛"）。需要先跑 serve，或给一个已可达的 base。

    - 默认（单文件 .esch2 / 整页）走 `assets/shot_esch2.mjs`；
    - 传 `--doc`（点选文档树里的页）或 `--zoom`（按文档坐标放大）时走 `assets/shot_doc.mjs`
      —— ⚠️ **看真正的图纸要用工程包 `.epro2`**：单页 `.esch2` 不含符号库，
      只会渲染成红色虚线占位框（LESSONS T-54）。
    """
    work = os.path.join(VIEWER_DIR, '.bridge-work', 'skill')
    os.makedirs(work, exist_ok=True)
    url = args.url or ('http://127.0.0.1:%d/index.html?file=%s&chrome=canvas'
                       % (args.port, urllib.parse.quote(args.file or '')))
    if args.doc or args.zoom:
        zx, zy, zt = '0', '0', '0'
        if args.zoom:
            parts = [p.strip() for p in args.zoom.split(',')]
            if len(parts) != 3:
                print('★ --zoom 格式应为 "docX,docY,times"（times 每次 ≈×1.82）')
                return 2
            zx, zy, zt = parts
        dst_name = 'shot_doc.mjs'
        shutil.copyfile(SHOT_DOC_ASSET, os.path.join(work, dst_name))
        argv = [url, os.path.abspath(args.out), args.doc or '',
                str(args.width), str(args.height), str(args.wait), zx, zy, zt]
        print('截图（工程包/文档模式）  doc=%r zoom=%s\n  -> %s' % (args.doc, args.zoom, args.out))
    else:
        dst_name = 'shot_esch2.mjs'
        shutil.copyfile(SHOT_ASSET, os.path.join(work, dst_name))
        argv = [url, os.path.abspath(args.out), str(args.width), str(args.height), str(args.wait)]
        print('截图 %s\n  -> %s' % (url, args.out))
    cmd = [NODE, os.path.join('.bridge-work', 'skill', dst_name)] + argv
    r = subprocess.run(cmd, cwd=VIEWER_DIR, capture_output=True, text=True, encoding='utf-8', errors='replace')
    for line in ((r.stdout or '') + (r.stderr or '')).splitlines():
        if line.startswith(('OK ', 'ERR ', 'click ', 'zoom ', 'PAGEERR')):
            print('  ' + line)
    if r.returncode != 0:
        print(((r.stdout or '') + (r.stderr or ''))[-1200:])
    return r.returncode


# ---------------------------------------------------------------- render
def cmd_render(args):
    if not os.path.isdir(VIEWER_DIR):
        print('★ 找不到 viewer 仓库 %s' % VIEWER_DIR)
        return 1
    work = os.path.join(VIEWER_DIR, '.bridge-work', 'skill')
    os.makedirs(work, exist_ok=True)
    dst = os.path.join(work, 'render_headless.mjs')
    shutil.copyfile(RENDER_ASSET, dst)
    vn = os.path.join(VIEWER_DIR, 'node_modules', 'vite-node', 'vite-node.mjs')
    if not os.path.exists(vn):
        print('★ 找不到 vite-node：%s（先在 viewer 仓库 npm install）' % vn)
        return 1
    cmd = [NODE, vn, '-c', 'vite.smoke.config.ts', os.path.join('.bridge-work', 'skill', 'render_headless.mjs')] + \
          [os.path.abspath(f) for f in args.files]
    print('无头渲染 %d 个文件…' % len(args.files))
    r = subprocess.run(cmd, cwd=VIEWER_DIR, capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    for line in out.splitlines():
        if line.startswith(('OK ', 'ERR ')):
            print('  ' + line)
    if r.returncode != 0 and not any(l.startswith(('OK ', 'ERR ')) for l in out.splitlines()):
        print(out[-1500:])
    print('\n判据：unknown=0 且 obj 数与预期相符 = 这份源码 viewer 完全认得、确实有内容。')
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description='easyeda-viewer：看图纸 / 落图视觉复核')
    ap.add_argument('--port-bridge', dest='port', type=int, default=None, help='EDA 桥端口（dump 用）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    d = sub.add_parser('dump', help='EDA 页面源码 -> .esch2')
    d.add_argument('--out', required=True)
    d.add_argument('--page'); d.add_argument('--all', action='store_true')
    d.set_defaults(func=cmd_dump)

    s = sub.add_parser('serve', help='组预览目录并前台起本地服务')
    s.add_argument('--dir', required=True)
    s.add_argument('--port', type=int, default=8931)
    s.set_defaults(func=cmd_serve)

    r = sub.add_parser('render', help='无头渲染自检')
    r.add_argument('files', nargs='+')
    r.set_defaults(func=cmd_render)

    sh = sub.add_parser('shot', help='无头 Chrome 截图（AI 的眼睛）')
    sh.add_argument('--out', required=True)
    sh.add_argument('--file', help='预览目录里的文件名（配合 --port）')
    sh.add_argument('--url', help='直接用完整 URL（优先）')
    sh.add_argument('--doc', help='工程包模式：文档树里页名的一部分（如 AFE）——切换文档后再截')
    sh.add_argument('--zoom', help='工程包模式：按文档坐标放大 "docX,docY,times"（每次≈×1.82）')
    sh.add_argument('--port', type=int, default=8931)
    sh.add_argument('--width', type=int, default=1800)
    sh.add_argument('--height', type=int, default=1200)
    sh.add_argument('--wait', type=int, default=8000, help='加载后等待毫秒数')
    sh.set_defaults(func=cmd_shot)

    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
