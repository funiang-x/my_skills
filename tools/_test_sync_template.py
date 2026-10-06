#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_test_sync_template.py — `tools/sync_template.py` 的自检（**不依赖真实母体**）。

    python tools/_test_sync_template.py

为什么要有它：sync_template 的判据全在"哪些差异算漂移"上，而那些判据**看不出来
对错**——排除项写漏一个，快照就会混进 `build/` 的产物；快照自加文件的名单写漏一个，
`check` 就会永远报一条假漂移。所以这里在临时目录里搭一对**假母体/假快照**，
把每条规则逐条钉住。

⚠️ 全程在 `tempfile` 里造数据，**绝不碰** `templates/stm32-hal/` 真身。
   做法是 import 模块后把它的 `SNAPSHOT` 全局替换成临时目录。

退出码：0 = 全过；1 = 有失败。
"""
from pathlib import Path
import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent

_fails = []
_total = 0


def check(name: str, cond: bool, detail: str = ""):
    global _total
    _total += 1
    print("%s %s%s" % ("✓" if cond else "✗", name, ("  ← " + detail) if (detail and not cond) else ""))
    if not cond:
        _fails.append(name)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "sync_template", REPO / "tools" / "sync_template.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write(root: Path, rel: str, text: str, newline: str = "\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)


def main() -> int:
    st = load_module()
    tmp = Path(tempfile.mkdtemp(prefix="sync_tpl_test_"))
    try:
        mother = tmp / "mother"
        snap = tmp / "snap"
        st.SNAPSHOT = snap                       # ← 只打这一处补丁，CLI 语义不变

        # ── 搭一对初始一致的假母体 / 假快照 ──────────────────────────────
        for r in ("firmware", "docs"):
            (mother / r).mkdir(parents=True, exist_ok=True)
            (snap / r).mkdir(parents=True, exist_ok=True)
        write(mother, "AGENTS.md", "# agents\n")
        write(mother, "firmware/CMakeLists.txt", "project(x)\n")
        write(mother, "firmware/Tools/fw.py", "# fw\n")
        # 快照自加的文件：母体没有，也不算漂移
        write(snap, "NOTICE.md", "# NOTICE\n")
        write(snap, "hardware/.gitkeep", "")
        for rel in ("AGENTS.md", "firmware/CMakeLists.txt", "firmware/Tools/fw.py"):
            write(snap, rel, (mother / rel).read_text(encoding="utf-8"))

        check("初始一致", st.compare(mother, snap) == ([], [], []),
              str(st.compare(mother, snap)))
        check("快照自加文件不算漂移（NOTICE.md / .gitkeep）",
              st.compare(mother, snap)[2] == [])

        # ── 排除项：这些目录在任意层级都不该被看见 ────────────────────────
        for rel in (".git/config", ".ai-skills-state/preflight.json", "_archive/x.md",
                    "_work/y.log", "firmware/build/z.o", "firmware/Tools/__pycache__/a.pyc"):
            write(mother, rel, "x")
        check("排除项不进比对（.git/.ai-skills-state/_archive/_work/build/__pycache__）",
              st.compare(mother, snap) == ([], [], []), str(st.compare(mother, snap)))
        for rel in (".git/config", "_work/y.log", "firmware/build/z.o"):
            write(snap, rel, "x")
        check("排除项在快照侧也不进比对", st.compare(mother, snap) == ([], [], []))

        # ── 三类漂移 ────────────────────────────────────────────────────
        write(mother, "firmware/NEW.c", "new\n")
        check("母体新增 → 报缺失", st.compare(mother, snap)[0] == ["firmware/NEW.c"],
              str(st.compare(mother, snap)[0]))

        write(snap, "AGENTS.md", "# agents CHANGED\n")
        check("内容不同 → 报 differ", st.compare(mother, snap)[1] == ["AGENTS.md"],
              str(st.compare(mother, snap)[1]))

        write(snap, "STRAY.md", "stray\n")
        check("快照多出 → 报 extra", st.compare(mother, snap)[2] == ["STRAY.md"],
              str(st.compare(mother, snap)[2]))

        # ── 行尾归一化：CRLF vs LF 不算内容差异 ──────────────────────────
        write(mother, "firmware/CRLF.txt", "a\nb\nc\n")
        write(snap, "firmware/CRLF.txt", "a\r\nb\r\nc\r\n")
        check("CRLF vs LF 不算漂移",
              st.compare(mother, snap)[1] == ["AGENTS.md"],   # 只有前面那处 AGENTS.md
              str(st.compare(mother, snap)[1]))

        # ── check：有漂移必须退 1 ────────────────────────────────────────
        with contextlib.redirect_stdout(io.StringIO()):
            rc = st.cmd_check(mother)
        check("check 有漂移 → 退 1", rc == 1, "rc=%d" % rc)

        # ── apply：干跑不动盘，--apply 才落地，且落地后自检必须过 ─────────
        before = (snap / "AGENTS.md").read_text(encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            st.cmd_apply(mother, apply=False, prune=False)
        check("干跑不改盘", (snap / "AGENTS.md").read_text(encoding="utf-8") == before)

        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = st.cmd_apply(mother, apply=True, prune=False)
        out = buf.getvalue()
        check("apply --apply → 退 0", rc == 0, "rc=%d" % rc)
        check("apply 后自检行出现", "自检：同步后与母体一致" in out)
        m2, d2, e2 = st.compare(mother, snap)
        check("apply 后内容一致", m2 == [] and d2 == [], "missing=%s differ=%s" % (m2, d2))
        check("未加 --prune 时多余文件保留", e2 == ["STRAY.md"], str(e2))

        with contextlib.redirect_stdout(io.StringIO()):
            rc = st.cmd_apply(mother, apply=True, prune=True)
        check("apply --prune → 退 0", rc == 0, "rc=%d" % rc)
        check("--prune 后完全一致", st.compare(mother, snap) == ([], [], []),
              str(st.compare(mother, snap)))

        # ── 母体路径校验 ────────────────────────────────────────────────
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                st._require_mother(str(tmp / "nope"))
                check("不存在的 --mother 必须拒", False)
            except SystemExit as e:
                check("不存在的 --mother 必须拒", e.code == 2, "code=%s" % e.code)
        plain = tmp / "plain"                        # 存在、但没有 firmware/
        plain.mkdir(exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                st._require_mother(str(plain))
                check("不像母体的 --mother 必须拒", False)
            except SystemExit as e:
                check("不像母体的 --mother 必须拒", e.code == 2, "code=%s" % e.code)
        # 正例：真的母体形状（有 firmware/）必须放行
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                ok = st._require_mother(str(mother)) == mother.resolve()
            except SystemExit:
                ok = False
        check("母体形状正确 → 放行", ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n共 %d 项，失败 %d 项" % (_total, len(_fails)))
    return 1 if _fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
