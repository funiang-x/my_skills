# my_skills — 嵌入式 AI Skill 集

一套「让 AI 在做嵌入式软硬件流程时**自动取用正确 skill**」的技能仓库。
覆盖 **选型 → 原理图 → 固件编码 → 烧录调试 → 工程方法** 的完整链路，
自带**任务路由协议**（AI 开工先声明用哪个 skill）与**管理工具**（一键装到各 AI 客户端）。

## 快速开始

```bash
git clone https://github.com/funiang-x/my_skills
cd my_skills
python tools/skillman.py install          # 干跑：看看会做什么
python tools/skillman.py install --apply  # 落地：挂接各 AI 客户端 + 装全局门
python tools/skillman.py doctor           # 体检：接线 / skill 可调用性 / 路由一致性
```

装好后，在任意支持 skill 的 AI 客户端里正常干活即可——AI 会按 `ROUTE.md`
的装配清单路由到对应 skill，并在动手前输出 `[ROUTE]` 声明给你看。

## AI 为什么"自动"用对 skill（触发链）

1. **全局门**（`install` 时写入各客户端）：用户级规则里一小段指针——「开工先读 `ROUTE.md`」
2. **`ROUTE.md`**：任务类型 ↔ skill 装配表——AI 判类后知道该装谁、该读什么
3. **路由声明**：AI 动手前必须先贴 `[ROUTE]` 行——你一眼看到它调了什么、读了什么
4. **开工证**（`tools/preflight.py`）：把该读的条款**正文**打印出来 + 发证；
   **skill 内容一改，证自动作废**（绑定 sha256），逼 AI 重读
5. **硬闸门**（`hooks/skill_gate.py`，可选装）：没证就改本库 / 跑库内脚本 → 直接拦下（退出码 2）

> 为什么不用"平台自动触发"兜底：各客户端触发机制不同、多数靠模型自行判断——不可预期。
> 本仓库把控制权收回到**文件 + 显式声明**：换任何客户端，结果一致。

## 收录什么

| 链路 | skill |
|---|---|
| 硬件选型 | `hardware-solution`（架构 / 电源树 / 器件 / BOM 风险） |
| 原理图（嘉立创 EDA） | `easyeda-schematic-net-fanout`（落图规程）· `easyeda-api`（桥 + API）· `easyeda-viewer`（离线看图）· `easyeda-sch-audit-fix`（审计修补） |
| 固件（STM32 + J-Link） | `stm32-hal-cli-flow`（构建/烧录/RTT CLI）· `stm32-hang-triage`（崩溃取证） |
| 工程方法 | `ponytail`（+`-audit`/`-review`，反过度工程）· `tdd` · `codebase-design` · `diagnosing-bugs` · `grilling` 系（需求拷问）· `handoff` · `writing-for-agents` · `resolving-merge-conflicts` |
| 环境管理 | `install-github-skill`（装技能规程）· `agent-skill-wiring`（跨客户端接线） |

### 嘉立创 EDA 链的前置（一次准备）

`easyeda-*` 四件套驱动的是**运行中的**嘉立创 EDA 专业版——装完 skill 后还需要两步 GUI 操作：

1. 在 EDA「扩展管理器」里安装 [Run API Gateway](https://jlc-ext.com/item/oshwhub/run-api-gateway) 扩展，
   并**勾选"允许外部交互"**（菜单栏出现「API Gateway」= 已加载；**它不在就不可能做任何 AI↔EDA 操作**）；
2. 在 `easyeda-api/` 目录里跑一次 `npm install`（桥服务的 Node 依赖）。

链路：**AI → `easyeda-api` skill → Bridge Server(49620-49629) → Run API Gateway 扩展 → 嘉立创 EDA 专业版**。
⚠️ 扩展**不会自动重连**：EDA 先于桥打开、或桥中途重启时，在 EDA 里重载一次扩展（或重启 EDA）。

## 三条命令

| 命令 | 作用 |
|---|---|
| `install` | 探测本机已装的 AI 客户端 → 挂接 skills 目录（Junction / symlink）→ 装全局门 → 报告 |
| `sync` | 更新本库（`git pull`）→ 重挂各端 → 体检 |
| `doctor` | 只读体检：接线完好 / skill 可调用（frontmatter 合法）/ 路由无死链 / 全局门在位 |

两个约定：

- **默认干跑**——先打印计划，`--apply` 才真正落地（动了你机器上的东西都会留备份说明）；
- **不碰你没装的东西**——只处理探测到的客户端目录。

## 第三方与来源（致谢）

- `easyeda-*` 四件套：[easyeda/easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill) · [easyeda/easyeda-enhanced-schematic-skill](https://github.com/easyeda/easyeda-enhanced-schematic-skill) · [easyeda/easyeda-viewer](https://github.com/easyeda/easyeda-viewer)（嘉立创 EDA 官方，MIT）
- `ponytail` 系：[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)（MIT，本库版有平台适配小改）
- 方法层（`tdd` / `codebase-design` / `grilling` / `grill-me` / `grill-with-docs` / `handoff` / `writing-for-agents` / `diagnosing-bugs` / `resolving-merge-conflicts`）：[mattpocock/skills](https://github.com/mattpocock/skills)（MIT）
- 汇报 PPT 链：推荐直接安装上游 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)（本库不含）

## 维护

- **只读发布**：欢迎 issue 反馈；不接受 PR（保持单方维护的一致性）
- 加 / 改 / 退 skill 的规程：`ROUTE.md` §2.3「环境/改技能」
- 本库采用「公开层 + 本地层」：本机私有的扩展 skill 与实战台账不进本仓（见 `.gitignore` 注释）
