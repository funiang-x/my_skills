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

**判定实现在 `tools/_gatecore.py`**（唯一实现，与 `rules/hooks/workbench_gate.py` 共用）。
2026-09-30 重构批次 1：判据从「整条命令串里找工具名」改成「看动作实际碰什么」
（`argv[0] ∈ executables` 或 `目标路径 ∈ paths`）—— 详见 `_gatecore.py` 头部注释。

**内部出错一律放行（fail-open）**：钩子有 bug 不该把整个 agent 锁死；出错只记一条日志。

**2026-10-02 修**：证池从"只认库根 `.state/`"改成**多池兼容** —— `preflight.py` 2026-10 起把证
默认写在**当前工作区** `.ai-skills-state/preflight.json`（理由是写成工作区外会被文件沙箱拒写，
"拿不到证"与"环境不让写"会混成同一个失败）。而本钩子仍只读库根，**于是任何证都看不见、
凡跑库内脚本一律被拦**。现按 `$AI_SKILLS_STATE` → `<payload.cwd>/.ai-skills-state/` → 库根 `.state/`
顺序**全部读进来合并**，三种落点都能放行，向后兼容。
"""
from pathlib import Path
import json
import os
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
LOG = REPO / ".state" / "gate.log"
TTL_HOURS = 8


def state_pools(payload):
    """→ 证池候选路径（按优先级）。任一存在即读，全部合并。

    为什么是三个而不是一个：签发端（`tools/preflight.py`）与实际执行端（agent 的工作区）
    不是同一个目录，且历史上落点改过一次。少读一个就会变成"明明签了证却被拦"。
    """
    cands = []
    env = os.environ.get("AI_SKILLS_STATE")
    if env:
        cands.append(Path(env).expanduser())
    cwd = None
    for k in ("cwd", "workspace", "workspaceFolder", "project_dir"):
        if payload.get(k):
            cwd = payload[k]
            break
    if cwd:
        cands.append(Path(cwd).expanduser() / ".ai-skills-state" / "preflight.json")
    cands.append(REPO / ".state" / "preflight.json")
    seen, out = set(), []
    for c in cands:
        s = str(c)
        if s not in seen:
            seen.add(s)
            out.append(c)
    return out


def read_tokens(pools):
    """把所有存在的证池合并成一张 token 列表（坏文件跳过，不抛）。"""
    toks = []
    for p in pools:
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                toks.extend(data.get("tokens", []) or [])
        except Exception:                                        # noqa: BLE001
            continue
    return toks


sys.path.insert(0, str(REPO / "tools"))
import _gatecore as G                                            # noqa: E402


def log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:                                            # noqa: BLE001
        pass


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as e:                                       # noqa: BLE001
        log("stdin 解析失败，放行：%r" % e)
        return 0

    tool = str(payload.get("tool_name") or payload.get("toolName") or "").strip()
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    kind, tgt = G.target_of(tool, dict(ti) if isinstance(ti, dict) else {})
    if not kind:
        return 0

    try:
        cfg = json.loads(OPS.read_text(encoding="utf-8"))
    except Exception as e:                                       # noqa: BLE001
        log("ops.json 读不到，放行：%r" % e)
        return 0

    if kind == "path":
        key, in_repo = G.norm(tgt, REPO)
    else:
        key, in_repo = tgt, False

    for ex in cfg.get("_exempt", []):
        if kind == "path" and G.fnmatch_any(ex, key):
            return 0

    zones = G.hit_zones(cfg, kind, key, in_repo)
    if not zones:
        return 0

    allowed, whys = G.allowed_of(zones)
    ok, got = False, "(无证)"
    pools = state_pools(payload)
    try:
        ok, got = G.cert_check(read_tokens(pools), allowed, REPO, TTL_HOURS)
    except Exception:                                            # noqa: BLE001
        pass

    if ok:
        log("放行 %s <- %s [%s]" % (str(key)[:80], " / ".join(whys), got))
        return 0

    log("拦截 %s <- %s [证=%s 允许=%s 池=%s]"
        % (str(key)[:80], " / ".join(whys), got, allowed,
           ",".join(p.as_posix() for p in pools)))
    sys.stderr.write(
        "\n⛔ 未开工前置 —— 该动作属于「%s」，必须先读 skill。\n"
        "   动作：%s\n"
        "   当前证：%s\n"
        "   本动作接受的任务类型：%s\n"
        "   证池（任一有证即可）：%s\n\n"
        "   请现在执行：python %s/tools/preflight.py %s\n"
        "   它会把这个操作**该读的 skill 条款正文打印出来**，并签发开工证。\n"
        "   读完条款再重试本动作（证 8 小时有效；skill 内容一改即作废）。\n\n"
        % (" / ".join(whys), str(key)[:120], got, " / ".join(allowed),
           " | ".join(p.as_posix() for p in pools),
           REPO.as_posix(), allowed[0] if allowed else "<任务类型>"))
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:                                       # noqa: BLE001
        log("内部异常，放行：%r" % e)
        raise SystemExit(0)
