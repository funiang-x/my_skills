#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serial_monitor.py — serial-monitor skill 的执行入口（依赖 pyserial，可选安装）。

用法：
    python serial_monitor.py --list
    python serial_monitor.py --auto --duration 10
    python serial_monitor.py --port COM7 --baud 115200 --wait "boot ok" --timeout 20
    python serial_monitor.py --port COM7 --monitor --timestamp --save run.log
退出码：0=成功 2=环境缺失(无 pyserial) 3=端口不确定/参数问题 4=连接失败 5=等待超时
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
    from serial.tools import list_ports
except ImportError:                                              # pragma: no cover
    serial = None
    list_ports = None

# 常见 USB 转串口 / 调试器虚拟串口
PREFERRED = ("ch340", "cp210", "stlink", "st-link", "cmsis-dap",
             "usb serial", "ft232", "ftdi", "silicon labs", "prolific")
KEYWORDS = ("error", "fail", "assert", "hardfault", "hard fault", "fault",
            "warn", "reset", "boot", "错误", "失败", "断言", "重启")


def need_pyserial():
    if serial is None:
        print("✗ environment-missing：缺 pyserial。装法：`pip install pyserial`")
        print("  临时替代：用系统串口工具（Windows: PuTTY / 串口调试助手；"
              "Linux: `screen /dev/ttyUSB0 115200`）")
        return True
    return False


def cmd_list():
    for p in sorted(list_ports.comports(), key=lambda p: p.device):
        print("  %-8s %s  [%s]" % (p.device, p.description or "", p.hwid or ""))
    return 0


def pick_port():
    ports = list(list_ports.comports())
    if not ports:
        print("✗ connection-failure：一个串口都没找到（线插了？驱动装了？）")
        return None
    pref = [p for p in ports
            if any(k in ((p.description or "") + " " + (p.hwid or "")).lower()
                   for k in PREFERRED)]
    if len(pref) == 1:
        print("· 自动选择：%s（%s）" % (pref[0].device, pref[0].description or ""))
        return pref[0].device
    if len(ports) == 1:
        print("· 自动选择：%s（%s）" % (ports[0].device, ports[0].description or ""))
        return ports[0].device
    print("✗ ambiguous-context：多个候选，请显式 --port：")
    for p in ports:
        print("    %-8s %s  [%s]" % (p.device, p.description or "", p.hwid or ""))
    return None


def cmd_monitor(a):
    port = a.port or pick_port()
    if not port:
        return 3
    try:
        ser = serial.Serial(port, a.baud, timeout=0.2)
    except Exception as e:                                       # noqa: BLE001
        print("✗ connection-failure：打不开 %s（%s）" % (port, e))
        return 4

    start = time.time()
    end = start + a.duration if a.duration else None
    wait_end = start + a.timeout if a.wait else None
    hits = {k: 0 for k in KEYWORDS}
    n = 0
    sink = open(a.save, "a", encoding="utf-8") if a.save else None
    mode = ("抓 %ss" % a.duration if a.duration
            else ("等 %r（最多 %ss）" % (a.wait, a.timeout) if a.wait else "持续监听"))
    print("▶ %s @ %d（%s）—— Ctrl-C 结束" % (port, a.baud, mode))
    try:
        while True:
            if end and time.time() > end:
                break
            if wait_end and time.time() > wait_end:
                print("\n✗ 等待超时：没等到 %r" % a.wait)
                return 5
            raw = ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not text:
                continue
            n += 1
            print(("[%s] " % time.strftime("%H:%M:%S")) + text if a.timestamp else text,
                  flush=True)
            if sink:
                sink.write(text + "\n")
                sink.flush()
            low = text.lower()
            for k in KEYWORDS:
                if k in low:
                    hits[k] += 1
            if a.wait and a.wait in text:
                print("✓ 命中等待字符串 %r" % a.wait)
                return 0
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        if sink:
            sink.close()

    print("\n—— 摘要 ——")
    print("  行数 %d ｜ 时长 %.1fs ｜ 端口 %s @ %d" % (n, time.time() - start, port, a.baud))
    hot = {k: v for k, v in hits.items() if v}
    print("  关键词命中：%s" % (", ".join("%s×%d" % kv for kv in hot.items()) or "无"))
    if a.save:
        print("  已存盘：%s" % a.save)
    return 0


def main():
    ap = argparse.ArgumentParser(description="串口日志抓取 / 等待 / 监控（serial-monitor skill）")
    ap.add_argument("--list", action="store_true", help="列串口后退出")
    ap.add_argument("--auto", action="store_true", help="自动挑串口（按常见 USB 串口芯片）")
    ap.add_argument("--port", help="显式串口，如 COM7 / /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--duration", type=int, help="抓 N 秒后停")
    ap.add_argument("--wait", help="等到出现该字符串即停")
    ap.add_argument("--timeout", type=int, default=30, help="--wait 的最长等待秒数（默认 30）")
    ap.add_argument("--monitor", action="store_true", help="持续监听直到 Ctrl-C")
    ap.add_argument("--timestamp", action="store_true", help="每行加时间戳")
    ap.add_argument("--save", help="同时存到文件（追加）")
    a = ap.parse_args()

    if need_pyserial():
        return 2
    if a.list:
        return cmd_list()
    if not (a.port or a.auto or a.duration or a.wait or a.monitor):
        print("· 没给动作：--list / --auto / --duration / --wait / --monitor 选一个")
        return 3
    return cmd_monitor(a)


if __name__ == "__main__":
    sys.exit(main())