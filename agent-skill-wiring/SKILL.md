---
name: agent-skill-wiring
description: 把新装的 AI 客户端接进统一体系——skill 目录做 Junction/symlink 指向共享库 ~/.ai-skills/，各层补 AGENTS.md / .trae/rules / CLAUDE.md 三扇规则门。当出现「某客户端读不到 skill」「新装了 Trae / Qoder / Codex / 豆包 类工具」「同一个项目各客户端行为不一致」「接线好像断了」时使用。
agent_created: true
metadata:
  version: "1.1.0"
  note: "2026-09-30 公开化改写：去本机绝对路径；工作台脚本引用改指本库 tools/skillman.py。"
---

# 跨客户端接线（skill 库 + 规则门）

> 设计说明：见本库 `README.md`「触发链」与 `templates/`。
> 挂接与补挂：`python tools/skillman.py install [--apply]`（默认干跑）。
> 体检：`python tools/skillman.py doctor`（退出码 0 才算好）。

## 一、skill 怎么接：一条铁律 + 两种接法

**铁律：资产只放一份。** 共享库 = `~/.ai-skills/`；任何端**不许另装拷贝**。

先看目标端的 skills 目录里有没有**官方机制文件**（`.system/`、`.default/`、`market/`、`skills.json`…）：

| 情况 | 接法 | 典型实例 |
|---|---|---|
| 干净 / 目录不存在 | **整体 Junction**：整个 skills 目录 → `~/.ai-skills/` | `~/.trae-cn/skills`、`~/.codebuddycn/skills`、`~/Doubao/skills` |
| 目录里有官方机制文件 | **逐项挂载**：每个 skill 单独建 Junction，机制目录原样保留 | `~/.codex/skills/<each>`（留 `.system/`）、`~/.fittencode/skills/external/<each>`（留 `.default/`）、`~/.marvis/skills/custom/<each>` |
| 该工具没有 skills 概念 | 不接，只做规则门 | Qoder |

整体 Junction 的写法 —— **踩过的坑**：别用 `subprocess.run([...])` 传参数列表，cmd 内建命令
会把引号吞掉、报 `无效参数 - "Users"`：

```python
import subprocess
cmd = 'mklink /J "%s" "%s"' % (link, target)   # target = <共享库路径>（如 ~/.ai-skills）
subprocess.run(cmd, shell=True)                 # shell=True + 完整字符串才稳
```

`mklink /J` 建 Junction **不需要管理员权限**；建完 `os.readlink()` 会返回 `\\?\C:\...`（比较目标时要剥前缀）。

**动手前必做**：目标端原 skills 目录整个复制到备份目录（如 `~/.local/skills-backup-<YYYYMMDD>/`）。
里面若藏着共享库没有的 skill，**先合并进共享库再改接**——合并时重名项要 `filecmp` 比对内容
择新版（并看目录里有没有对方缺的文件），别盲覆盖。

## 二、规则怎么接：每层三扇门

各家读的入口文件名不同，所以**每层目录放三份薄转发**（只指路、不复制规则）：

| 门 | 谁读 | 要点 |
|---|---|---|
| `AGENTS.md` | ZCode · WorkBuddy · WorkBuddy AI · CodeBuddy · CodeBuddy CN · Qoder · Codex · FittenCode · Marvis | 跨工具通用规范 |
| `.trae/rules/project_rules.md` | Trae Work CN / TraeCode CN | **自动读、不需要开关**——Trae 唯一可靠入口 |
| `CLAUDE.md` | Claude Code / TraeCode 系 | 转发层，读到这里转入 `AGENTS.md` |

**最容易漏的一条**：Trae 读 `AGENTS.md` 要在「设置 → 规则 → 导入设置」里**手动打开
"将 AGENTS.md 包含在上下文中"**（AI 做不了）；所以项目根没有 `.trae/rules/` 时，Trae 在这个
项目里等于瞎的。

**每扇门顶部还必须带 `[MUST] 开工前置`**（指到 `ROUTE.md`：拿证 → 判类 → 装 skill →
输出 `[ROUTE]` 声明再开工）——**手写的 `AGENTS.md` 也不能漏**。门模板：`templates/project-door.md`。

## 三、验收（别只看目录存在）

1. **探针穿透**：从该端路径读 `ponytail/SKILL.md`，字节数要与共享库一致——"目录在"不等于"通"。
2. 跑 `python tools/skillman.py doctor`：接线 + 穿透探针 + skill 可调用性 + 路由一致性 + 全局门。
3. **未验证就标未验证**：某些端（Trae 市场缓存、豆包）是否真的重扫了 skill 列表，需打开软件
   肉眼确认一次，别把"文件接上了"说成"agent 能用了"。

## 四、顺手要做的维护

- 合并外部来源的 skill 时，查跨 skill 相对引用（`../shared/...`）和**上游作者的机器绝对路径**
  （如 `/home/leo/work/...`）——skill 被平铺到 `skills/<名>/` 后这些引用会全部指空。
- 没有 `SKILL.md` 的目录会被各端忽略（例外：某些端 skill 依赖的机制目录如 `shared/`，
  必须与它们**同层**保留）。
- 新增/删除客户端后，同步 `tools/skillman.py` 的 `CLIENTS` 表（与全局门候选 `GLOBAL_DOORS`）。

## 五、本库配套工具

| 命令 | 用途 |
|---|---|
| `python tools/skillman.py install` | 探测本机客户端 → 挂接 skills 目录 + 装全局门（干跑；`--apply` 落地） |
| `python tools/skillman.py doctor` | 体检：接线 / 探针穿透 / skill 可调用性 / 路由 / 全局门。**退 0 才算好** |
| `python tools/skillman.py sync` | 更新本库（git pull）+ 重挂各端 + 体检 |

## ⚠️ 加/改 skill 之后必做

**共享库 `~/.ai-skills/` 是唯一安装点；但「逐项挂载」的 3 端不会自动同步。**

- **整体 Junction 端**（WorkBuddy · WorkBuddy AI · CodeBuddy · CodeBuddy CN · Trae CN · 豆包 …）
  → 共享库加 skill **立刻可见，无需动作**。
- **逐项挂载端**（Codex 留 `.system/` · FittenCode 留 `.default/` · Marvis）→
  **新增 skill 后必须逐项补挂**（实测无自动同步）。补挂命令：

```bash
python tools/skillman.py install --apply     # 幂等：只补缺的，其余不动
```

改已有 skill：**只改共享库那一份**（各端是链接，改完立刻全端生效）；
若某端条目是**拷贝**而非链接（`doctor` 会报异常），那端会分叉——删掉重新挂。

**加/改 skill 的完整规程**见 `ROUTE.md` §2.3「环境/改技能」。
