#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jlink_flasher.py — flash-jlink skill 的执行入口（纯标准库）。

用法：
    python jlink_flasher.py --detect
    python jlink_flasher.py --artifact build/Debug/app.elf --device STM32F407VG
    python jlink_flasher.py --artifact app.bin --base-address 0x08000000 --device STM32F407VG
    python jlink_flasher.py --rtt --device STM32F407VG --duration 10 --output rtt.log
退出码：0=成功 2=环境缺失 3=参数/产物问题 4=连接失败 5=目标响应异常
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

ART_RANK = {".elf": 0, ".axf": 0, ".hex": 1, ".bin": 2}
ERR_CONNECT = ("cannot connect", "could not connect", "failed to connect",
               "no emulator", "emulator not found", "cannot find j-link",
               "no j-link")
ERR_OTHER = ("error", "failed", "cannot find", "not found", "not supported")
OK_MARKS = ("o.k.", "script processing completed", "downloading file", "verifying")


def find_tool(*names):
    """在 JLINK_DIR / JLINK_PATH、PATH、默认安装目录里找工具 → Path | None。"""
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


def commander_exe():
    return find_tool("JLink.exe", "JLinkExe")


def rtt_logger_exe():
    return find_tool("JLinkRTTLogger.exe", "JLinkRTTLogger")


def classify(out: str) -> int:
    low = out.lower()
    if any(m in low for m in ERR_CONNECT):
        return 4
    if any(m in low for m in ERR_OTHER):
        return 5
    if any(m in low for m in OK_MARKS):
        return 0
    return 5          # 既无成功标记也无已知错误：交给人看原始输出


def cmd_detect():
    exe = commander_exe()
    if not exe:
        print("✗ environment-missing：找不到 JLink.exe / JLinkExe")
        print("  可用环境变量 JLINK_DIR 指向安装目录（如 "
              r"C:\Program Files\SEGGER\JLink_V936" "）")
        return 2
    print("✓ J-Link 工具：%s" % exe)
    rtt = rtt_logger_exe()
    print("%s RTT 日志工具：%s" % ("✓" if rtt else "·", rtt or "未找到（--rtt 不可用）"))
    with tempfile.NamedTemporaryFile("w", suffix=".jlink", delete=False,
                                     encoding="utf-8") as f:
        f.write("ShowEmuList\nqc\n")
        script = f.name
    try:
        r = subprocess.run([str(exe), "-CommanderScript", script],
                           capture_output=True, text=True, timeout=90)
        out = (r.stdout or "") + (r.stderr or "")
        print("探针列表（ShowEmuList）：")
        tail = [ln for ln in out.splitlines() if ln.strip()][-25:]
        print("\n".join("  " + ln for ln in tail) or "  （无输出）")
    except subprocess.TimeoutExpired:
        print("· 探测超时——探针可能未插好")
    finally:
        Path(script).unlink(missing_ok=True)
    return 0


