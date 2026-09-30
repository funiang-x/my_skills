#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_test_gate.py — skill_gate.py 的冒烟自测（无证场景四态）。

测：
  1) 无证 · 写仓库内文件            → 应拦  (rc=2)
  2) 无证 · 跑受管脚本（eda_sch.py）→ 应拦  (rc=2)
  3) 任意 · 跑 preflight 自己       → 应放行 (rc=0)
  4) 无证 · 写仓库外文件            → 应放行 (rc=0)

测试期间把证池临时挪走（模拟"无证"），结束后恢复。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                               # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "hooks" / "skill_gate.py"
STATE = REPO / ".state" / "preflight.json"


def run(payload):
    p = subprocess.run([sys.executable, str(GATE)], input=json.dumps(payload),
                       capture_output=True, text=True, encoding="utf-8",
                       cwd=str(REPO))
    return p.returncode


def main():
    bak = STATE.parent / "preflight.json.bak-test"
    existed = STATE.exists()
    if existed:
        shutil.move(str(STATE), str(bak))
    results = []
    try:
        wrote_repo = {"tool_name": "write_to_file",
                      "tool_input": {"file_path": str(REPO / "README.md")}}
        results.append(("无证·写仓库内文件", 2, run(wrote_repo)))

        run_script = {"tool_name": "execute_command",
                      "tool_input": {"command": "python /tmp/eda_sch.py audit"}}
        results.append(("无证·跑受管脚本", 2, run(run_script)))

        pre = {"tool_name": "execute_command",
               "tool_input": {"command": "python %s/tools/preflight.py 软件/编码" % REPO}}
        results.append(("跑 preflight 自己", 0, run(pre)))

        outside = {"tool_name": "write_to_file",
                   "tool_input": {"file_path": str(Path.home() / "some_project" / "main.c")}}
        results.append(("无证·写仓库外文件", 0, run(outside)))
    finally:
        if existed:
            shutil.move(str(bak), str(STATE))

    ok = True
    print("skill_gate 冒烟自测（无证场景）")
    for name, want, got in results:
        good = want == got
        ok = ok and good
        print("  [%s] %s：期望 rc=%d 实际 rc=%d" % ("✓" if good else "✗", name, want, got))
    print("EXIT: %d" % (0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
