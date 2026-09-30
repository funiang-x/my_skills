#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill_audit.py — skill 库**只读**审计（来源 / 体量 / 死链 / 重叠 / 孤儿）。

为什么要有它：`skillman.py doctor` 只查「接线通不通、frontmatter 合不合法」——
**结构合法 ≠ 值得留**。本脚本查的是"该不该留"的四类客观信号：

  ① 来源（provenance）  平台自带 / 第三方上游 / 自研 / 未知 —— 未知项 = 该补标签的
  ② 体量（context 成本）SKILL.md 行数 + 附属文件数 —— 装一次要吃掉多少上下文
  ③ 死链                 正文里引用的 skill 本地文件（scripts/… · LESSONS.md）是否存在
  ④ 重叠                 同一任务类型下 ≥2 个 skill 的触发词重合度 —— 冗余候选
  ⑤ 孤儿                 在库但未登记进 ROUTE.md §2 —— 永远不会被路由到

**它不下判决**。删/留是人拍板（见 README「维护」节）；本脚本只把证据摆齐。

用法：
    python tools/skill_audit.py            # 打印报告（默认，只读）
    python tools/skill_audit.py --write    # 写入 SKILL_AUDIT.md
    python tools/skill_audit.py --json     # 机器可读
退出码：0 = 无高危项；1 = 有（死链 / 孤儿 / 重叠对）
"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                              # noqa: BLE001
    pass

REPO = Path(__file__).resolve().parent.parent
ROUTE = REPO / "ROUTE.md"
README = REPO / "README.md"
GITIGNORE = REPO / ".gitignore"
# 落在 .state/ 而非仓根：报告里会列出平台自带 skill 的名字，
# 那是**本地层**（见 .gitignore），写进仓根等于把它泄漏到公开仓。
OUT = REPO / ".state" / "SKILL_AUDIT.md"

# 库基础设施，不是 skill
INFRA = {"tools", "hooks", "templates", "shared", ".state", ".git",
         "embedded_ai_skills", "node_modules", "__pycache__"}

# 重叠判定：同一对 skill 的「特征词」IDF 加权分 ≥ 此值 → 报为冗余候选。
# 特征词 = 只在 ≤RARE_DF 个 skill 的 description 里出现的词（全库套话不计分）。
OVERLAP_SCORE = 1.0
RARE_DF = 4

# 描述里没有信息量的词（后一组 = 本库中文 description 的通用套话，去掉才比得出真重叠）
STOP = set("""use when the a an of to for and or is are with in on it this that
any all not you your user users want wants needs need using used also say says
skill skills agent agents task tasks code coding work works""".split())
STOP |= set("""需要 使用 当需 时使 嵌入 入式 用自 自带 进行 通过 要通 完成 查时
调用 支持 相关 以及 可以 一个 这个 那个 如果 或者 并且 用来 用于 适用 场景""".split())


# ---------------------------------------------------------------- frontmatter

def frontmatter(skill_dir: Path) -> dict:
    """取 SKILL.md 的 frontmatter（只做浅层 key: value，够用）。"""
    p = skill_dir / "SKILL.md"
    if not p.is_file():
        return {}
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\r?\n(.*?)\r?\n---", txt, re.S)
    if not m:
        return {}
    fm, out, key, buf = m.group(1), {}, None, []
    for line in fm.splitlines():
        if re.match(r"^[A-Za-z_][\w-]*\s*:", line):
            if key:
                out[key] = "\n".join(buf).strip()
            key = line.split(":", 1)[0].strip()
            buf = [line.split(":", 1)[1].strip()]
        elif key:
            buf.append(line.strip())
    if key:
        out[key] = "\n".join(buf).strip()
    return out


def desc_of(fm: dict) -> str:
    return re.sub(r"\s+", " ", fm.get("description", "")).strip()


def metadata_of(fm: dict) -> str:
    """metadata 块是缩进子块，原样返回便于搜 source / author。"""
    return fm.get("metadata", "")


# ---------------------------------------------------------------- provenance

def local_layer() -> dict:
    """从 .gitignore 解析「不进仓」清单 → {名字: platform|vendor|local}。归类取其上方注释。"""
    if not GITIGNORE.is_file():
        return {}
    out, comment = {}, ""
    for line in GITIGNORE.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("#"):
            c = s.lstrip("#").strip()
            if c:
                comment = c
            continue
        m = re.match(r"^/([A-Za-z0-9_.-]+)/$", s)
        if not m:
            continue
        name = m.group(1)
        if "Trae" in comment or "平台自带" in comment:
            out[name] = "platform"
        elif "第三方" in comment or "克隆" in comment or "大件" in comment:
            out[name] = "vendor"
        else:
            out[name] = "local"
    return out


