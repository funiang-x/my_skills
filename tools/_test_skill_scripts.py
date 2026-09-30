#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_test_skill_scripts.py — 6 个自研工具链 skill 的冒烟自检（**不碰硬件**）。

    python tools/_test_skill_scripts.py

为什么要有它：这 6 个 skill 是公开层的"通用工具链"，但没有 CI。这条自检覆盖
**参数解析 + 环境探测 + 失败分流退出码**三件最容易回归的事；真实烧录/串口读写
不在范围内（无硬件的机器就该跑过，插上板子前不需要它）。

退出码：0 = 全过；1 = 有失败。
"""
from pathlib import Path
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent

# (脚本, 参数, 期望退出码——元组表示"任一即可")
CASES = [
    ("build-cmake/scripts/cmake_builder.py", ["--help"], 0),
    ("build-cmake/scripts/cmake_builder.py", ["--detect"], (0, 2)),
    ("build-cmake/scripts/cmake_builder.py", ["--list-presets", "--source", str(REPO)], 0),
    ("flash-jlink/scripts/jlink_flasher.py", ["--help"], 0),
    ("flash-jlink/scripts/jlink_flasher.py", ["--detect"], (0, 2)),
    ("flash-jlink/scripts/jlink_flasher.py", [], 3),            # 缺 --artifact
    ("debug-jlink/scripts/jlink_debugger.py", ["--detect"], (0, 2)),
    ("debug-jlink/scripts/jlink_debugger.py", [], 3),           # 缺 --device
    ("serial-monitor/scripts/serial_monitor.py", ["--help"], 0),
    ("serial-monitor/scripts/serial_monitor.py", ["--list"], (0, 2)),   # 无 pyserial=2
    ("serial-shell/scripts/shell_proxy.py", [], 3),             # 缺 --port
    ("serial-shell/scripts/shell_proxy.py", ["--port", "COM_X", "--send", "x"], (2, 4)),
    ("static-analysis/scripts/static_analyzer.py", ["--detect"], (0, 2)),
    ("static-analysis/scripts/static_analyzer.py", [], 3),
]


def main():
    failed = 0
    for rel, args, want in CASES:
        p = REPO / rel
        cmd = [sys.executable, str(p)] + args
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        ok = r.returncode in want if isinstance(want, tuple) else r.returncode == want
        print("%s %s %s → 退出码 %d（期望 %s）"
              % ("✓" if ok else "✗", rel, " ".join(args) or "(无参数)",
                 r.returncode, want))
        if not ok:
            failed += 1
            print("  ---- 输出 ----")
            print("  " + (r.stdout or r.stderr).strip().replace("\n", "\n  ")[:600])
    print("\n共 %d 项，失败 %d 项" % (len(CASES), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())