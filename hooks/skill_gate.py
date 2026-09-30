#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill_gate.py — PreToolUse 硬闸门：没拿开工证就拦住这个动作。

装在支持 PreToolUse 的客户端 settings.json（片段见 `templates/hook-settings.json`）：

    {"hooks": {"PreToolUse": [{"matcher": "write_to_file|replace_in_file|execute_command|Bash|Edit|Write",
        "hooks": [{"type": "command",
                   "command": "python <REPO>/hooks/skill_gate.py", "timeout": 15}]}]}}

协议（与上游实测确认过的实现同源）：
  · stdin 收 JSON：`tool_name` / `tool_input`
  · **退出码 2 = 拦截**；stderr 文本会回传给模型 —— 这就是"告诉它去读 skill"的通道

判定：把动作的**目标**（写哪个文件 / 跑什么命令）与 `tools/ops.json` 的 zone 比对；
命中 zone 就要求存在**新鲜开工证**（≤8h 且 skill 内容未变，见 `tools/preflight.py`）。

**内部出错一律放行（fail-open）**：钩子有 bug 不该把整个 agent 锁死；出错只记一条日志。
"""
from pathlib import Path
import json
import sys

# 往管道写 stderr 时 Windows 默认用 GBK，中文提示会变成乱码。
# 钩子的提示是给**模型**读的，必须 UTF-8。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

REPO = Path(__file__).resolve().parent.parent
OPS = REPO / "tools" / "ops.json"
STATE = REPO / ".state" / "preflight.json"
LOG = REPO / ".state" / "gate.log"
TTL_HOURS = 8

WRITE_TOOLS = {"write_to_file", "replace_in_file", "edit_file", "create_file",
               "Edit", "Write", "MultiEdit", "NotebookEdit"}
EXEC_TOOLS = {"execute_command", "Bash", "run_command", "terminal"}

import re                                                        # noqa: E402

# 命令命中判据：必须**在执行**那个脚本，而不是"提到"它。
#   `python x/eda_sch.py nc` ✓命中   ·   `Select-String ... eda_sch.py`（只读查看）✗不命中
RUNNER = re.compile(r"(?i)(^|[\s&|;(])(python3?(\.exe)?|py(\.exe)?|node|npx|bash|sh)(\s|$)")
# 自带可执行名的工具：出现即算执行（无条件命中）
EXECISH = ("jlink", "openocd", "st-flash", "stm32_programmer", "nrfjprog", "pyocd")


def log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:                                            # noqa: BLE001
        pass


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


def norm(p):
    """归一到仓库相对 posix 串。返回 (key, in_repo)。

    能归一到 REPO 下 → key 是相对路径、in_repo=True；否则原样（in_repo=False）。
    """
    s = str(p).replace("\\", "/")
    try:
        rp = Path(p)
        if not rp.is_absolute():
            rp = Path.cwd() / rp
        rp = rp.resolve()
        return rp.relative_to(REPO).as_posix(), True
    except ValueError:
        return s, False
    except Exception:                                            # noqa: BLE001
        return s, False


def fnmatch_any(pat, s):
    import fnmatch
    if fnmatch.fnmatch(s, pat) or fnmatch.fnmatch(s.lower(), pat.lower()):
        return True
    if pat.startswith("**/"):
        return fnmatch.fnmatch(s, pat[3:]) or fnmatch.fnmatch(s.lower(), pat[3:].lower())
    return False


def path_hit(patterns, key, in_repo):
    """paths 规则匹配：`repo:` 前缀 = 本仓库内（key 已归一为仓库相对路径）。"""
    for p in patterns:
        if p.startswith("repo:"):
            if in_repo and fnmatch_any(p[5:] or "**", key):
                return True
        elif fnmatch_any(p, key):
            return True
    return False


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as e:                                       # noqa: BLE001
        log("stdin 解析失败，放行：%r" % e)
        return 0

    tool = str(payload.get("tool_name") or payload.get("toolName") or "").strip()
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    kind, tgt = target_of(tool, dict(ti) if isinstance(ti, dict) else {})
    if not kind:
        return 0

    try:
        cfg = json.loads(OPS.read_text(encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        log("ops.json 读不到，放行：%r" % e)
        return 0

    if kind == "path":
        key, in_repo = norm(tgt)
    else:
        key, in_repo = tgt, False

    for ex in cfg.get("_exempt", []):
        if kind == "path" and fnmatch_any(ex, key):
            return 0

    # 同一个动作可能命中多个 zone —— **取并集**：任一张属于任一命中 zone
    # 允许的任务类型的证即放行。
    hit_zones = []
    for z in cfg.get("zones", []):
        if kind == "path":
            hit = path_hit(z.get("paths", []), key, in_repo)
        else:
            # 命令不能只"提到"脚本名就算命中（只读查看会被误拦）——
            # 必须是在"执行"它：命令里要有解释器/执行器标记。
            hit = False
            for c in z.get("commands", []):
                if c.lower() not in key.lower():
                    continue
                if any(c.lower().startswith(e) for e in EXECISH) or RUNNER.search(key):
                    hit = True
                    break
        if hit:
            hit_zones.append(z)

    if hit_zones:
        allowed, whys = [], []
        for z in hit_zones:
            whys.append(z.get("why"))
            for o in z.get("ops", []):
                if o not in allowed:
                    allowed.append(o)
        # 查开工证（多张并存，任一张命中放行）
        ok, got = False, "(无证)"
        try:
            import hashlib
            import time
            pool = json.loads(STATE.read_text(encoding="utf-8")).get("tokens", [])
            seen = []
            for d in pool:
                op = d.get("op", "?")
                fresh = (time.time() - d.get("ts", 0)) <= TTL_HOURS * 3600
                intact = all(
                    hashlib.sha256((REPO / n / "SKILL.md").read_bytes()).hexdigest() == h
                    for n, h in (d.get("skills") or {}).items()
                    if (REPO / n / "SKILL.md").exists())
                seen.append(op + ("" if fresh and intact else
                                  ("(超时)" if not fresh else "(skill已改)")))
                if fresh and intact and op in allowed:
                    ok = True
                    got = op
                    break
            if not ok:
                got = ",".join(seen) or "(无证)"
        except Exception:                                        # noqa: BLE001
            pass
        if ok:
            log("放行 %s <- %s [%s]" % (str(key)[:80], " / ".join(whys), got))
            return 0
        log("拦截 %s <- %s [证=%s 允许=%s]" % (str(key)[:80], " / ".join(whys), got, allowed))
        sys.stderr.write(
            "\n⛔ 未开工前置 —— 该动作属于「%s」，必须先读 skill。\n"
            "   动作：%s\n"
            "   当前证：%s\n"
            "   本动作接受的任务类型：%s\n\n"
            "   请现在执行：python %s/tools/preflight.py %s\n"
            "   它会把这个操作**该读的 skill 条款正文打印出来**，并签发开工证。\n"
            "   读完条款再重试本动作（证 8 小时有效；skill 内容一改即作废）。\n\n"
            % (" / ".join(whys), str(key)[:120], got, " / ".join(allowed),
               REPO.as_posix(), allowed[0] if allowed else "<任务类型>"))
        return 2

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:                                       # noqa: BLE001
        log("内部异常，放行：%r" % e)
        raise SystemExit(0)
