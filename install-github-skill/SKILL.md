---
name: install-github-skill
description: "把 GitHub 上的第三方 Agent Skill / 插件仓库安全地审计并安装到本机共享 skill 库（正本 ~/.ai-skills/）。当用户给出一个 GitHub 仓库链接并说‘安装这个技能/插件/skill’，或要求把某个开源仓库变成可用技能时使用。"
agent_created: true
metadata:
  version: "1.2.0"
  note: "2026-09-30 公开化改写：去本机绝对路径与私有插件路径；收口流程改指 ROUTE.md §2.3。"
---

# 从 GitHub 安装第三方技能

把"给我个仓库链接 → 变成能用的技能"这件事标准化：**先审计，再适配，最后安装**。

## 环境提示（Windows + Bash）

- 遇到 `command not found` 再补 PATH，别预先折腾；本机若有本地代理，curl 走代理可达 GitHub。
- **一个客户端跑完整流程**：从 Bash 里调 PowerShell 可能被安全钩子拦（反之亦然）——
  要用哪家就在哪家把命令跑完，别来回跨。

## 步骤 1：下载仓库

**优先用 tarball，不要用 `git clone`**（clone 较容易中途被 SIGTERM；小仓 tarball 几秒）：

```bash
mkdir -p "<工作区>/_tmp" && cd "<工作区>/_tmp"
curl -sL --max-time 180 -o nb.tar.gz "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main" -w "HTTP:%{http_code} SIZE:%{size_download}\n"
mkdir -p nb && tar -xzf nb.tar.gz -C nb
```

分支名不确定时先试 `main`，失败换 `master`。下载完先 `find . -type f -printf "%8s  %p\n" | sort -k2` 看全貌。

## 步骤 2：安全审计（不可跳过）

审计要点（纯静态文本分析，**绝不执行被审内容**）：

| 检查 | 手段 |
|------|------|
| 危险关键词全扫 | `grep -rnE "curl\|wget\|eval \|exec\(\|subprocess\|os\.system\|popen\|sudo\|chmod\|rm -rf\|base64\|/dev/null\|nohup" .` |
| URL / 外联 | `grep -rhoE "https?://[^ )\"'\`]+" . \| sort -u` |
| Base64 载荷 | `grep -rnE "[A-Za-z0-9+/]{40,}={0,2}" .` |
| 敏感路径 | `grep -rnE "~/\.ssh\|\.aws\|\.env\|api[_-]?key\|secret\|token\|password\|credential" .` |

（装了官方插件市场的 `skills-security-check` 的话，可直接读它目录里的 `SKILL.md` 走完整流程。）

**定级关键**：区分「skill 自动执行」与「仅给 Agent 能力」。前者才是投毒风险：
- 优先精读这几个文件：`hooks/*`（会话启动自动跑）、`scripts/*.sh`、`scripts/*.py`、`tests/*.py`。
- 判定规则：`rm -rf` 目标是它自己的安装目录 → 安全；`subprocess` 只跑自家脚本 → 安全；
  "让 Agent 去联网下载资料到项目目录" → 属 Agent 行为需用户审批，算 P1 提示不算 P0。

## 步骤 3：安装到共享库正本

目标：`~/.ai-skills/<skill-name>/`（用户级，跨客户端可用；各端经 Junction 共享）。

```bash
SRC="<解压目录>"; DEST="$HOME/.ai-skills/<skill-name>"
mkdir -p "$DEST"
cp -r "$SRC/skills/<skill-name>/." "$DEST/"                        # skill 主体
mkdir -p "$DEST/agents" && cp "$SRC/agents/"*.md "$DEST/agents/"   # 仓库根的 agent 文件（若有）
```

**不要运行上游的 `install.sh`** —— 它们通常写 `~/.claude`、`~/.codex`，碰其他客户端的配置。手工复制更干净。

### 例外：目标不是「纯 skill 仓」而是「CLI + installer + 自带 skill」的产品

