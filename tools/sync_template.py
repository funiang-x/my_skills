#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_template — 模板快照同步：母体工程 → `templates/stm32-hal/`

  check : 只读比对（默认动作）——列出快照与母体不一致的文件
  apply : 把母体的改动同步进快照（`--apply`；`--prune` 才删"快照多出来的"）

为什么需要它
    本库携带的 `templates/stm32-hal/` 是**某个母体工程在某个时刻的快照**
    （见 `templates/stm32-hal/NOTICE.md`）。母体继续演进、快照就会悄悄变旧，
    而"快照旧了"**没有任何报错** —— 2026-10-06 就是这么漏的：母体修了根目录
    `.vscode/` 的路径，快照还是旧版，靠人肉 `diff -rq` 才发现。
    ⇒ 把"比对"变成一条命令，改完母体就跑一次。

约定
    · 默认**干跑**（只打印计划），`--apply` 才真正写；
    · 母体路径**必须显式传** `--mother` —— 它是本机路径，按 `ROUTE.md` §2.8 的
      规矩不许写死在库里（写死 = 换台机器就指空，且没有任何报错）；
    · 快照 = 母体 **去掉**排除项 + **保留**本库自加的文件（`NOTICE.md` / `.gitkeep`）；
    · 只比对**文件**，不比对目录 —— 与 git 同口径（空目录本来就存不进仓库）。

用法
    python tools/sync_template.py check --mother ~/Desktop/Project/projects/templet
    python tools/sync_template.py apply --mother <母体路径> --apply
    python tools/sync_template.py apply --mother <母体路径> --apply --prune
