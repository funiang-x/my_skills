#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jlink_debugger.py — debug-jlink skill 的执行入口（纯标准库）。

用法：
    python jlink_debugger.py --detect
    python jlink_debugger.py --server-only --device STM32F407VG
    python jlink_debugger.py --device STM32F407VG --artifact app.elf \
        --cmd "info registers" --cmd "bt"
退出码：0=成功 2=环境缺失 3=参数问题 4=连接失败 5=目标响应异常
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass


def find_tool(*names):
    """在 JLINK_DIR / JLINK_PATH、PATH、默认安装目录里找工具 → Path | None。

    （与 flash-jlink 的同名小函数刻意重复：每个 skill 要能独立分发。）
    """
    env = os.environ.get("JLINK_DIR") or os.environ.get("JLINK_PATH")
    cands = []
    if env:
        cands += [Path(env), Path(env) / names[0]]
    for n in names:
        w = shutil.which(n)
        if w:
            cands.append(Path(w))
    if os.name == "nt":
        roots = [r"C:\Program Files\SEGGER", r"C:\Program Files (x86)\SEGGER"]
    else:
        roots = ["/opt/SEGGER", str(Path.home() / "SEGGER"), "/usr/local/SEGGER"]
    for root in roots:
        rp = Path(root)
        if rp.is_dir():
            for n in names:
                cands += sorted(rp.glob("JLink*/" + n), reverse=True)
    for c in cands:
        if c.is_file():
            return c
    return None


def server_exe():
    return find_tool("JLinkGDBServerCL.exe", "JLinkGDBServerCL",
                     "JLinkGDBServer.exe", "JLinkGDBServer")


def gdb_exe(override):
    if override:
        return override if Path(override).is_file() or shutil.which(override) else None
    return shutil.which("arm-none-eabi-gdb")


def cmd_detect():
    ok = True
    srv = server_exe()
    print("%s J-Link GDB Server：%s" % ("✓" if srv else "✗", srv or "未找到"))
    ok = ok and bool(srv)
    g = gdb_exe(None)
    print("%s GDB（arm-none-eabi-gdb）：%s" % ("✓" if g else "✗", g or "未找到（用 --gdb 指定路径）"))
    ok = ok and bool(g)
    return 0 if ok else 2


def wait_port(port, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def server_cmd(exe, dev, iface, speed, port):
    return [str(exe), "-device", dev, "-if", iface, "-speed", str(speed),
            "-port", str(port), "-singlerun", "-silent"]


def main():
    ap = argparse.ArgumentParser(description="J-Link GDB Server / 批量取证（debug-jlink skill）")
    ap.add_argument("--detect", action="store_true", help="探测 GDB Server 与 GDB 后退出")
    ap.add_argument("--device", help="芯片型号，如 STM32F407VG（必填）")
    ap.add_argument("--interface", default="SWD", choices=["SWD", "JTAG"])
    ap.add_argument("--speed", type=int, default=4000, help="kHz，默认 4000")
    ap.add_argument("--port", type=int, default=2331, help="GDB Server 端口，默认 2331")
    ap.add_argument("--artifact", help="带符号 ELF（给 gdb 加载符号）")
    ap.add_argument("--cmd", action="append", help="要执行的 gdb 命令（可重复；默认 info registers + bt）")
    ap.add_argument("--gdb", help="gdb 可执行文件路径（默认 PATH 里的 arm-none-eabi-gdb）")
    ap.add_argument("--server-only", action="store_true", help="只前台起 Server（另开终端连 gdb）")
    a = ap.parse_args()

    if a.detect:
        return cmd_detect()
    exe = server_exe()
    if not exe:
        print("✗ environment-missing：找不到 JLinkGDBServerCL")
        return 2
    if not a.device:
        print("✗ ambiguous-context：必须显式给 --device（芯片型号）")
        return 3

    cmd = server_cmd(exe, a.device, a.interface, a.speed, a.port)
    if a.server_only:
        print("$ " + " ".join(cmd))
        print("· 前台运行：另开终端用 gdb 连 `target extended-remote 127.0.0.1:%d`；Ctrl-C 结束" % a.port)
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass
        return 0

    gdb = gdb_exe(a.gdb)
    if not gdb:
        print("✗ environment-missing：找不到 arm-none-eabi-gdb（用 --gdb 指定）")
        return 2

    print("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_port(a.port):
            print("✗ connection-failure：GDB Server 端口 %d 没起来（探针/目标连不上？）" % a.port)
            return 4
        ex = []
        if a.artifact:
            ex += ["-ex", "file %s" % Path(a.artifact).resolve()]
        ex += ["-ex", "target extended-remote 127.0.0.1:%d" % a.port]
        for c in (a.cmd or ["info registers", "bt"]):
            ex += ["-ex", c]
        ex += ["-ex", "detach"]
        gcmd = [gdb, "-batch", "-q"] + ex
        print("$ " + " ".join(gcmd))
        r = subprocess.run(gcmd, capture_output=True, text=True, timeout=180)
        print(r.stdout)
        if r.stderr.strip():
            print(r.stderr)
        if r.returncode == 0:
            return 0
        if "connection" in (r.stderr + r.stdout).lower():
            return 4
        return 5
    except subprocess.TimeoutExpired:
        print("✗ connection-failure：gdb 超时")
        return 4
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())