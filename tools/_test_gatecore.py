#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_test_gatecore.py — 闸门**判定核心**的回归测试（只读，不改任何东西）。

为什么要有它：2026-09-30 之前，"只读命令被误拦"这个 bug **复发过 4 次** ——
3 次靠加词边界修（`jlink` / `easyeda` 的裸子串误伤），1 次靠换判据（`st-flash`
是独立词，词边界治不了）。**每次修完都没有东西保证它不再回来。**

用法：
    python tools/_test_gatecore.py                       # 测本库（公开层）
    python tools/_test_gatecore.py --host <工作台根目录>   # 顺带测某个宿主工作台的 ops.json 与钩子
    python tools/_test_gatecore.py --host ~/Desktop/Project/workbench

退出码：0 = 全过；1 = 有失败（据此判断判据是不是被改坏了）。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent
CORE = REPO / "tools" / "_gatecore.py"
HOOK = REPO / "hooks" / "skill_gate.py"

spec = importlib.util.spec_from_file_location("_gatecore", CORE)
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

fails = []


def check(label, cond, detail=""):
    print("  %s %s%s" % ("[✓]" if cond else "[✗]", label,
                         ("  " + detail) if detail else ""))
    if not cond:
        fails.append(label)


def unit(label, cmd, ops, want_hit):
    zones = G.hit_zones(ops, "cmd", cmd, False)
    check(label, bool(zones) == want_hit, "命中 %d" % len(zones))


def e2e(label, hook, payload, want_rc):
    p = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    check(label, p.returncode == want_rc, "rc=%d 期望 %d" % (p.returncode, want_rc))


def path_case(label, ops, base, p, want_hit):
    key, inb = G.norm(str(p), base)
    zones = G.hit_zones(ops, "path", key, inb)
    check(label, bool(zones) == want_hit, "命中 %d" % len(zones))


def command_suite(tag, ops):
    """命令判定 —— **两个宿主都必须过**（判据与 ops.json 无关）。"""
    print("\n=== %s：命令判定 ===" % tag)
    # 这几条是**误拦的回归防线**：只读搜索绝不能再命中
    unit("只读搜索含设备工具名（旧判据误拦的那种）",
         "grep -oE 'arm-none-eabi|st-flash|JLink' f.txt", ops, False)
    unit("只读搜索提到脚本名（不算执行）",
         'grep -n "eda_sch.py" x.md', ops, False)
    unit("管道：argv0 是 grep",
         "cat a.txt | grep eda_sch.py", ops, False)
    unit("python -c 内联代码不算执行脚本",
         'python -c "import eda_sch"', ops, False)
    # 真执行必须命中
    unit("真执行受管脚本（python 后第一个参数）",
         "python some/dir/eda_sch.py nc", ops, True)
    unit("带版本的解释器 python3.13",
         "python3.13 some/dir/eda_sch.py drc", ops, True)
    unit("按 && 拆段后取第二段（要测的是拆段，故用两边都登记的脚本）",
         "cd some/dir && python some/eda_sch.py nc", ops, True)
    # 设备动作已移出判定范围（拍板 D3）
    unit("设备动作不在任何 zone 里（拍板 D3）",
         "JLinkExe -device STM32F407", ops, False)
    unit("设备动作 st-flash 不在任何 zone 里（拍板 D3）",
         "st-flash write fw.bin 0x8000000", ops, False)


def hook_suite(tag, hook):
    if not (hook and hook.is_file()):
        return
    print("\n=== %s：端到端（喂 stdin JSON）===" % tag)
    e2e("只读 grep 含设备工具名 ⇒ 放行", hook,
        {"tool_name": "Bash",
         "tool_input": {"command": "grep -oE 'a|st-flash|b' f.txt"}}, 0)
    e2e("设备命令 ⇒ 放行（D3）", hook,
        {"tool_name": "Bash",
         "tool_input": {"command": "JLinkExe -device STM32F407"}}, 0)


print("闸门判定核心 回归测试")

# ---- 本库（公开层）：ops.json 只有 `repo:**` 一条 path 规则，所以路径用例只测"仓内 vs 仓外" ----
SK_OPS = json.loads((REPO / "tools" / "ops.json").read_text(encoding="utf-8"))
command_suite("本库", SK_OPS)
print("\n=== 本库：路径判定 ===")
path_case("仓内文件 ⇒ 命中 repo:**", SK_OPS, REPO, REPO / "ROUTE.md", True)
path_case("仓外文件 ⇒ 不命中", SK_OPS, REPO, Path.home() / "nowhere-outside/x.txt", False)
hook_suite("本库", HOOK)

# ---- 可选：宿主工作台（不在本仓，故用 --host 显式传入）----
host = None
if "--host" in sys.argv:
    i = sys.argv.index("--host")
    if i + 1 < len(sys.argv):
        host = Path(sys.argv[i + 1]).expanduser().resolve()
if host and (host / "tools" / "ops.json").is_file():
    H_OPS = json.loads((host / "tools" / "ops.json").read_text(encoding="utf-8"))
    tag = "宿主 %s" % host.name
    command_suite(tag, H_OPS)
    print("\n=== %s：路径判定 ===" % tag)
    for rel, want in (("products/P/hardware/a.kicad_sch", True),
                      ("products/P/firmware/main.c", True),
                      ("workbench/00_总纲.md", True),
                      ("_review-bak/x.md", False)):
        path_case(rel, H_OPS, host.parent, host.parent / rel, want)
    hook_suite(tag, host / "hooks" / "workbench_gate.py")

print("\n=== 结果 ===")
if fails:
    print("FAIL %d 项：%s" % (len(fails), "；".join(fails)))
    raise SystemExit(1)
print("全部通过")
