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

**判定实现在 `tools/_gatecore.py`**（唯一实现，与 `workbench/hooks/workbench_gate.py` 共用）。
2026-09-30 重构批次 1：判据从「整条命令串里找工具名」改成「看动作实际碰什么」
（`argv[0] ∈ executables` 或 `目标路径 ∈ paths`）—— 详见 `_gatecore.py` 头部注释。

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
    try:
        pool = json.loads(STATE.read_text(encoding="utf-8")).get("tokens", [])
        ok, got = G.cert_check(pool, allowed, REPO, TTL_HOURS)
    except Exception:                                            # noqa: BLE001
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:                                       # noqa: BLE001
        log("内部异常，放行：%r" % e)
        raise SystemExit(0)
