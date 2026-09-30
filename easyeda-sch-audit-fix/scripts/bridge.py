# -*- coding: utf-8 -*-
"""与嘉立创 EDA Pro 桥接通信的公共件（各脚本 `from bridge import run, pages`）。

- **端口不写死**：本机桥在 49620-49629 里挑第一个可用的，这里自动探测（缓存一次）。
- `pages()`：返回 `{页名: uuid}`。**不要**用 `getCurrentSchematicAllSchematicPagesInfo()`——
  它在"当前没打开原理图文档"时返回**空数组**（2026-09-30 实测）；`getAllSchematicsInfo()` 任何时候都有效。
"""
import json
import urllib.error
import urllib.request

_PORTS = range(49620, 49630)
_base = None


def _find():
    global _base
    if _base:
        return _base
    for p in _PORTS:
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/health' % p, timeout=2) as r:
                body = json.loads(r.read().decode('utf-8'))
            if body.get('service') == 'easyeda-bridge':
                _base = 'http://127.0.0.1:%d' % p
                return _base
        except Exception:                                        # noqa: BLE001
            continue
    raise RuntimeError('找不到桥（49620-49629 无响应）。先启动桥 + 在 EDA 里加载 Run API Gateway 扩展。')


def exec_js(code, timeout=60):
    req = urllib.request.Request(
        _find() + '/execute',
        data=json.dumps({'code': code}, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:                          # 大字符串回传会 500
        return {'error': 'HTTP %d' % e.code}


def run(code, timeout=60):
    r = exec_js(code, timeout)
    if not r.get('success'):
        raise RuntimeError(r.get('error'))
    return r['result']


def as_obj(v):
    """桥回传的 JSON 字符串 -> 对象。"""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def pages():
    """{页名: uuid}，覆盖工程下所有原理图页。"""
    out = {}
    for sch in (as_obj(run('const s = await eda.dmt_Schematic.getAllSchematicsInfo();'
                           'return JSON.stringify(s);')) or []):
        for pg in ((sch or {}).get('page') or []):
            if isinstance(pg, dict):
                out[pg.get('name') or pg.get('uuid')] = pg.get('uuid')
    return out


def open_page(uuid, settle_ms=1500):
    """切页并**等足**（换太快会读到上一页的源码，见 easyeda-viewer/LESSONS.md T-01）。"""
    run('await eda.dmt_EditorControl.openDocument("%s");'
        'await new Promise(r => setTimeout(r, %d)); return 1;' % (uuid, settle_ms),
        timeout=max(60, settle_ms // 1000 + 60))
