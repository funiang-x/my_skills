#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""static_analyzer.py — static-analysis skill 的执行入口（纯标准库，调外部工具）。

用法：
    python static_analyzer.py --detect
    python static_analyzer.py --cppcheck src Device --include inc
    python static_analyzer.py --clang-tidy src/main.c --compile-commands build
退出码：0=无发现 1=有发现 2=环境缺失 3=参数问题
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

SEV = ("error", "warning", "style", "performance", "portability")
SEV_PAT = re.compile(r": (%s):" % "|".join(SEV))
NOISE_DIRS = ("build", ".git", "node_modules")


def cmd_detect():
    ok = True
    for name, hint in (("cppcheck", "https://cppcheck.sourceforge.io/ 或系统包管理器"),
                       ("clang-tidy", "LLVM 发行版自带"),
                       ("clang", "可选：clang --analyze 静态分析")):
        p = shutil.which(name)
        if p:
            try:
                ver = subprocess.run([p, "--version"], capture_output=True, text=True,
                                     timeout=20).stdout.strip().splitlines()[0]
            except Exception:                                    # noqa: BLE001
                ver = ""
            print("  ✓ %-12s %s" % (name, ver))
        else:
            print("  · %-12s 未找到——%s" % (name, hint))
    if not shutil.which("cppcheck") and not shutil.which("clang-tidy"):
        print("✗ environment-missing：cppcheck 与 clang-tidy 都没有")
        ok = False
    return 0 if ok else 2


def run_cppcheck(a):
    exe = shutil.which("cppcheck")
    if not exe:
        print("✗ environment-missing：找不到 cppcheck（装好后重试）")
        return 2
    paths = a.cppcheck or ["."]
    cmd = [exe, "--enable=warning,style,performance,portability",
           "--inline-suppr", "--quiet", "--template=gcc"]
    for inc in a.include or []:
        cmd += ["-I", inc]
    for p in paths:
        if Path(p).is_dir():
            for n in NOISE_DIRS:
                d = Path(p) / n
                if d.is_dir():
                    cmd += ["-i", str(d)]
    cmd += paths
    print("$ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    findings = [ln for ln in out.splitlines() if SEV_PAT.search(ln)]
    if not findings:
        print("✓ cppcheck：无发现（扫描范围：%s）" % ", ".join(paths))
        return 0
    counts = {s: sum(1 for ln in findings if ": %s:" % s in ln) for s in SEV}
    print("\n发现 %d 条（%s）：" % (len(findings),
                                   ", ".join("%s×%d" % (k, v) for k, v in counts.items() if v)))
    for ln in findings[:30]:
        print("  " + ln)
    if len(findings) > 30:
        print("  …（其余 %d 条略）" % (len(findings) - 30))
    return 1


def run_clang_tidy(a):
    exe = shutil.which("clang-tidy")
    if not exe:
        print("✗ environment-missing：找不到 clang-tidy（装好后重试）")
        return 2
    files = a.clang_tidy or []
    if not files:
        print("✗ 参数问题：--clang-tidy 后面要给文件（如 src/main.c）")
        return 3
    base = [exe, "--quiet"]
    if a.compile_commands:
        base += ["-p", a.compile_commands]
    total = 0
    for f in files:
        r = subprocess.run(base + [f], capture_output=True, text=True)
        hits = [ln for ln in ((r.stdout or "") + (r.stderr or "")).splitlines()
                if "warning:" in ln or "error:" in ln]
        total += len(hits)
        print("--- %s：%d 条 ---" % (f, len(hits)))
        for ln in hits[:20]:
            print("  " + ln)
    return 1 if total else 0


def main():
    ap = argparse.ArgumentParser(description="静态分析：cppcheck / clang-tidy（static-analysis skill）")
    ap.add_argument("--detect", action="store_true", help="探测工具后退出")
    ap.add_argument("--cppcheck", nargs="*", help="用 cppcheck 扫这些路径（默认 .）")
    ap.add_argument("--include", action="append", help="-I 头文件目录（可重复）")
    ap.add_argument("--clang-tidy", nargs="*", help="用 clang-tidy 检查这些文件")
    ap.add_argument("--compile-commands", help="compile_commands.json 所在目录（clang-tidy 的 -p）")
    a = ap.parse_args()

    if a.detect:
        return cmd_detect()
    if a.clang_tidy is not None:
        return run_clang_tidy(a)
    if a.cppcheck is not None:
        return run_cppcheck(a)
    print("✗ 参数问题：--detect / --cppcheck / --clang-tidy 选一个")
    return 3


if __name__ == "__main__":
    sys.exit(main())