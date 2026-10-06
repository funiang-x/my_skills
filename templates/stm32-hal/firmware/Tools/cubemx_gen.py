#!/usr/bin/env python3
"""cubemx_gen —— 用 **无头（headless）模式** 让 CubeMX 按 `.ioc` 重新生成代码。

为什么需要它
------------
在 CubeMX 的 GUI 里点 Generate Code 时，只要 `.ioc` 里有**手改过**的外设，
它就会弹一个模态框：

    WARNINGS:
      - Main Config: These peripherals still have some not configured or
        wrong parameter values: [FSMC, I2C1]
    Do you still want to generate code ?   [Yes] [No]

**每次都要人手点一下** —— 自动化跑不动。

无头模式（`STM32CubeMX.exe -q <script>`）**不问这个**，直接生成。
本脚本就是把"写脚本 → 起 CubeMX → 报告"这三步固定下来。

⚠️ 一个实测的坑：**必须让 CubeMX 的 stdout 挂在管道上**。
   把输出直接重定向到文件（`> log 2>&1`）时，启动器会**提前返回**、
   CubeMX 实际上没跑完（现象：命令 1 秒就结束、`Core/` 里文件时间戳没变）。
   本脚本用 `subprocess` + `PIPE`，天然满足这个条件。

⚠️ 生成完**一定要回头核对 `Core/`**！CubeMX 会**静默删掉**它认为不该存在的
   东西 —— 本工程踩过一次：`DMA2_Stream0_IRQHandler()` 被删了
   （ADC/DMA 不在 CubeMX 的 IP 列表里），结果是 DMA 完成中断没人处理。
   ⇒ 本脚本跑完会自动打印一份 `Core/` 的改动摘要，**别跳过不看的**。

⚠️ 它**不检查**参数合法性。想知道 CubeMX 到底在抱怨什么，看
   `~/.stm32cubemx/STM32CubeMX.log` 里的 `OptionalMessage_ERROR` /
   `IP not ready for code generation` 行 —— 那才是逐条原因。

用法
----
    python Tools/cubemx_gen.py            # 重新生成 + 打印 Core/ 改动摘要
    python Tools/cubemx_gen.py --dry-run  # 只打印将要执行的命令

环境变量
--------
    STM32CUBEMX_HOME  CubeMX 安装目录（默认见下面的候选列表）
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ⚠️ .ioc 文件名**自动发现**（工程根下唯一一个 *.ioc）—— 本工具保持工程无关，
#    派生工程零修改可用。多个 .ioc 会直接报错，避免猜错目标。
_iocs = sorted(ROOT.glob("*.ioc"))
if len(_iocs) != 1:
    raise SystemExit(f"!! 工程根应有且仅有一个 .ioc，实际找到 {len(_iocs)} 个："
                     f"{[p.name for p in _iocs]}")
IOC = _iocs[0]
CORE = ROOT / "Core"
CUBEMX_LOG = Path.home() / ".stm32cubemx" / "STM32CubeMX.log"

# CubeMX 的安装位置候选（先看环境变量，再看这几个）
CUBEMX_CANDIDATES = [
    Path(os.environ.get("STM32CUBEMX_HOME", "")) if os.environ.get("STM32CUBEMX_HOME") else None,
    Path.home() / "AppData/Local/Programs/STM32CubeMX",
    Path("C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX"),
    Path("C:/ST/STM32CubeMX"),
    Path("/opt/stm32cubemx"),
    Path("/Applications/STMicroelectronics/STM32CubeMX.app/Contents/MacOs"),
]


def find_cubemx() -> Path:
    for d in CUBEMX_CANDIDATES:
        if d is None:
            continue
        exe = d / ("STM32CubeMX.exe" if os.name == "nt" else "STM32CubeMX")
        if exe.is_file():
            return exe
    raise SystemExit(
        "找不到 STM32CubeMX。设一个环境变量指过去：\n"
        "    STM32CUBEMX_HOME=<CubeMX 安装目录>\n"
        "候选位置：\n  " + "\n  ".join(str(d) for d in CUBEMX_CANDIDATES if d)
    )


def snapshot() -> dict[str, int]:
    """Core/ 下每个文件的 mtime，用来判断"这次生成到底动了哪些文件"。"""
    return {
        str(p.relative_to(ROOT)): p.stat().st_mtime_ns
        for p in CORE.rglob("*")
        if p.is_file()
    }


def report_log_issues() -> None:
    """把 CubeMX 日志里真正的原因挑出来（GUI 那个模态框只说了"哪几个 IP"）。"""
    if not CUBEMX_LOG.is_file():
        return
    pat = re.compile(
        r"OptionalMessage_(ERROR|WARNING).*?- (.*)$"
        r"|IP not ready for code generation: (\S+)",
        re.M,
    )
    hits = pat.findall(CUBEMX_LOG.read_text(encoding="utf-8", errors="replace"))
    if not hits:
        print("  CubeMX 日志：没有参数级告警 ✅")
        return
    print("  CubeMX 日志里仍有的参数告警（这些就是模态框点名的那几个 IP 的原因）：")
    for kind, msg, ip in hits:
        if ip:
            print(f"    [not ready] {ip}")
        else:
            print(f"    [{kind}] {msg}")


def main() -> int:
    ap = argparse.ArgumentParser(description="用无头模式让 CubeMX 重新生成代码")
    ap.add_argument("--dry-run", action="store_true", help="只打印命令，不执行")
    args = ap.parse_args()

    exe = find_cubemx()
    if not IOC.is_file():
        raise SystemExit(f"找不到 {IOC}")

    # 脚本：加载 .ioc → 生成 → 退出。路径用正斜杠，Java 在 Windows 上也认。
    script = f"config load {IOC.as_posix()}\nproject generate\nexit\n"
    print(f"== cubemx_gen ==\n  CubeMX : {exe}\n  .ioc   : {IOC}")

    if args.dry_run:
        print("  script :\n" + "\n".join("    " + s for s in script.splitlines()))
        return 0

    before = snapshot()

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name

    try:
        # ⚠️ stdout 必须是 PIPE（见文件头：重定向到文件会让启动器提前返回）
        proc = subprocess.run(
            [str(exe), "-q", script_path],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        os.unlink(script_path)

    tail = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()][-3:]
    print(f"  退出码 : {proc.returncode}")
    for ln in tail:
        print(f"  {ln}")

    after = snapshot()
    changed = sorted(k for k in after if before.get(k) != after[k])
    removed = sorted(k for k in before if k not in after)
    print(f"  Core/ 改动：{len(changed)} 个文件被重写" + (f"，{len(removed)} 个被删除" if removed else ""))
    for k in changed:
        print(f"    M {k}")
    for k in removed:
        print(f"    D {k}")

    print("\n  ⚠️ 逐条看上面的改动：CubeMX 会**静默删掉**它认为不该存在的东西")
    print("     （本工程踩过：DMA2_Stream0_IRQHandler 被删 ⇒ 采样完成中断没人处理）。")
    print("     删掉的是手写逻辑就补回去（USER CODE 段不会被删）。")
    report_log_issues()
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
