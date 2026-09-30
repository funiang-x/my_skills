#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skillman — 本库管理三命令：install / sync / doctor

  install : 探测本机已装的 AI 客户端 → 把它们的 skills 目录接到本库 → 装全局门 → 报告
  sync    : git pull（可选）→ 重挂各端 → 体检
  doctor  : 只读体检（接线 / skill 可调用性 / 路由一致性 / 全局门）

约定：
  · **默认干跑**（只打印计划），`--apply` 才真正落地；
  · 只处理**探测到**的客户端目录，不碰你没装的东西；
  · 写全局门文件前先备份（`.bak-<日期>`），写入用标记块（幂等，可安全重跑）。

Windows 用 Junction（`mklink /J`，免管理员）；macOS / Linux 用 symlink。
"""
from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                               # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()

# ── 已知客户端（探测目录存在才处理）─────────────────────────────────────────
# (名称, skills 目录, 接法, 探测依据目录)
CLIENTS = [
    ("ZCode",        "~/.zcode/skills",               "junction", "~/.zcode"),
    ("WorkBuddy",    "~/.workbuddy/skills",           "junction", "~/.workbuddy"),
    ("WorkBuddy AI", "~/.workbuddy-ai/skills",        "junction", "~/.workbuddy-ai"),
    ("CodeBuddy",    "~/.codebuddy/skills",           "junction", "~/.codebuddy"),
    ("CodeBuddy CN", "~/.codebuddycn/skills",         "junction", "~/.codebuddycn"),
    ("Trae CN",      "~/.trae-cn/skills",             "junction", "~/.trae-cn"),
    ("Doubao",       "~/Doubao/skills",               "junction", "~/Doubao"),
    ("Codex",        "~/.codex/skills",               "per-item", "~/.codex"),
    ("FittenCode",   "~/.fittencode/skills/external", "per-item", "~/.fittencode"),
    ("Marvis",       "~/.marvis/skills/custom",       "per-item", "~/.marvis"),
]

# 全局门候选位置（**只写已存在的文件**，绝不创建；找不到就提示按 templates/global-door.md 手工放置）
# 说明：`~/.workbuddy/MEMORY.md` 等是实测存在的"跨项目记忆"载体（2026-09-30 探明）；
# `~/AGENTS.md` 一类是通用约定位置，存在才写。
GLOBAL_DOORS = [
    "~/AGENTS.md",
    "~/CLAUDE.md",
    "~/.claude/CLAUDE.md",
    "~/.codebuddy/AGENTS.md",
    "~/.codex/AGENTS.md",
    "~/.workbuddy/MEMORY.md",
    "~/.workbuddy-ai/MEMORY.md",
    "~/.trae-cn/memory/user_profile.md",
    "~/.qoder/memory/MEMORY.md",
]

MARK_BEGIN = "<!-- my_skills:global-door -->"
MARK_END = "<!-- /my_skills:global-door -->"

PROBE = "ponytail"          # 接线探针 skill（本库必有）


def disp(p) -> str:
    s = str(p)
    try:
        return "~" + s[len(str(HOME)):] if s.startswith(str(HOME)) else s
    except Exception:                                            # noqa: BLE001
        return s


def skills_on_disk():
    """本库全部 skill（一级目录 + 有 SKILL.md）。"""
    return sorted(d.name for d in REPO.iterdir()
                  if d.is_dir() and (d / "SKILL.md").is_file())


def is_link_like(p: Path) -> bool:
    """符号链接 / Windows Junction 判定（注意：Path.is_symlink 对 junction 返回 False）。"""
    try:
        if p.is_symlink():
            return True
    except OSError:
        pass
    try:
        if hasattr(os.path, "isjunction") and os.path.isjunction(str(p)):
            return True
    except OSError:
        pass
    if os.name == "nt":
        try:
            import stat as _stat
            tag = getattr(os.lstat(str(p)), "st_reparse_tag", 0)
            if tag and tag == getattr(_stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003):
                return True
        except OSError:
            pass
    return False


def link_target(p: Path):
    """是链接 / Junction 返回目标字符串（去掉 \\\\?\\ 前缀），否则 None。"""
    if not is_link_like(p):
        return None
    try:
        t = os.readlink(str(p))
    except OSError:
        return None
    if t.startswith("\\\\?\\"):
        t = t[4:]
    return t


def make_link(link: Path, target: Path) -> bool:
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True, text=True)
        return r.returncode == 0
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except OSError:
        return False


def stale_links(sd: Path, names) -> list:
    """端目录里「指向本库、但本库已无该目录」的链接名 —— 退库后没清的悬空 Junction。

    只认这一类：指向别处的链接、以 `.` 开头的客户端机制目录（`.system` / `.default`）、
    以及实体目录一律不碰。本库基础设施（tools/hooks/templates/.state）没有 SKILL.md，
    本就不在 `names` 里，不会被误判。
    """
    out = []
    if not sd.is_dir():
        return out
    for child in sorted(sd.iterdir()):
        if child.name in names or child.name.startswith("."):
            continue
        t = link_target(child)
        if t is None:
            continue
        try:
            tp = Path(t)
            if tp.parent.resolve() == REPO.resolve() and not tp.exists():
                out.append(child.name)
        except OSError:
            continue
    return out


def door_text() -> str:
    r = REPO.as_posix()
    return (MARK_BEGIN + "\n"
            "[MUST] 开工前置：任何任务动手前，先读 `%s/ROUTE.md`，按其 §1 走四步"
            "（拿证 → 判类 → 装 skill → 读参考），**先输出 `[ROUTE]` 声明**再干活。"
            "拿证命令：`python %s/tools/preflight.py <类型>`。\n" % (r, r)
            + MARK_END)


def door_status(p: Path):
    """返回 (状态, 说明)。状态 ∈ {ok, plan, absent, broken}"""
    if not p.exists():
        return "absent", "不存在（跳过）"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return "broken", "读不到：%s" % e
    if MARK_BEGIN in text and MARK_END in text:
        return "ok", "已装（标记块在位）"
    return "plan", "计划：插入标记块（先备份）"


def apply_door(p: Path) -> str:
    """写入/更新标记块。返回说明。"""
    text = p.read_text(encoding="utf-8", errors="replace")
    block = door_text()
    if MARK_BEGIN in text and MARK_END in text:
        i = text.index(MARK_BEGIN)
        j = text.index(MARK_END) + len(MARK_END)
        if text[i:j] == block:
            return "已是最新"
        new = text[:i] + block + text[j:]
    else:
        bak = p.with_name(p.name + ".bak-" + _today())
        if not bak.exists():
            shutil.copy2(str(p), str(bak))
        new = text.rstrip("\n") + "\n\n" + block + "\n"
    p.write_text(new, encoding="utf-8")
    return "已写入"


def _today():
    import time
    return time.strftime("%Y%m%d")


# ── install ────────────────────────────────────────────────────────────────

def plan_client(name, skills_dir, how, probe_dir, apply):
    """返回 (级别, 一行说明)。级别 ∈ {ok, plan, warn, skip}"""
    sd, pd = Path(skills_dir).expanduser(), Path(probe_dir).expanduser()
    if not pd.exists():
        return "skip", "未检测到（跳过）"
    if how == "junction":
        tgt = link_target(sd)
        if tgt is not None:
            try:
                same = Path(tgt).resolve() == REPO.resolve()
            except OSError:
                same = False
            if same:
                return "ok", "已接好 → 本库"
            return "warn", "链接指向别处（%s）——人工确认后再动" % tgt
        if sd.exists():
            return "warn", "skills 目录是实体目录（非链接）——人工处理后重跑"
        if apply:
            ok = make_link(sd, REPO)
            return ("ok" if ok else "warn"), ("已创建 Junction → 本库" if ok else "创建失败")
        return "plan", "计划：创建 Junction → 本库"
    # per-item
    names = skills_on_disk()
    miss, wrong = [], []
    for n in names:
        lp = sd / n
        tgt = link_target(lp)
        if tgt is not None:
            try:
                if Path(tgt).resolve() == (REPO / n).resolve():
                    continue
            except OSError:
                pass
            wrong.append(n)
        elif lp.exists():
            wrong.append(n)
        else:
            miss.append(n)
    # 残留 = 端目录里「指向本库、但本库已无该目录」的链接（退库后没清）。
    stale = stale_links(sd, names)
    if apply and (miss or wrong or stale):
        sd.mkdir(parents=True, exist_ok=True)
        done = 0
        for n in miss:
            if make_link(sd / n, REPO / n):
                done += 1
        cut = 0
        for n in stale:
            try:
                os.rmdir(str(sd / n))        # 删 Junction 只摘链接，不动目标
                cut += 1
            except OSError:
                pass
        bits = ["补挂 %d / 共 %d" % (done, len(names))]
        if stale:
            bits.append("清残留 %d / %d" % (cut, len(stale)))
        if wrong:
            bits.append("异常 %d 项：%s" % (len(wrong), ",".join(wrong[:3])))
        return ("ok" if not wrong else "warn"), "逐项：" + "；".join(bits)
    if not miss and not wrong and not stale:
        return "ok", "逐项：全部正确（%d 项）" % len(names)
    parts = ["缺 %d 项" % len(miss)] if miss else []
    if stale:
        parts.append("残留 %d 项待清（%s）" % (len(stale), ",".join(stale[:4])))
    if wrong:
        parts.append("异常 %d 项" % len(wrong))
    return "plan", "逐项：" + "、".join(parts)


def cmd_install(apply: bool):
    print("skillman install%s" % ("" if apply else "（干跑；加 --apply 落地）"))
    print("库：%s（%d 个 skill）\n" % (disp(REPO), len(skills_on_disk())))

    print("[客户端接线]")
    stats = {"ok": 0, "plan": 0, "warn": 0, "skip": 0}
    for name, sd, how, pd in CLIENTS:
        lv, msg = plan_client(name, sd, how, pd, apply)
        stats[lv] = stats.get(lv, 0) + 1
        print("  %-13s %-32s %s" % (name, disp(Path(sd).expanduser()), msg))
    print("  %-13s %-32s %s" % ("Qoder", "—", "无 skills 目录约定，只走规则门（用全局门/项目门）"))

    print("\n[全局门]")
    door_hit = False
    for cand in GLOBAL_DOORS:
        p = Path(cand).expanduser()
        lv, msg = door_status(p)
        if lv == "absent":
            continue
        door_hit = True
        if lv == "plan" and apply:
            msg = apply_door(p)
        print("  %-28s %s" % (disp(p), msg))
    if not door_hit:
        print("  未发现全局规则文件——请按 templates/global-door.md 手工放置（或告诉 skillman 新增候选路径）")

    print("\n[钩子（可选）]")
    print("  片段见 templates/hook-settings.json；合并进客户端 settings.json 后，"
          "没开工证的动作会被 hooks/skill_gate.py 拦下。")

    print("\n[提示] " + ("落地完成。" if apply else
                        "干跑结束。确认无误后重跑： python tools/skillman.py install --apply"))
    return 1 if stats["warn"] else 0


# ── sync ───────────────────────────────────────────────────────────────────

def cmd_sync(apply: bool):
    print("skillman sync%s\n" % ("" if apply else "（干跑；加 --apply 落地）"))
    git = shutil.which("git")
    if (REPO / ".git").exists() and git:
        if apply:
            r = subprocess.run([git, "-C", str(REPO), "pull", "--ff-only"],
                               capture_output=True, text=True)
            print("[git pull] rc=%d\n%s" % (r.returncode, (r.stdout or r.stderr).strip()))
        else:
            r = subprocess.run([git, "-C", str(REPO), "status", "-sb"],
                               capture_output=True, text=True)
            print("[git] 计划：pull --ff-only（当前：%s）" % (r.stdout or "").strip().splitlines()[:1])
    else:
        print("[git] 本库不是 git 仓或没有 git——跳过更新")
    print("\n→ 接续执行 install 的挂接部分：")
    rc1 = cmd_install(apply)
    print("\n→ 接续执行 doctor：")
    rc2 = cmd_doctor()
    return max(rc1, rc2)


# ── doctor ─────────────────────────────────────────────────────────────────

def frontmatter_ok(d: Path):
    p = d / "SKILL.md"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, "SKILL.md 读不到"
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False, "无 frontmatter"
    fm = []
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        fm.append(ln)
    blk = "\n".join(fm)
    m = re.search(r"^name:\s*(.+)$", blk, re.M)
    if not m:
        return False, "缺 name"
    nm = m.group(1).strip().strip('"').strip("'")
    if nm != d.name:
        return False, "name=%s ≠ 目录名" % nm
    if not re.search(r"^description:", blk, re.M):
        return False, "缺 description"
    return True, "ok"


def workflow_skill_names(text):
    """取 WORKFLOW.md §2 表格里「必载 skill」列（第 3 列）的反引号 skill 名。

    **只取那一列、不扫全文**：全文里还有 `doctor` / `—` / `ROUTE.md` 这类反引号词，
    扫全文会把它们误判成 skill 名。列定位口径与 ROUTE.md §2 的解析保持一致。
    """
    if "## 2." not in text:
        return []
    sec = text.split("## 2.", 1)[1].split("## 3.", 1)[0]
    out = []
    for line in sec.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        out.extend(re.findall(r"`([a-z0-9][a-z0-9_-]*)`", cells[2]))
    return sorted(set(out))


def local_layer_names():
    """从 .gitignore 解析「本地层」目录名（`/name/` 形式）。

    本名单是**公开层 / 本机层的分界线**，也是漂移检查的放行名单——
    磁盘上已删的名字若还留在这里，会**放行本不该放行的引用**（2026-09-30 清过 4 个）。
    """
    gi = REPO / ".gitignore"
    if not gi.is_file():
        return set()
    return set(re.findall(r"^/([A-Za-z0-9_.-]+)/$",
                          gi.read_text(encoding="utf-8", errors="replace"), re.M))


def cmd_doctor():
    print("skillman doctor（只读体检）\n")
    errors, warns, oks = [], [], []

    # 1. 本库完整性
    print("[1/5] 本库完整性")
    required = ["ROUTE.md", "WORKFLOW.md", "PREREQUISITES.md", "AGENTS.md", "README.md",
                "tools/preflight.py", "hooks/skill_gate.py", "tools/ops.json"]
    for rel in required:
        if (REPO / rel).exists():
            oks.append(rel)
        else:
            errors.append("缺文件：%s" % rel)
    print("  %s" % ("全部在位（%d 项）" % len(required) if not errors
                    else "；".join(errors)))

    skills = skills_on_disk()
    # 2. 客户端接线
    print("[2/5] 客户端接线（探针：%s/SKILL.md）" % PROBE)
    for name, sd, how, pd in CLIENTS:
        if not Path(pd).expanduser().exists():
            continue
        sdp = Path(sd).expanduser()
        if how == "junction":
            tgt = link_target(sdp)
            if tgt is None:
                warns.append("%s 未接（%s 不是链接）" % (name, disp(sdp)))
                print("  ✗ %-13s 未接" % name)
                continue
            try:
                same = Path(tgt).resolve() == REPO.resolve()
            except OSError:
                same = False
            if same:
                oks.append(name)
                print("  ✓ %-13s → 本库" % name)
            else:
                warns.append("%s 指向 %s" % (name, tgt))
                print("  ✗ %-13s 指向别处" % name)
        else:
            probe = sdp / PROBE / "SKILL.md"
            st = stale_links(sdp, skills)
            if st:
                warns.append("%s 有 %d 个悬空接线：%s" % (name, len(st), ",".join(st[:4])))
            if probe.exists():
                oks.append(name)
                print("  ✓ %-13s 探针穿透%s" % (name, "（✂ 残留 %d 待清）" % len(st) if st else ""))
            else:
                warns.append("%s 探针不通（缺 %s）" % (name, disp(probe)))
                print("  ✗ %-13s 探针不通" % name)

    # 3. skill 可调用性
    print("[3/5] skill 可调用性（%d 个）" % len(skills))
    bad = []
    for n in skills:
        ok, msg = frontmatter_ok(REPO / n)
        if not ok:
            bad.append("%s：%s" % (n, msg))
    if bad:
        errors.extend(bad)
        print("  ✗ %d 个有问题：\n    - %s" % (len(bad), "\n    - ".join(bad)))
    else:
        print("  ✓ 全部合法（name=目录名 + description 在位）")

    # 4. 路由一致性（ROUTE.md）
    print("[4/5] 路由一致性（ROUTE.md）")
    try:
        sys.path.insert(0, str(REPO / "tools"))
        import preflight as _pf                                  # noqa: E402
        ops = _pf.parse_ops()
        referenced = sorted({s for v in ops.values() for s in v["skills"]})
        missing = [s for s in referenced if s not in skills]
        # **区分「公开层缺」与「本地层缺」**（2026-09-30）：
        # 本地层 skill **本来就不随本仓发布**（见 `.gitignore` 与 PREREQUISITES.md §3），
        # 新机 clone 后缺它们是**已知状态，不是缺陷** ⇒ 只警告，不算错误。
        # 只有**公开层**的 skill 被引用却不在，才是真问题（表写错了，或仓不完整）。
        _gi = REPO / ".gitignore"
        _local = set(re.findall(r"^/([A-Za-z0-9_.-]+)/$",
                                _gi.read_text(encoding="utf-8"), re.M)) if _gi.is_file() else set()
        _hard = [s for s in missing if s not in _local]
        _soft = [s for s in missing if s in _local]
        if _hard:
            errors.append("路由引用了不存在的**公开层** skill：%s" % ",".join(_hard))
            print("  ✗ 引用了不存在的**公开层** skill：%s" % ",".join(_hard))
        if _soft:
            warns.append("本地层 skill 未装：%s" % ",".join(_soft))
            print("  ⚠ 本地层 skill 未装（不随本仓发布，属已知状态）：%s" % ",".join(_soft))
            print("    → 逐项清单与装法见 PREREQUISITES.md §3")
        if not missing:
            print("  ✓ 表内引用的 skill 全部存在（%d 个任务类型 / %d 个 skill）"
                  % (len(ops), len(referenced)))
        route_text = (REPO / "ROUTE.md").read_text(encoding="utf-8")
        noref = [n for n in skills if n not in route_text]
        if noref:
            warns.append("未在 ROUTE.md 出现：%s" % ",".join(noref))
            print("  ⚠ 未在公开路由表出现（%d 个，若为本地扩展 skill 属正常，"
                  "请在本地增量表登记）：%s" % (len(noref), ", ".join(noref[:12])))

        # 4b. WORKFLOW.md 防漂 —— 阶段视图里的 skill 名必须 ⊆（ROUTE.md §2 ∪ .gitignore 本地层）
        #
        # 为什么要有这条：WORKFLOW.md 的「必载 skill」列是对 ROUTE.md §2 的**复述**
        # （同一批 skill 按阶段重排一遍），**复述就会漂**。写了 ROUTE.md 里没有的名字，
        # agent 照 WORKFLOW.md 装载 → 装空或装错，而两份文档各自看都"没问题"。
        # 允许名单必须含**本地层**：ROUTE.md §2 是公开表，本不该出现平台自带/第三方大件的名字，
        # 但 WORKFLOW.md 是阶段视图、会点它们的名（如落图阶段的 easyeda-agent）——这是正常的。
        wf = REPO / "WORKFLOW.md"
        _local = local_layer_names()
        if not wf.is_file():
            errors.append("缺文件：WORKFLOW.md（流程阶段视图）")
            print("  ✗ 缺 WORKFLOW.md")
        else:
            _allowed = set(referenced) | _local
            _drift = [n for n in workflow_skill_names(wf.read_text(encoding="utf-8"))
                      if n not in _allowed]
            if _drift:
                errors.append("WORKFLOW.md 漂移：%s 不在 ROUTE.md §2，也不在 .gitignore 本地层"
                              % ",".join(_drift))
                print("  ✗ WORKFLOW.md 漂移：%s" % ", ".join(_drift))
            else:
                print("  ✓ WORKFLOW.md 与 ROUTE.md §2 一致（放行本地层 %d 个）" % len(_local))
    except Exception as e:                                       # noqa: BLE001
        warns.append("路由解析不可用：%r" % e)
        print("  ⚠ 路由解析不可用：%r" % e)

    # 5. 全局门
    print("[5/5] 全局门")
    found = [c for c in GLOBAL_DOORS if Path(c).expanduser().exists()]
    installed = [c for c in found
                 if MARK_BEGIN in Path(c).expanduser().read_text(encoding="utf-8", errors="replace")]
    if installed:
        print("  ✓ 已装：%s" % ", ".join(disp(Path(c).expanduser()) for c in installed))
    elif found:
        warns.append("全局门未装（候选文件存在但无标记块）")
        print("  ⚠ 候选文件存在但未装（跑 install --apply）")
    else:
        warns.append("未发现全局规则文件")
        print("  ⚠ 未发现全局规则文件（按 templates/global-door.md 手工放置）")

    print("\n结果：OK=%d ｜ 警告=%d ｜ 错误=%d" % (len(oks), len(warns), len(errors)))
    if warns:
        print("警告：")
        for w in warns:
            print("  - %s" % w)
    if errors:
        print("错误：")
        for e in errors:
            print("  - %s" % e)
    print("EXIT:", 1 if errors else 0)
    return 1 if errors else 0


# ── main ───────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog="skillman", description="本库管理：install（装）/ sync（更新）/ doctor（体检）")
    ap.add_argument("command", choices=["install", "sync", "doctor"])
    ap.add_argument("--apply", action="store_true", help="真正落地（默认干跑）")
    args = ap.parse_args()
    if args.command == "install":
        return cmd_install(args.apply)
    if args.command == "sync":
        return cmd_sync(args.apply)
    return cmd_doctor()


if __name__ == "__main__":
    raise SystemExit(main())
