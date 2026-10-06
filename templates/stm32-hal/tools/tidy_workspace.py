#!/usr/bin/env python3
"""templet 工作区归位器（与 G2026 同款机制，全项目模板版）。

用法: python tools/tidy_workspace.py [--apply]
规则:
  删除: __pycache__/ 与 *.pyc（build/Drivers/Middlewares 除外）；_work/ 内 14 天旧产物
  归档: 工程根 *bak* 散件 → _archive/
  归类: 工程根白名单之外的一切新散件 → _work/root/<类型>/
  白名单: AGENTS.md CLAUDE.md README.md PROJECT.md .gitignore
  冻结区: _archive/（永不动，每次运行重生成 MANIFEST.md）
"""
import re, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GARD = 48 * 3600
WORK_EXPIRE = 14 * 24 * 3600
NOW = time.strftime("%Y%m%d-%H%M")
ROOT_KEEP = {"AGENTS.md", "CLAUDE.md", "README.md", "PROJECT.md", ".gitignore"}


def is_old(p: Path) -> bool:
    return time.time() - p.stat().st_mtime > GARD


def plan():
    moves, deletes = [], []
    for p in ROOT.iterdir():
        if p.name.startswith((".", "_archive", "_work")) or p.name in ROOT_KEEP or not p.is_file():
            continue
        if not is_old(p):
            continue
        if re.search(r"bak", p.name, re.I):
            moves.append((p, ROOT / "_archive" / p.name))
        else:
            ext = p.suffix.lstrip(".") or "misc"
            moves.append((p, ROOT / "_work" / "root" / ext / p.name))
    for cache in ROOT.rglob("__pycache__"):
        parts = set(cache.parts)
        if parts & {".git", "firmware/build", "firmware/Drivers", "firmware/Middlewares", "_archive", "_work", "node_modules"}:
            continue
        if is_old(cache):
            deletes.append(cache)
    work = ROOT / "_work"
    if work.exists():
        for p in work.rglob("*"):
            if not p.is_file() or "tidy-log" in p.parts:
                continue
            if time.time() - p.stat().st_mtime > WORK_EXPIRE:
                deletes.append(p)
    return moves, deletes


def write_manifest():
    arc = ROOT / "_archive"
    if not arc.exists():
        return
    lines = ["# _archive 内容清单", "",
             "> `tools/tidy_workspace.py` 自动生成——勿手编。本目录被 git 忽略：",
             "> `rg` 默认搜不到，搜证据加 `--no-ignore` 或按本清单取。", ""]
    for d in sorted(arc.iterdir()):
        if d.is_dir():
            files = [p for p in d.rglob("*") if p.is_file()]
            size = sum(p.stat().st_size for p in files) / 1e6
            lines.append(f"- `{d.name}/`（{len(files)} 文件 · {size:.1f} MB）")
        else:
            lines.append(f"- `{d.name}`")
    (arc / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(apply: bool):
    moves, deletes = plan()
    print(f"[{'APPLY' if apply else 'DRY-RUN'}] 搬运 {len(moves)} 项，删除 {len(deletes)} 处")
    for src, dst in moves:
        print(f"  搬 {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}")
    for d in deletes:
        print(f"  删 {d.relative_to(ROOT)}{'/' if d.is_dir() else ''}")
    if not apply:
        print("(dry-run，加 --apply 执行)")
        return
    log = []
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        final, i = dst, 1
        while final.exists():
            final = dst.with_name(f"{dst.stem}-{i}{dst.suffix}"); i += 1
        shutil.move(str(src), str(final))
        log.append(f"MOVE {src.relative_to(ROOT)} -> {final.relative_to(ROOT)}")
    for d in deletes:
        if d.is_dir(): shutil.rmtree(d)
        else: d.unlink()
        log.append(f"DELETE {d.relative_to(ROOT)}")
    (ROOT / "_work" / "tidy-log").mkdir(parents=True, exist_ok=True)
    (ROOT / "_work" / "tidy-log" / f"{NOW}.log").write_text("\n".join(log) or "(nothing)", encoding="utf-8")
    write_manifest()
    print(f"完成：搬 {len(moves)}、删 {len(deletes)}；清单 _archive/MANIFEST.md 已更新")


if __name__ == "__main__":
    run("--apply" in sys.argv)