def cmd_flash(a):
    exe = commander_exe()
    if not exe:
        print("✗ environment-missing：找不到 JLink.exe / JLinkExe")
        return 2
    if not a.device:
        print("✗ ambiguous-context：必须显式给 --device（芯片型号，如 STM32F407VG）")
        return 3

    art = Path(a.artifact)
    if art.is_dir():
        cands = sorted((p for p in art.rglob("*")
                        if p.is_file() and p.suffix.lower() in ART_RANK),
                       key=lambda p: (ART_RANK[p.suffix.lower()], -p.stat().st_mtime))
        if not cands:
            print("✗ artifact-missing：%s 下没有 ELF/HEX/BIN" % art)
            return 3
        art = cands[0]
        print("· 自动选择产物：%s" % art)
    art = art.resolve()
    if not art.is_file():
        print("✗ artifact-missing：%s 不存在" % art)
        return 3
    if art.suffix.lower() == ".bin" and not a.base_address:
        print("✗ artifact-missing：BIN 必须给 --base-address（如 0x08000000）")
        return 3

    lines = ["r"]
    if art.suffix.lower() == ".bin":
        lines.append('loadfile "%s" %s' % (art, a.base_address))
    else:
        lines.append('loadfile "%s"' % art)
    lines += ["verify", "r", "g", "qc"]
    with tempfile.NamedTemporaryFile("w", suffix=".jlink", delete=False,
                                     encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
        script = f.name
    print("J-Link 脚本：")
    print("\n".join("  " + ln for ln in lines))
    cmd = [str(exe), "-device", a.device, "-if", a.interface,
           "-speed", str(a.speed), "-autoconnect", "1",
           "-CommanderScript", script]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        print("✗ connection-failure：烧录超时（180s）")
        return 4
    finally:
        Path(script).unlink(missing_ok=True)

    print("\n--- J-Link 输出（尾部 25 行）---")
    print("\n".join(out.strip().splitlines()[-25:]) or "（无输出）")
    code = classify(out)
    label = {0: "✓ 成功（含校验）", 4: "✗ connection-failure",
             5: "✗ target-response-abnormal"}.get(code, "?")
    print("\n结果：%s（退出码 %d）" % (label, code))
    if code == 0:
        print("→ 看日志：serial-monitor 或 --rtt；GDB：debug-jlink")
    return code


def cmd_rtt(a):
    tool = rtt_logger_exe()
    if not tool:
        print("✗ environment-missing：找不到 JLinkRTTLogger（随 J-Link 工具包安装）")
        return 2
    if not a.device:
        print("✗ ambiguous-context：--rtt 也需要 --device")
        return 3
    out_path = Path(a.output or ("rtt-%s.log" % time.strftime("%Y%m%d-%H%M%S")))
    cmd = [str(tool), "-Device", a.device, "-If", a.interface,
           "-Speed", str(a.speed), "-RTTChannel", str(a.rtt_channel), str(out_path)]
    print("$ " + " ".join(cmd))
    if a.duration:
        try:
            subprocess.run(cmd, timeout=a.duration)
        except subprocess.TimeoutExpired:
            print("· 已达 --duration %ss，停止抓取" % a.duration)
    else:
        print("· 未给 --duration：Ctrl-C 结束")
        subprocess.run(cmd)
    if out_path.is_file():
        text = out_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        print("✓ RTT 日志：%s（%d 行）" % (out_path, len(lines)))
        print("\n".join("  " + ln for ln in lines[-15:]))
        return 0
    print("✗ target-response-abnormal：没有生成日志文件（RTT 通道没启用？）")
    return 5


def main():
    ap = argparse.ArgumentParser(description="J-Link 烧录 / 校验 / RTT（flash-jlink skill）")
    ap.add_argument("--detect", action="store_true", help="探测工具与探针后退出")
    ap.add_argument("--artifact", help="ELF/HEX/BIN 产物路径（给目录则自动挑）")
    ap.add_argument("--device", help="芯片型号，如 STM32F407VG（必填）")
    ap.add_argument("--interface", default="SWD", choices=["SWD", "JTAG"])
    ap.add_argument("--speed", type=int, default=4000, help="kHz，默认 4000")
    ap.add_argument("--base-address", help="BIN 的烧录基地址，如 0x08000000")
    ap.add_argument("--rtt", action="store_true", help="抓 RTT 日志（不烧录）")
    ap.add_argument("--rtt-channel", type=int, default=0)
    ap.add_argument("--duration", type=int, help="RTT 抓取秒数（不给则 Ctrl-C 结束）")
    ap.add_argument("--output", help="RTT 日志文件路径")
    a = ap.parse_args()

    if a.detect:
        return cmd_detect()
    if a.rtt:
        return cmd_rtt(a)
    if not a.artifact:
        print("✗ artifact-missing：给 --artifact（或 --detect / --rtt）")
        return 3
    return cmd_flash(a)


if __name__ == "__main__":
    sys.exit(main())