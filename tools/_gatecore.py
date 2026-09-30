#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_gatecore.py — 开工证闸门的**唯一判定实现**（两个钩子共用）。

为什么要有它：`~/.ai-skills/hooks/skill_gate.py` 与
`rules/hooks/workbench_gate.py` 是**同一套判据**的两个宿主 —— 不抽出来就会各改各的、
慢慢漂开。本仓 2026-09-30 已因"两份独立实现"收口过一次（`preflight.py` / `gate.py`
改薄转发，见 `CHANGELOG.md`），这里是同一手法的延续。

本模块只放**判定**，不放：证池读写 · 日志 · stderr 提示 · ops.json 路径
—— 那些两个宿主各不相同，留在各自文件里。

## 判据（2026-09-30 重构：从「文本匹配」改成「看动作实际碰什么」）

    命中 = (argv[0] ∈ zone.executables)  OR  (目标路径 ∈ zone.paths)

**旧判据的错**：在**整条命令字符串**里找工具名 ⇒ `grep -oE '...|st-flash|...'` 这种
**只读搜索**也会命中（2026-09-30 实测被误拦；此前同类误拦 3 次，那次靠加词边界修了
`jlink` / `easyeda`，但 `st-flash` 是独立词，词边界治不了）。**根因是判据选错了，
不是词表不全** —— 加白名单治不了。

**新判据**：把命令按 `|` `&&` `||` `;` 换行**拆段**（引号内不拆），每段取 `argv[0]`；
`argv[0]` 是解释器（python / node / bash …）时，再取其后**第一个非开关参数**（即脚本）。
于是：
    `python tools/eda_sch.py nc`  → {python, eda_sch.py} → 命中 eda_sch.py ✓
    `grep -oE 'a|st-flash|b' f`   → {grep}               → 不命中 ✓（误拦根治）

