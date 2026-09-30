#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shell_proxy.py — serial-shell skill 的执行入口（依赖 pyserial）。

用法：
    python shell_proxy.py --port COM7 --send "help"
    python shell_proxy.py --port COM7 --script cmds.txt
    python shell_proxy.py --port COM7 --interactive
退出码：0=成功 2=环境缺失(无 pyserial) 3=参数问题 4=连接失败
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

try:
    import serial
except ImportError:                                              # pragma: no cover
    serial = None

EOLS = {"crlf": "\r\n", "lf": "\n", "cr": "\r", "none": ""}


def need_pyserial():
    if serial is None:
        print("✗ environment-missing：缺 pyserial。装法：`pip install pyserial`")
        return True
    return False


def drain(ser, settle, budget):
    """读到「连续 settle 秒没有新行」为止；budget 是总上限秒。"""
    out, end, last = [], time.time() + budget, time.time()
    while time.time() < end:
        raw = ser.readline()
        if raw:
            out.append(raw.decode("utf-8", "replace").rstrip("\r\n"))
            last = time.time()
        elif (time.time() - last) >= settle:
            break
    return out


def send_one(ser, line, eol):
    print("> " + line)
    ser.write((line + eol).encode("utf-8"))
    ser.flush()


def main():
    ap = argparse.ArgumentParser(description="串口交互 shell（serial-shell skill）")
    ap.add_argument("--port", help="串口，如 COM7 / /dev/ttyUSB0（必填）")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--eol", choices=sorted(EOLS), default="crlf", help="行尾符，默认 crlf")
    ap.add_argument("--timeout", type=float, default=1.0, help="每条命令后的静默判定秒数")
    ap.add_argument("--budget", type=float, default=10.0, help="单条命令响应的最长等待秒数")
    ap.add_argument("--send", help="发送一行并打印响应")
    ap.add_argument("--script", help="逐行发送文件内容（空行与 # 开头跳过）")
    ap.add_argument("--interactive", action="store_true", help="交互模式：输入一行发一行")
    a = ap.parse_args()

    if not a.port:
        print("✗ 参数问题：必须给 --port（先跑 serial-monitor --list 看有哪些口）")
        return 3
    if not (a.send or a.script or a.interactive):
        print("✗ 参数问题：--send / --script / --interactive 选一个")
        return 3
    if need_pyserial():
        return 2
    try:
        ser = serial.Serial(a.port, a.baud, timeout=0.2)
    except Exception as e:                                       # noqa: BLE001
        print("✗ connection-failure：打不开 %s（%s）" % (a.port, e))
        return 4

    eol = EOLS[a.eol]
    try:
        if a.send:
            send_one(ser, a.send, eol)
            print("\n".join(drain(ser, a.timeout, a.budget)))
            return 0
        if a.script:
            lines = [ln.strip() for ln in Path(a.script).read_text(encoding="utf-8").splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
            for ln in lines:
                send_one(ser, ln, eol)
                for out in drain(ser, a.timeout, a.budget):
                    print(out)
            return 0
        print("· 交互模式：输入即发；Ctrl-C / Ctrl-D 退出")
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not line.strip():
                continue
            send_one(ser, line, eol)
            for out in drain(ser, a.timeout, a.budget):
                print(out)
    finally:
        ser.close()


if __name__ == "__main__":
    sys.exit(main())