def upstream_from_readme() -> set:
    """从 README「第三方与来源」节的反引号名里取上游 skill（支持 `easyeda-*` 通配）。"""
    if not README.is_file():
        return set()
    txt = README.read_text(encoding="utf-8", errors="replace")
    if "第三方与来源" not in txt:
        return set()
    sec = txt.split("第三方与来源", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"`([A-Za-z0-9_.\-*]+)`", sec))


def match_upstream(name: str, patterns: set) -> str:
    """README 里的名字 ↔ skill 目录名。支持 `easyeda-*` 通配与 `ponytail` 系（前缀+连字符）。"""
    for p in patterns:
        if p.endswith("*"):
            if name.startswith(p[:-1]):
                return p
        elif p == name:
            return p
        elif name.startswith(p + "-"):        # README 写 `ponytail`，实为 ponytail / -audit / -review
            return p + "-*"
    return ""


def provenance(name: str, fm: dict, local: dict, up: set) -> tuple:
    """→ (origin, evidence)。origin ∈ platform | vendor | upstream | self | unknown

    优先级（**显式标记 > 启发式**）：
      1. `.gitignore` 本地层 → platform / vendor（这是硬边界）
      2. frontmatter 顶层 `agent_created: true` → self
      3. frontmatter `metadata.source` / `official_repository` / `author` → upstream
      4. README 致谢里的名字（含 `easyeda-*` 通配）→ upstream
      5. metadata 内层 `agent_created: true` → self
      6. 都没有 → unknown（该补标签）

    为什么 2/3 要排在 4 前面：README 的通配 `easyeda-*` 会把**自研**的
    `easyeda-sch-audit-fix`（它带 agent_created: true）一并吞成"上游"——实测踩过。
    """
    if name in local:
        return local[name], ".gitignore 本地层"
    if re.fullmatch(r"true", fm.get("agent_created", "").strip(), re.I):
        return "self", "frontmatter agent_created: true"
    meta = metadata_of(fm)
    for k in ("source:", "official_repository:", "viewer_repo:", "author:"):
        m = re.search(r"%s\s*(\S+)" % re.escape(k), meta)
        if m:
            return "upstream", "frontmatter %s %s" % (k.rstrip(":"), m.group(1)[:60])
    hit = match_upstream(name, up)
    if hit:
        return "upstream", "README 致谢：%s" % hit
    if re.search(r"agent_created:\s*true", meta, re.I):
        return "self", "frontmatter metadata.agent_created: true"
    return "unknown", "无来源标记"


# ---------------------------------------------------------------- dead links

LINK_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|json|js|mjs|sh|diff|yaml|yml))`")
LOCAL_PREFIX = ("scripts/", "references/", "assets/", "workflows/")
# 工程 / 环境文件：正文提到它们是"叫你去读工程里的东西"，不是 skill 自带文件 → 不算死链
PROJECT_FILES = {
    "AGENTS.md", "CLAUDE.md", "README.md", "ROUTE.md", "LICENSE", "SKILL.md",
    "CMakePresets.json", "CMakeLists.txt", "compile_commands.json", "package.json",
    "CONTEXT.md", ".em_skill.json", "README.upstream.md", "PATCHES.md", "PATCHES.diff",
}
# 行级豁免：这一行在讲"你要产出什么"或"去工程里找"，其中的文件名不是 skill 自带文件
CREATE_VERBS = ("产出", "生成", "创建", "新建", "输出", "落盘", "保存", "交付", "清单",
                "write", "create", "generate", "produce", "output")
PROJECT_CTX = ("工程根", "工程目录", "项目根", "工作区", "工程里", "本工程", "目标工程")


def dead_links(skill_dir: Path) -> list:
    """正文引用、且**应当是 skill 自带**却找不到的文件。

    判据（保守，宁漏勿错）：
      · `scripts/…` `references/…` 这类 skill 本地路径 → 直接查存在性
      · 裸文件名 → 在 skill 目录内递归找、在仓库根找；都没有才算缺失
      · 工程/环境文件名（白名单）· 跨仓路径 · 「产出清单」与「工程内」两类行 → 整行不判
    """
    p = skill_dir / "SKILL.md"
    if not p.is_file():
        return []
    own = {f.name for f in skill_dir.rglob("*") if f.is_file()}
    root = {f.name for f in REPO.iterdir()}
    bad = set()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if any(v in line for v in CREATE_VERBS) or any(v in line for v in PROJECT_CTX):
            continue
        for raw in set(LINK_RE.findall(line)):
            if raw.startswith(("/", "http")) or raw in PROJECT_FILES:
                continue
            if raw.startswith(LOCAL_PREFIX):
                if not (skill_dir / raw).exists():
                    bad.add(raw)
                continue
            if "/" in raw:                      # 跨仓路径，判不了
                continue
            if raw in own or raw in root:
                continue
            bad.add(raw)
    return sorted(bad)


def is_forwarder(skill_dir: Path) -> bool:
    """薄壳转发件：正文只有一句「Call the Skill tool with X」——没有独立内容。"""
    p = skill_dir / "SKILL.md"
    if not p.is_file():
        return False
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n?(.*)$", txt, re.S)
    body = (m.group(1) if m else txt).strip()
    return len(body) < 200 and bool(re.search(r"call the skill tool", body, re.I))


# ---------------------------------------------------------------- overlap

def route_groups() -> dict:
    """解析 ROUTE.md §2 全部表格 → {任务类型: [skill 名]}。"""
    if not ROUTE.is_file():
        return {}
    txt = ROUTE.read_text(encoding="utf-8", errors="replace")
    if "## 2." not in txt:
        return {}
    sec = txt.split("## 2.", 1)[1].split("## 3.", 1)[0]
    groups: dict = {}
    for line in sec.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or cells[0].strip("`") in ("类型", ""):
            continue
        task = cells[0].strip("`")
        names = re.findall(r"`([a-z0-9][a-z0-9_-]*)`", cells[2])
        if names:
            groups.setdefault(task, []).extend(names)
    return {k: sorted(set(v)) for k, v in groups.items()}