**设备动作不在判定范围内**（2026-09-30 拍板 D3）：角色分工写着"AI 不烧板、不下单"，
拦它是**拦错对象**。所以 `JLink*` / `openocd` / `st-flash` / `STM32_Programmer` 一律不在
任何 zone 的 `executables` 里。
"""
import fnmatch
import re
from pathlib import Path

WRITE_TOOLS = {"write_to_file", "replace_in_file", "edit_file", "create_file",
               "Edit", "Write", "MultiEdit", "NotebookEdit"}
EXEC_TOOLS = {"execute_command", "Bash", "run_command", "terminal"}

# 解释器 / 执行器：`argv[0]` 命中它时，真正"被执行的东西"是后面第一个非开关参数。
# 用正则而不是集合：本机有 `python3.13` 这种带版本的写法（实测 python 解析到 MSYS 的 3.14）。
_RUNNER_RE = re.compile(
    r"^(python|py|node|npx|npm|bash|sh|zsh|pwsh|powershell|cmd|env)"
    r"[\d.]*(\.exe|\.cmd|\.bat)?$")


def target_of(tool, ti):
    """返回 (类型, 目标字符串)：类型 ∈ {path, cmd, ''}。"""
    if tool in WRITE_TOOLS:
        for k in ("file_path", "filePath", "target_file", "path", "notebook_path"):
            v = ti.get(k)
            if isinstance(v, str) and v:
                return "path", v
        return "", ""
    if tool in EXEC_TOOLS:
        for k in ("command", "cmd", "script"):
            v = ti.get(k)
            if isinstance(v, str) and v:
                return "cmd", v
        return "", ""
    return "", ""


def fnmatch_any(pat, s):
    if fnmatch.fnmatch(s, pat) or fnmatch.fnmatch(s.lower(), pat.lower()):
        return True
    if pat.startswith("**/"):
        return (fnmatch.fnmatch(s, pat[3:]) or fnmatch.fnmatch(s.lower(), pat[3:].lower()))
    return False


def norm(p, base):
    """归一到 base 相对的 posix 串 → (key, in_base)。"""
    s = str(p).replace("\\", "/")
    try:
        rp = Path(p)
        if not rp.is_absolute():
            rp = Path.cwd() / rp
        rp = rp.resolve()
        return rp.relative_to(Path(base).resolve()).as_posix(), True
    except ValueError:
        return s, False
    except Exception:                                            # noqa: BLE001
        return s, False


def path_hit(patterns, key, in_base):
    """paths 规则匹配：`repo:` 前缀 = 本仓内（key 已归一为仓相对路径）。"""
    for p in patterns:
        if p.startswith("repo:"):
            if in_base and fnmatch_any(p[5:] or "**", key):
                return True
        elif fnmatch_any(p, key):
            return True
    return False


# ---------------------------------------------------------------- 命令判定

def segments(cmd):
    """按 `|` `||` `&&` `;` 换行拆段 —— **只在引号外拆**。

    引号内不拆是必须的：`grep -oE 'a|st-flash|b'` 里的 `|` 是**搜索模式**的一部分，
    拆开就等于把只读搜索当成了执行。
    """
    out, buf, q = [], [], None
    for ch in cmd:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            buf.append(ch)
            continue
        if ch == "\n" or ch in "|&;":
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    return [s.strip() for s in out if s.strip()]


def tokens(seg):
    """把一段命令切成 token（尊重单双引号；不做变量展开）。"""
    out, buf, q = [], [], None
    for ch in seg:
        if q:
            if ch == q:
                q = None
            else:
                buf.append(ch)
            continue
        if ch in "\"'":
            q = ch
            continue
        if ch.isspace():
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def effective_executables(seg):
    """→ 这一段**实际执行**的可执行名集合（basename、小写）。

    · 取 `argv[0]` 的 basename；先剥掉 `VAR=value` 前缀（`FOO=1 python x.py`）
    · `argv[0]` 是解释器 → 再取其后**第一个非开关参数**（`-c` = 内联代码，到此为止）
    · **不扫全串** —— 这正是旧判据误拦只读搜索的根因
    """
    toks = tokens(seg)
    while toks and _ENV_ASSIGN.match(toks[0]):
        toks.pop(0)
    if not toks:
        return set()
    head = Path(toks[0]).name.lower()
    out = {head}
    if _RUNNER_RE.match(head):
        for t in toks[1:]:
            if t == "-c":
                break
            if t.startswith("-"):
                continue
            out.add(Path(t).name.lower())
            break
    return out


def command_hit(zone, cmd):
    """zone 的 `executables` 里，有没有哪个是这条命令**真的在执行**的。"""
    exes = [str(e).lower() for e in zone.get("executables", [])]
    if not exes:
        return False
    for seg in segments(cmd):
        if effective_executables(seg) & set(exes):
            return True
    return False


# ---------------------------------------------------------------- 汇总

def hit_zones(cfg, kind, key, in_base):
    """→ 命中的 zone 列表。**取并集**：同一动作可命中多个 zone。"""
    out = []
    for z in cfg.get("zones", []):
        if kind == "path":
            hit = path_hit(z.get("paths", []), key, in_base)
        else:
            hit = command_hit(z, key)
        if hit:
            out.append(z)
    return out


def allowed_of(zones):
    """→ (允许的任务类型列表, 各 zone 的 why 列表)。"""
    allowed, whys = [], []
    for z in zones:
        whys.append(z.get("why"))
        for o in z.get("ops", []):
            if o not in allowed:
                allowed.append(o)
    return allowed, whys


def cert_check(pool, allowed, skills_dir, ttl_hours=8):
    """→ (是否放行, 展示串)。任一张证：未超时 + 绑定 skill 未改 + 类型 ∈ allowed。"""
    import hashlib
    import time
    ok, seen = False, []
    for d in (pool or []):
        op = d.get("op", "?")
        fresh = (time.time() - d.get("ts", 0)) <= ttl_hours * 3600
        intact = True
        for n, h in (d.get("skills") or {}).items():
            p = Path(skills_dir) / n / "SKILL.md"
            if p.exists():
                try:
                    if hashlib.sha256(p.read_bytes()).hexdigest() != h:
                        intact = False
                        break
                except OSError:
                    pass
        seen.append(op + ("" if (fresh and intact) else
                          ("(超时)" if not fresh else "(skill已改)")))
        if fresh and intact and op in allowed:
            ok = True
            return True, op
    return ok, (",".join(seen) or "(无证)")
