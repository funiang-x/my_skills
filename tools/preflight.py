#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight.py — 开工前置：把该操作要读的 skill 条款**实际打印出来**，并发一张开工证。

为什么要有它：长文档进上下文会被压缩，关键条款会丢——"放在显眼处提醒"治不了这个，
只有"不做就走不下去"能治。本脚本 + `hooks/skill_gate.py`（PreToolUse 硬闸门）
把开工前置从"靠自觉"改成"拦得住"。

用法（在任意目录）：
    python tools/preflight.py                # 列出全部任务类型
    python tools/preflight.py 硬件/落图        # 打印条款 + 发开工证
    python tools/preflight.py --status        # 看当前证是否有效

**可传协议文件 / 证池 / skill 目录**（本工作台之外的宿主用它复用同一实现，见下）：
    python tools/preflight.py --protocol /path/to/01_任务路由协议.md \
        --state /path/to/rules/.state/preflight.json \
        --skills ~/.ai-skills --noun 操作类型 --ref 01_任务路由协议 硬件/落图

开工证绑定**每个 skill 内容的 sha256** —— 所以**改了 skill 就必须重新走一遍**，旧证自动作废。
证默认写在 `.state/preflight.json`（相对本仓库）。协议默认唯一来源：`ROUTE.md` §2。
"""
from pathlib import Path
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                               # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent        # 仓库根（skill 就在根级）


def _split_args() -> tuple:
    """→ (位置参数, 选项字典)。选项形如 `--k v`；后面没跟值的算开关（如 `--status`）。"""
    pos, opts, i = [], {}, 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a.startswith("--"):
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                opts[a[2:]] = sys.argv[i + 1]
                i += 2
            else:
                opts[a[2:]] = True
                i += 1
            continue
        pos.append(a)
        i += 1
    return pos, opts


ARGS, OPT = _split_args()
PROTOCOL = Path(OPT.get("protocol", REPO / "ROUTE.md")).resolve()
SKILLS = Path(OPT.get("skills", REPO)).resolve()
STATE = Path(OPT.get("state", REPO / ".state" / "preflight.json")).resolve()
NOUN = OPT.get("noun", "任务类型")                   # 打印措辞（工作台说"操作类型"）
REF = OPT.get("ref", PROTOCOL.stem)                  # [ROUTE] 声明里的「依据=」
TTL_HOURS = 8

import hashlib                                                  # noqa: E402
import json                                                     # noqa: E402
import re                                                       # noqa: E402
import time                                                     # noqa: E402


def parse_ops():
    """从协议文件的 §2 装配表解析「任务类型 → 必载 skill / 必读」。

    不另建一份清单（单点真相）：协议表就是唯一来源。
    skill 名靠"目录里有 SKILL.md"来识别，顺带滤掉 `tools/`、`templates/` 之类。
    """
    text = PROTOCOL.read_text(encoding="utf-8")
    disk = {d.name for d in SKILLS.iterdir()
            if d.is_dir() and (d / "SKILL.md").is_file()}
    ops = {}
    for line in text.splitlines():
        if not line.startswith("|") or line.count("|") < 4:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = re.fullmatch(r"`([^`]+)`", cells[0])
        if not m or m.group(1) in ("类型",) or set(cells[0]) <= set("-: "):
            continue
        op = m.group(1)
        # **按名字形状过滤，不按磁盘过滤**（2026-09-30 修）：
        # 原先这里是 `if s in disk` —— 于是"引用了但没装"的名字被解析层吃掉，
        # 调用方（`skillman doctor` 的"路由引用了不存在的 skill"）永远拿到空 missing，
        # **那道检查成了死代码**。实测：新机 clone 后 doctor 报"全部存在"，其实缺 3 个。
        # 形状过滤仍能滤掉 `Tools/fw.py` / `CMakePresets.json` / `references/usage.md` 这类噪声。
        skills = [s for s in re.findall(r"`([^`]+)`", cells[2] if len(cells) > 3 else "")
                  if re.fullmatch(r"[a-z][a-z0-9_-]*", s)]
        seen, uniq = set(), []
        for s in skills:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        docs = (" ".join(cells[3:]).strip() if len(cells) > 3 else cells[2]) or "无"
        ops[op] = {"trigger": cells[1], "skills": uniq, "docs": docs}
    return ops


def skill_block(name):
    """返回 (skill 的 sha256, 开工前置块原文, 章节标题列表)。"""
    p = SKILLS / name / "SKILL.md"
    if not p.exists():
        return "", "", []
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", "replace")
    lines = text.splitlines()
    top, heads = [], []
    for ln in lines:
        if ln.startswith("## ") or ln.startswith("### "):
            heads.append(ln.lstrip("# ").strip())
    for i, ln in enumerate(lines):
        if "[MUST] 开工前置" in ln:
            for ln2 in lines[i:i + 22]:
                if top and ln2.startswith("## "):
                    break
                top.append(ln2)
            break
    return sha, "\n".join(top), heads


def main():
    ops = parse_ops()

    if OPT.get("status"):
        if not STATE.exists():
            print("开工证：**无**。开工前跑 `python tools/preflight.py <%s>`。" % NOUN)
            return 1
        pool = json.loads(STATE.read_text(encoding="utf-8")).get("tokens", [])
        if not pool:
            print("开工证：**无**（全部过期或未签发）。")
            return 1
        now = time.time()
        for d in pool:
            age = (now - d.get("ts", 0)) / 3600
            good = age <= TTL_HOURS and all(
                hashlib.sha256((SKILLS / n / "SKILL.md").read_bytes()).hexdigest() == h
                for n, h in (d.get("skills") or {}).items()
                if (SKILLS / n / "SKILL.md").exists())
            print("开工证：%-12s ｜ 任务=%-16s ｜ %.1f 小时前 ｜ %s"
                  % (d.get("token"), d.get("op"), age,
                     "有效" if good else "**已失效**（超时或 skill 已改）"))
        return 0

    if not ARGS:
        print("可用的%s（来自 `%s` §2，共 %d 个）：\n" % (NOUN, PROTOCOL.name, len(ops)))
        for op, v in ops.items():
            print("  %-20s skill=%-38s %s"
                  % (op, ",".join(v["skills"]) or "无", v["trigger"][:42]))
        print("\n用法： python tools/preflight.py <%s>" % NOUN)
        print("（不带证去做改动动作，会被 PreToolUse 钩子拦下；钩子装法见 templates/hook-settings.json）")
        return 0

    op = ARGS[0]
    if op not in ops:
        print("⛔ 没有这个%s：%s\n\n可用：\n" % (NOUN, op))
        for k in ops:
            print("   ", k)
        return 2

    v = ops[op]
    print("=" * 78)
    print("开工前置 ｜ %s：%s" % (NOUN, op))
    print("触发特征：%s" % v["trigger"])
    print("必载 skill：%s" % (", ".join(v["skills"]) or "无（本类型无 skill）"))
    print("必读：%s" % v["docs"])
    print("=" * 78)

    shas = {}
    for name in v["skills"]:
        sha, top, heads = skill_block(name)
        if not sha:
            print("\n⚠️ skill `%s` **未安装**（目录/文件缺失）。" % name)
            print("   常见原因：它是**本地层 skill**（不随本仓发布）→ 见 `PREREQUISITES.md` §3；"
                  "若确已废弃，则按 `%s` §2 修表。" % PROTOCOL.name)
            continue
        shas[name] = sha
        print("\n" + "─" * 78)
        print("【skill】%s   sha256=%s" % (name, sha[:12]))
        print("─" * 78)
        if top:
            print(top)
        if heads:
            print("\n▶ 该 skill 的章节（**逐节读原文**，重点：含「开工必读 / 铁律 / 坑」的节）：")
            for h in heads:
                print("    · %s" % h)

    print("\n" + "=" * 78)
    print("[MUST] 接着按顺序做，缺一步都不算开工：")
    print("  1. 用 `read_file` **读上面列出的章节原文**（别凭印象；长文会被压缩，读了才算数）")
    print("  2. 读上面「必读」列点到的文件")
    print("  3. 把下面这行加进你的 `[ROUTE]` 声明（含 `证=` 字段）再动手：")
    tok = hashlib.sha256(
        (op + "|" + "|".join(sorted(shas.values())) + "|" + time.strftime("%Y-%m-%d"))
        .encode("utf-8")).hexdigest()[:12]
    print()
    print("[ROUTE] 类型=%s | skill=%s | 参考=%s | 证=%s | 依据=%s"
          % (op, ",".join(shas) or "无", v["docs"][:40], tok, REF))
    print()
    print("  （证已写入 `%s`，%d 小时内有效；"
          "**skill 内容一改，证自动作废**，需重跑本命令）" % (STATE, TTL_HOURS))
    print("=" * 78)

    # 多张证并存（各带自己的 TTL），切任务不必来回重跑；同任务类型覆盖旧的
    STATE.parent.mkdir(parents=True, exist_ok=True)
    try:
        pool = json.loads(STATE.read_text(encoding="utf-8")).get("tokens", [])
    except Exception:                                            # noqa: BLE001
        pool = []
    now = time.time()
    pool = [t for t in pool
            if now - t.get("ts", 0) <= TTL_HOURS * 3600 and t.get("op") != op]
    pool.append({"op": op, "ts": now, "token": tok, "skills": shas})
    STATE.write_text(json.dumps({"tokens": pool}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
