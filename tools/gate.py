#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate.py — 脚本级开工闸门（与平台无关的那一层）。

平台钩子（`hooks/skill_gate.py`，PreToolUse）只能覆盖支持钩子的客户端。
本文件把同一道闸门做进 **skill 自己的脚本**：改图只能走 `eda_sch.py` / `dangling.py` /
`delete_part.py`，**闸门做进脚本 = 闸门做进操作本身**，任何客户端都绕不过。

用法（各 skill 脚本入口处，**防御式导入**，找不到本库就放行）：

    import os, sys
    _here = os.path.dirname(os.path.abspath(__file__))
    for _d in (os.environ.get("SKILLS_TOOLS"),
               os.path.abspath(os.path.join(_here, "..", "..", "tools")),
               os.path.abspath(os.path.join(_here, "..", "..", "..", "..", "workbench", "tools"))):
        if _d and os.path.isfile(os.path.join(_d, "gate.py")):
            sys.path.insert(0, _d)
            break
    try:
        from gate import require
        require("硬件/落图")          # 无有效开工证 → 打印指引并 sys.exit(3)
    except ImportError:
        pass                          # 不在本库里（skill 被单独拷走）→ 放行

设计取舍：
  · **找不到本库就放行**（fail-open）—— skill 是可移植资产，不能因为离开本库就跑不动。
  · **只拦"写"类动作**；只读脚本（如 `audit_sch.py`）不接闸门——读不需要许可。
  · 证与钩子层共用同一份 `.state/preflight.json`，两边结论永远一致。
"""
from pathlib import Path
import hashlib
import json
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".state" / "preflight.json"
TTL_HOURS = 8


def _tokens():
    try:
        return json.loads(STATE.read_text(encoding="utf-8")).get("tokens", [])
    except Exception:                                            # noqa: BLE001
        return []


def check(ops):
    """返回 (是否放行, 说明)。`ops` = 本次动作接受的任务类型（任一命中即可）。"""
    if isinstance(ops, str):
        ops = [ops]
    pool = _tokens()
    if not pool:
        return False, "(无证)"
    seen = []
    for d in pool:
        op = d.get("op", "?")
        fresh = (time.time() - d.get("ts", 0)) <= TTL_HOURS * 3600
        intact = all(
            hashlib.sha256((REPO / n / "SKILL.md").read_bytes()).hexdigest() == h
            for n, h in (d.get("skills") or {}).items()
            if (REPO / n / "SKILL.md").exists())
        seen.append(op + ("" if fresh and intact else
                          ("(超时)" if not fresh else "(skill已改，证作废)")))
        if fresh and intact and op in ops:
            return True, op
    return False, ",".join(seen)


def require(ops):
    """不满足就打印指引并以退出码 3 结束（2 留给平台钩子，别混）。"""
    if isinstance(ops, str):
        ops = [ops]
    ok, got = check(ops)
    if ok:
        return
    sys.stderr.write(
        "\n⛔ 未开工前置 —— 本脚本会改动图纸/工作区，必须先读 skill 条款。\n"
        "   当前证：%s\n"
        "   本操作接受的任务类型：%s\n\n"
        "   请现在执行（任选其一，按你要做的事）：\n%s\n"
        "   它会把这个操作**该读的 skill 条款正文打印出来**，并签发开工证。\n"
        "   读完条款再重跑本脚本（证 8 小时有效；skill 内容一改即作废）。\n\n"
        % (got, " / ".join(ops),
           "\n".join("     python %s/tools/preflight.py %s" % (REPO.as_posix(), o)
                     for o in ops)))
    raise SystemExit(3)


if __name__ == "__main__":
    ops = sys.argv[1:]
    if not ops:
        print("用法： python tools/gate.py <任务类型> [...]   （检查当前证是否够用）")
        print("当前证：", ", ".join(t.get("op", "?") for t in _tokens()) or "（无）")
        raise SystemExit(0)
    ok, got = check(ops)
    print(("✅ 放行：%s" % got) if ok else ("⛔ 拦下：当前证=%s，需要 %s" % (got, ops)))
    raise SystemExit(0 if ok else 3)