"""
from pathlib import Path
import argparse
import filecmp
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                               # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()
SNAPSHOT = REPO / "templates" / "stm32-hal"

# ── 排除项：母体里有、但**不进快照**的 ────────────────────────────────────────
# 按**目录名**匹配任意层级（`firmware/build/...` 与 `firmware/Tools/__pycache__/...`
# 都要排除），所以给的是名字而不是路径。
EXCLUDE_DIRS = {
    ".git",             # 母体的版本库
    ".ai-skills-state", # 门禁开工证（本机状态）
    "_archive",         # 历史证据区（母体自己的归档）
    "_work",            # AI 会话临时产物
    "build",            # 构建产物
    "__pycache__",      # Python 字节码
}

# ── 本库**自加**的文件：母体里没有，但不算漂移 ────────────────────────────────
SNAPSHOT_ONLY = {
    "NOTICE.md",        # 快照出处与派生方式说明（本库自己写的）
}
# 占位文件：空目录在 git 里存不住，用 .gitkeep 占位（任意层级都算）
SNAPSHOT_ONLY_NAMES = {".gitkeep"}


def disp(p: Path) -> str:
    s = str(p)
    try:
        return "~" + s[len(str(HOME)):] if s.startswith(str(HOME)) else s
    except Exception:                                            # noqa: BLE001
        return s


def walk_files(root: Path) -> dict:
    """{相对路径(posix): 绝对 Path}。排除项按**目录名**在任意层级生效。"""
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        out[rel.as_posix()] = p
    return out


def same_file(a: Path, b: Path) -> bool:
    """字节相同；**文本文件按归一化后的行尾比**。

    为什么要归一化：两个仓库的 `core.autocrlf` / `.gitattributes` 可能不同，
    checkout 出来的行尾一个 CRLF 一个 LF —— 那种差异**不是内容差异**，
    按字节比会报一屏假漂移。
    """
    try:
        if filecmp.cmp(str(a), str(b), shallow=False):
            return True
    except OSError:
        return False
    try:
        ta = a.read_text(encoding="utf-8")
        tb = b.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False            # 二进制且字节不同 ⇒ 真的不同
    return ta.replace("\r\n", "\n") == tb.replace("\r\n", "\n")


def is_snapshot_only(rel: str) -> bool:
    name = Path(rel).name
    return rel in SNAPSHOT_ONLY or name in SNAPSHOT_ONLY_NAMES


def compare(mother: Path, snap: Path):
    """→ (缺失, 内容不同, 快照多余)。三个 list 都是相对路径字符串。"""
    m, s = walk_files(mother), walk_files(snap)
    missing = sorted(set(m) - set(s))
    extra = sorted(k for k in set(s) - set(m) if not is_snapshot_only(k))
    differ = sorted(k for k in set(m) & set(s) if not same_file(m[k], s[k]))
    return missing, differ, extra


def _require_mother(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        print("✗ --mother 不是目录：%s" % disp(p))
        print("  母体路径必须显式给，且库里**不写死**它（ROUTE.md §2.8）。")
        raise SystemExit(2)
    if not (p / "firmware").is_dir():
        print("✗ --mother 看着不像模板母体（没有 firmware/ 子目录）：%s" % disp(p))
        raise SystemExit(2)
    return p


def cmd_check(mother: Path) -> int:
    print("== sync_template check ==")
    print("  母体    %s" % disp(mother))
    print("  快照    %s" % disp(SNAPSHOT))
    missing, differ, extra = compare(mother, SNAPSHOT)
    total = len(missing) + len(differ) + len(extra)
    if not total:
        print("\n✓ 快照与母体一致（%d 个文件）" % len(walk_files(SNAPSHOT)))
        print("EXIT: 0")
        return 0
    print("\n✗ 快照落后于母体，%d 处不一致：" % total)
    if missing:
        print("  母体有、快照没有（%d）：" % len(missing))
        for k in missing[:20]:
            print("    + %s" % k)
    if differ:
        print("  内容不同（%d）：" % len(differ))
        for k in differ[:20]:
            print("    ~ %s" % k)
    if extra:
        print("  快照有、母体没有（%d）—— 母体删过？确认后加 --prune：" % len(extra))
        for k in extra[:20]:
            print("    - %s" % k)
    print("\n修法：python tools/sync_template.py apply --mother %s --apply" % disp(mother))
    print("EXIT: 1")
    return 1


def cmd_apply(mother: Path, apply: bool, prune: bool) -> int:
    print("== sync_template apply%s ==" % ("" if apply else "（干跑，加 --apply 才落地）"))
    print("  母体    %s" % disp(mother))
    print("  快照    %s" % disp(SNAPSHOT))
    missing, differ, extra = compare(mother, SNAPSHOT)

    todo = missing + differ
    if todo:
        print("\n将复制 %d 个文件（母体 → 快照）：" % len(todo))
        for k in todo[:30]:
            print("  %s %s" % ("+" if k in missing else "~", k))
        if len(todo) > 30:
            print("  … 其余 %d 个略" % (len(todo) - 30))
    else:
        print("\n没有要复制的文件。")

    if extra:
        print("\n快照多出 %d 个文件（母体已没有）：" % len(extra))
        for k in extra[:20]:
            print("  - %s" % k)
        if not prune:
            print("  ⇒ 默认**不删**。确认这些是母体删掉的，再加 --prune。")

    if not todo and not (extra and prune):
        print("\n✓ 已是最新，无操作")
        print("EXIT: 0")
        return 0

    if not apply:
        print("\n（干跑结束；加 --apply 落地）")
        print("EXIT: 0")
        return 0

    n = 0
    for k in todo:
        dst = SNAPSHOT / k
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mother / k, dst)
        n += 1
    if extra and prune:
        for k in extra:
            (SNAPSHOT / k).unlink()
            n += 1
    print("\n✓ 已同步：复制 %d 个、删除 %d 个"
          % (len(todo), len(extra) if prune else 0))

    # 同步完立刻自证一遍 —— "写完了" 与 "真的同步了" 是两件事
    m2, d2, e2 = compare(mother, SNAPSHOT)
    if m2 or d2 or (e2 and prune):
        print("✗ 同步后仍有 %d 处不一致 —— 别急着提交，先看："
              % (len(m2) + len(d2) + len(e2)))
        for k in (m2 + d2 + e2)[:10]:
            print("    %s" % k)
        print("EXIT: 1")
        return 1
    print("  自检：同步后与母体一致 ✓（共 %d 个文件）" % len(walk_files(SNAPSHOT)))
    print("EXIT: 0")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="sync_template",
        description="模板快照同步：母体工程 → templates/stm32-hal/"
                    "（check 只比对 / apply 同步）")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, help_ in (("check", "只读比对：列出快照与母体不一致的文件"),
                        ("apply", "把母体的改动同步进快照（默认干跑）")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--mother", required=True,
                        help="模板母体工程根（含 firmware/ 的那个目录）—— "
                             "本机路径，库内不写死")
        if name == "apply":
            sp.add_argument("--apply", action="store_true", help="真正落地（默认干跑）")
            sp.add_argument("--prune", action="store_true",
                            help="同时删除「快照多出来的」文件（母体已删的）")
    args = ap.parse_args()
    mother = _require_mother(args.mother)
    if args.command == "check":
        return cmd_check(mother)
    return cmd_apply(mother, args.apply, args.prune)


if __name__ == "__main__":
    raise SystemExit(main())