def words(desc: str) -> set:
    toks = set(re.findall(r"[a-z][a-z0-9_+-]{2,}", desc.lower()))
    for seg in re.findall(r"[\u4e00-\u9fff]+", desc):        # 中文取 2-gram
        toks |= {seg[i:i + 2] for i in range(len(seg) - 1)}
    return toks - STOP


# ---------------------------------------------------------------- main

def main() -> int:
    local = local_layer()
    up = upstream_from_readme()
    groups = route_groups()
    routed = {n for v in groups.values() for n in v}

    rows = []
    for d in sorted(REPO.iterdir()):
        if not d.is_dir() or d.name in INFRA or not (d / "SKILL.md").is_file():
            continue
        fm = frontmatter(d)
        desc = desc_of(fm)
        origin, ev = provenance(d.name, fm, local, up)
        files = [f for f in d.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
        kb = sum(f.stat().st_size for f in files) // 1024
        rows.append({
            "name": d.name,
            "origin": origin,
            "evidence": ev,
            "lines": len((d / "SKILL.md").read_text(encoding="utf-8",
                                                    errors="replace").splitlines()),
            "files": len(files),
            "kb": kb,
            "desc": desc,
            "words": words(desc),
            "dead": dead_links(d),
            "forwarder": is_forwarder(d),
            "routed": d.name in routed,
            "tasks": [t for t, v in groups.items() if d.name in v],
        })

    order = {"platform": 0, "vendor": 1, "upstream": 2, "self": 3, "unknown": 4}
    rows.sort(key=lambda r: (order.get(r["origin"], 9), -r["lines"]))

    # 重叠：**全库两两比**，不局限在同一任务组内 —— 真风险正是"两个 skill 抢同一个活"，
    # 而它们常被登记在不同任务类型下（如 EDA 的 net-fanout 在"硬件/落图"、
    # audit-fix 在"硬件/审计"，同组比对永远碰不到面）。
    #
    # 打分用 **IDF 加权**而非 Jaccard：长 description 会把 Jaccard 稀释掉
    # （实测 EDA 那对真重叠被稀释到阈值以下）。只在 ≤RARE_DF 个 skill 里出现的词
    # 才算"特征词"，全库都有的套话（"需要/使用/当需要时使用"）零权重。
    df = {}
    for r in rows:
        for t in r["words"]:
            df[t] = df.get(t, 0) + 1

    def rare_shared(a: set, b: set) -> tuple:
        sh = {t for t in (a & b) if df.get(t, 99) <= RARE_DF}
        if not sh:
            return 0.0, []
        score = sum(1.0 / df[t] for t in sh)
        return score, sorted(sh, key=lambda t: (df.get(t, 99), t))

    overlaps = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            score, sh = rare_shared(a["words"], b["words"])
            if score >= OVERLAP_SCORE and len(sh) >= 2:
                overlaps.append((a["name"], b["name"], score, sh[:8],
                                 a["tasks"] or ["（未登记）"], b["tasks"] or ["（未登记）"]))
    overlaps.sort(key=lambda x: -x[2])

    dead = [r for r in rows if r["dead"]]
    # 孤儿 = 公开层 skill 却没登记进 ROUTE.md §2（发布出去也路由不到）。
    # 平台自带 / 第三方大件本来就不进公开路由表 → 单列，不算缺陷。
    orphan = [r for r in rows if not r["routed"] and r["origin"] not in ("platform", "vendor")]
    unrouted = [r for r in rows if not r["routed"] and r["origin"] in ("platform", "vendor")]
    forwarders = [r for r in rows if r["forwarder"]]
    untagged = [r for r in rows if r["origin"] == "unknown"]

    if "--json" in sys.argv:
        print(json.dumps({"skills": [{k: v for k, v in r.items() if k != "words"}
                                     for r in rows],
                          "overlaps": overlaps,
                          "orphan": [r["name"] for r in orphan],
                          "dead": {r["name"]: r["dead"] for r in dead}},
                         ensure_ascii=False, indent=2))
        return 1 if (dead or orphan or overlaps) else 0

    L = []
    A = L.append
    A("# SKILL 审计报告")
    A("")
    A("> 由 `tools/skill_audit.py --write` 生成（只读审计，不下判决）。")
    A("> 删 / 留由人拍板；改来源标签后重跑本脚本。")
    A("")
    A("共 **%d** 个 skill · 死链 **%d** · 公开层孤儿 **%d** · 重叠对 **%d** · 薄壳 **%d** · 待标来源 **%d**"
      % (len(rows), len(dead), len(orphan), len(overlaps), len(forwarders), len(untagged)))
    A("")
    A("## 1. 总表（按来源分档，档内按 SKILL.md 行数降序）")
    A("")
    A("| skill | 来源 | 依据 | 正文行 | 文件 | KB | 已登记路由 |")
    A("|---|---|---|---:|---:|---:|---|")
    for r in rows:
        A("| `%s` | %s | %s | %d | %d | %d | %s |"
          % (r["name"], r["origin"], r["evidence"], r["lines"], r["files"], r["kb"],
             "✓" if r["routed"] else ("**✗ 孤儿**" if r["origin"] not in ("platform", "vendor")
                                      else "— 不进公开表")))
    A("")
    A("## 2. 重叠对（**全库两两**比，特征词 IDF 加权分 ≥ %.1f 且共同特征词 ≥ 2）" % OVERLAP_SCORE)
    A("")
    A("> **特征词** = 只在 ≤%d 个 skill 的描述里出现的词 —— 全库都有的套话（\"需要/使用/"
      "当需要时使用\"）零权重。\n> 重叠 ≠ 必删：父子关系（`ponytail` / `-audit` / `-review`）属正常分层；"
      "要看**职责词**是否真撞车。" % RARE_DF)
    A("")
    if overlaps:
        A("| A | B | 分 | 共同特征词 | A 的任务类型 | B 的任务类型 |")
        A("|---|---|---:|---|---|---|")
        for a, b, sc, sh, ta, tb in overlaps:
            A("| `%s` | `%s` | %.1f | %s | %s | %s |"
              % (a, b, sc, "、".join(sh), "、".join(ta), "、".join(tb)))
    else:
        A("（无）")
    A("")
    A("## 3. 薄壳转发件（正文只有一句「Call the Skill tool with X」，无独立内容）")
    A("")
    if forwarders:
        for r in forwarders:
            A("- `%s`（%d 行，%d KB）→ 建议并入其指向的真身" % (r["name"], r["lines"], r["kb"]))
    else:
        A("（无）")
    A("")
    A("## 4. 死链（正文引用、应当是 skill 自带却找不到的文件）")
    A("")
    if dead:
        for r in dead:
            A("- `%s` → %s" % (r["name"], ", ".join("`%s`" % x for x in r["dead"])))
    else:
        A("（无）")
    A("")
    A("## 5. 公开层孤儿（在库、来源是上游/自研，却没登记进 ROUTE.md §2）")
    A("")
    if orphan:
        for r in orphan:
            A("- `%s`（来源 %s）→ 发布出去也路由不到" % (r["name"], r["origin"]))
    else:
        A("（无）")
    A("")
    A("## 6. 未进公开路由表（平台自带 / 第三方大件 —— 这是**正常**的，列出来只为看清边界）")
    A("")
    for r in unrouted:
        A("- `%s`（%s）" % (r["name"], r["origin"]))
    A("")
    A("## 7. 待补来源标签")
    A("")
    if untagged:
        A("frontmatter 缺 `metadata.source`（上游）或 `agent_created: true`（自研），")
        A("无法自动判源 —— 补上后本表自动转正：")
        A("")
        for r in untagged:
            A("- `%s`" % r["name"])
    else:
        A("（无）")
    text = "\n".join(L) + "\n"

    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print("已写入 %s（%d 个 skill）" % (OUT, len(rows)))
    else:
        print(text)

    print("\n[小计] 死链 %d · 公开层孤儿 %d · 重叠对 %d · 薄壳 %d · 待标来源 %d"
          % (len(dead), len(orphan), len(overlaps), len(forwarders), len(untagged)))
    # 退出码只认**硬缺陷**：公开层 skill 没进路由表 = 发布出去也路由不到。
    # 死链 / 重叠是启发式信号，报出来给人判，不据此判失败。
    return 1 if orphan else 0


if __name__ == "__main__":
    raise SystemExit(main())
