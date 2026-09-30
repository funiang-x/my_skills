#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_check_public.py — 公开层 / 本地层 边界检查（推送前跑一次）。

用法：python tools/_check_public.py

判定对象 = `git ls-files`（**已暂存/已跟踪**的文件清单）——即"将来会被推上去的东西"。
"""
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                               # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent

out = subprocess.run(["git", "-C", str(REPO), "ls-files"],
                     capture_output=True, text=True, encoding="utf-8").stdout
files = [f for f in out.splitlines() if f.strip()]
print("tracked（已跟踪）= %d 个文件\n" % len(files))

checks = [
    ("实战台账 LESSONS 混入",
     r"LESSONS"),
    ("第三方大件 ppt-master 混入",
     r"^ppt-master/"),
    ("Trae 系 skill 混入",
     r"^(build-cmake|debug-jlink|flash-jlink|"
     r"serial-monitor|serial-shell|static-analysis|shared)/"),
    ("运行态 .state 混入",
     r"^\.state/|/\.state/"),
    ("第三方克隆 embedded_ai_skills 混入",
     r"^embedded_ai_skills/"),
    ("PATCHES.diff 内部留证混入",
     r"PATCHES\.diff"),
]

bad = False
for name, pat in checks:
    hits = [f for f in files if re.search(pat, f)]
    if hits:
        bad = True
        print("✗ %s → %s" % (name, ", ".join(hits[:5])))
    else:
        print("✓ 干净：%s" % name)

tops = sorted({f.split("/")[0] for f in files})
print("\n顶层条目（%d）：" % len(tops))
print(", ".join(tops))

must = ["ROUTE.md", "WORKFLOW.md", "PREREQUISITES.md", "AGENTS.md", "README.md",
        "LICENSE", ".gitignore",
        "tools/preflight.py", "tools/skillman.py", "tools/gate.py", "tools/ops.json",
        "tools/skill_audit.py",
        "hooks/skill_gate.py", "templates/global-door.md", "templates/project-door.md",
        "templates/hook-settings.json",
        "ponytail/SKILL.md", "easyeda-api/SKILL.md", "easyeda-viewer/SKILL.md",
        "agent-skill-wiring/SKILL.md", "install-github-skill/SKILL.md"]
missing = [m for m in must if m not in files]
if missing:
    bad = True
    print("\n✗ 缺失关键文件：%s" % missing)
else:
    print("\n✓ 关键文件全在（%d 项抽查）" % len(must))

print("\nEXIT:", 1 if bad else 0)
raise SystemExit(1 if bad else 0)