有些项目（例：`easyeda-agent`）本体是 **CLI + daemon + 连接器**，skill 只是附赠，
installer 是装 CLI 的**唯一正规途径**——这时**不能**照上面"手工复制"办，但也不能裸跑 installer：

| 坑 | 后果 | 对策 |
|---|---|---|
| installer 默认把 skill 写进 `~/.codex/skills`、`~/.claude/skills`、`~/.agents/skills` | 若那些目录是宿主共享库的 **Junction/逐项挂载端** → **双头管理打架**（`skillman` 以为是自己管的） | **查它有没有"跳过 skill"开关**（`EASYEDA_INSTALL_SKILLS=none` 这类）→ 装上，**只装 CLI** |
| 默认走第三方镜像（如 `gh-proxy.com`） | 信任边界外移 | 查有没有关镜像的开关（`EASYEDA_GITHUB_PROXY=off`） |
| 未检测到客户端时**默认创建** `~/.codex` / `~/.claude` 空目录 | 污染家目录 | 同上，用跳过开关 |
| 它自带 `update` 子命令（如 `easyeda update`） | **本地改动会被覆盖** → 你的适配全丢 | **一个字都别改上游文件**；适配写进宿主工作台（`machine.md` / `LOCAL.md`）；升级 = 重下它的 skill 包覆盖 |
| 它自己的 skill 目标目录 ≠ 你的共享库 | 不冲突，但 10 端看不到 | 从 Release 下它的 skill 包（`skills.tar.gz` 之类）→ 校验 sha256 → 解出放进 `~/.ai-skills/<name>/` → `skillman install --apply` |

**统一姿势**：`installer 只装 CLI（带跳过开关）` → `手工把 skill 放进共享库` → `skillman 挂 10 端` → `登记路由` → `本机适配写进工作台`。
**别忘了划层**：这类第三方大件通常该进 `.gitignore` 的**本地层**（不进公开仓），与 `ppt-master` 同档。

装完按 `ROUTE.md` §2.3「环境/改技能」收口：定任务类型 → `python tools/skillman.py install --apply`
补挂逐项端 → 登记路由 → `python tools/skillman.py doctor` 退出码 0。

## 步骤 4：适配（上游几乎总有问题）

| 常见问题 | 处理 |
|---------|------|
| `SKILL.md` 里用 `../../agents/xxx.md` 引用仓库根目录 | 复制到技能目录内后改成 `agents/xxx.md`（相对技能根） |
| 命令写成 `python3 xxx.py` | Windows 无 `python3`，改成 `python`（或用你的托管解释器全路径） |
| `hooks/session-start` | 多数客户端不加载 Claude Code 的 hook，跳过；其作用只是会话启动提醒 |
| 依赖第三方 Python 包 | 装到隔离 venv（`python -m venv <venv 目录>`），再 `pip install <pkg>` |

改动后用 `diff` 留证，并在报告里逐条说明改了什么、为什么 —— **不要静默修改上游内容**。

## 步骤 5：验证 + 报告

```bash
find "$DEST" -type f | sed "s|.*/<skill-name>/||" | sort   # 清单核对
python -m py_compile "$DEST"/scripts/*.py                  # 脚本语法（无 scripts 则跳过）
```

报告（写成 md 交付）必须包含：审计评级与依据、安装清单、**为适配做的每一处改动**、
**本机环境改动记录（含回滚方式）**、未就绪的依赖及影响面。

## 已知环境硬坑（别重复踩）

| 坑 | 结论 |
|----|------|
| `msys64` 的 `pacman.exe` | 在 git-bash 里**跑不通**：卡死在数据库同步，`timeout` 也杀不掉。要装 MSYS2 包只能让用户在 MSYS2 UCRT64 终端里手工跑 |
| `weasyprint` | Windows 上除了 pip 包还需要系统 GTK（Pango/cairo/gobject）。装不上的话别硬啃，直接告知用户并给替代方案 |
| `git clone` | 容易 SIGTERM，改用 codeload tarball |

> **收尾提示**：装完把新目录纳入本库的版本管理（commit 进 `~/.ai-skills` 仓）；
> `_tmp` 只作审计暂存，交报告后清理。
