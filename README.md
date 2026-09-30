# my_skills — 嵌入式 AI Skill 集

一套「让 AI 在做嵌入式软硬件流程时**自动取用正确 skill**」的技能仓库。
覆盖 **选型 → 原理图 → 固件编码 → 构建/烧录/调试 → 工程方法** 的完整链路，
自带**任务路由协议**（AI 开工先声明用哪个 skill）与**管理工具**（一键装到各 AI 客户端）。

## 目录地图（先看这个，再往下看文件列表）

**根目录只有三类东西**，一眼分辨：

| 类型 | 怎么认 | 有哪些 |
|---|---|---|
| **skill** | 目录里有 `SKILL.md` | 下面那张表的 **23 个** |
| **库基础设施** | 目录里**没有** `SKILL.md` | `hooks/`（硬闸门）· `templates/`（门模板）· `tools/`（管理工具） |
| **根文件** | — | `ROUTE.md`（用哪个 skill）· `WORKFLOW.md`（按什么阶段做）· **`PREREQUISITES.md`（要跑起来还差什么）** · `AGENTS.md`（agent 入口）· `README.md` · `LICENSE` · `.gitignore` |

> **为什么 23 个 skill 平铺在根目录、不能分文件夹？**
> skill 发现机制要求 `<skills目录>/<名字>/SKILL.md` —— **只有一层**。
> 放进 `skills/eda/xxx/` 客户端就**找不到**了。所以"看着零散"是格式的代价，不是没整理。
> （17 → 23：2026-09-30 六个原「平台自带、非 Trae 用户拿不到」的 skill
> —— `build-cmake` / `flash-jlink` / `debug-jlink` / `serial-monitor` / `serial-shell` / `static-analysis`
> —— 由**自研替代版**进仓，本仓自此对 JTAG/CMake/串口/静态分析**自洽**。）

> **23 是"公开层"的数，不是你机器上看到的数。**
> 本机另外挂着 **2 个本地层** skill（第三方大件 `easyeda-agent` · `ppt-master`，见 `.gitignore` 的分界线）——
> 它们与公开层**一视同仁**地挂到各客户端，只是**不随本仓发布**。
> 所以本机含 `SKILL.md` 的一级目录是 **25 个**。
> 看到"目录比 23 多"不是没整理，是分层；**判据永远是 `.gitignore`**，不是数数。

### 两份文档的分工（别混）

| 文档 | 回答 | 形态 |
|---|---|---|
| `ROUTE.md` | **该用哪个 skill** | 任务类型 ↔ skill 装配表（任务视图） |
| `WORKFLOW.md` | **按什么阶段做** | 阶段 → 交付物 → 验收判据（阶段视图） |

两者**互为复述**（同一批 skill，两种排法），所以有机器检查防漂：`skillman.py doctor`
会校验 `WORKFLOW.md` 里的 skill 名 ⊆（`ROUTE.md` §2 ∪ `.gitignore` 本地层名单）。

## 按你要做的事，找该装哪个 skill

> 下面「按链路分组」是**按类别**排的；这一节是**按你要做的事**索引——
> **不知道 skill 叫什么名字时，从这里查。**
> 带 ⚠️ 的是**本地层**（不随本仓发布，需自备；见 [`PREREQUISITES.md`](PREREQUISITES.md) §3），
> **没装也各有降级路径**。

| 你要做的事 | 装哪个 skill |
|---|---|
| 选 MCU / 选器件 / 比方案 | `hardware-solution` |
| 画 / 改原理图、改网表、跑 DRC | `easyeda-api`（+ `easyeda-agent` ⚠️ 加强） |
| 离线看图纸、落图后视觉复核 | `easyeda-viewer` |
| 写 / 改**任何**代码（含脚本） | `ponytail`（**强制，无例外**） |
| 审查整个仓的过度工程 | `ponytail-audit`（**点名触发**） |
| 只审查这次改了什么 | `ponytail-review`（**点名触发**） |
| 构建固件 / 看体积 / 跑单测 | `stm32-hal-cli-flow` |
| 通用 CMake 工程构建 / 定位产物 | `build-cmake` |
| 烧录、看 RTT 日志 | `flash-jlink` |
| 板子崩了 / 卡死 / HardFault | `stm32-hang-triage` |
| GDB 取证（寄存器 / 栈回溯） | `debug-jlink` |
| 抓串口日志 / 交互 shell | `serial-monitor` / `serial-shell` |
| 静态分析（cppcheck / clang-tidy） | `static-analysis` |
| 通用 bug 定位（复现 → 收紧 → 定位） | `diagnosing-bugs` |
| 想先写测试再写实现 | `tdd` |
| 设计模块接口、嫌接口太碎 | `codebase-design` |
| 需求没想清楚，想被拷问一轮 | `grilling` |
| 把当前会话交给另一个 agent | `handoff` |
| 写 skill / 写 `AGENTS.md` | `writing-for-agents` |
| 解 git 合并 / 变基冲突 | `resolving-merge-conflicts` |
| 从 GitHub 装一个新 skill | `install-github-skill` |
| 新装了 agent、读不到 skill | `agent-skill-wiring` |
| 做 / 改汇报 PPT | `ppt-master` ⚠️ |

### 23 个 skill 按链路分组

| 链路 | 干什么 | 目录名 |
|---|---|---|
| **硬件选型** | 需求 → 候选对比 → 选型结论 | `hardware-solution` |
| **原理图**（嘉立创 EDA） | 桥 + API 参考（落图主链） | `easyeda-api` |
| | 离线看图 / 落图视觉复核 | `easyeda-viewer` |
| **固件**（STM32 + J-Link） | 构建 / 烧录 / RTT / 体积 / 单测（自有模板工程体系） | `stm32-hal-cli-flow` |
| | 崩溃 / 卡死 / 静默死锁取证 | `stm32-hang-triage` |
| **工具链**（通用，2026-09-30 自研进仓） | 通用 CMake 构建 / 产物定位 | `build-cmake` |
| | J-Link 烧录 / 校验 / RTT | `flash-jlink` |
| | J-Link GDB Server / 批量取证 | `debug-jlink` |
| | 串口日志抓取（含等待/摘要） | `serial-monitor` |
| | 串口交互 shell / 批量命令 | `serial-shell` |
| | 静态分析包装（cppcheck / clang-tidy） | `static-analysis` |
| **工程方法**（语言无关） | 反过度工程 + 全仓审计 + 只查 diff | `ponytail` · `ponytail-audit` · `ponytail-review` |
| | 测试驱动开发 | `tdd` |
| | 深模块设计词汇 | `codebase-design` |
| | 通用 bug 诊断循环 | `diagnosing-bugs` |
| | 需求 / 方案拷问 | `grilling` |
| | 会话交接 | `handoff` |
| | 写 agent 文档（skill / AGENTS.md） | `writing-for-agents` |
| | 解 git 合并 / 变基冲突 | `resolving-merge-conflicts` |
| **环境管理** | 从 GitHub 装 skill（含安全审计） | `install-github-skill` |
| | 跨客户端接线 | `agent-skill-wiring` |

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

> ✅ **公开层 23 个 skill，clone + install 即可全流程开工**（STM32 + J-Link + 嘉立创 EDA 主链自洽）。
> 还需自备的只有两类**可选件**：真工具链（J-Link / arm-gcc / cmake / Node / pyserial，缺了各有降级路径）
> 与两个第三方大件 skill（`easyeda-agent` ⚠️ / `ppt-master` ⚠️）——
> 逐项清单见 **[`PREREQUISITES.md`](PREREQUISITES.md)**（**先读那份再动手**）。

## AI 为什么"自动"用对 skill（触发链）

1. **全局门**（`install` 时写入各客户端）：用户级规则里一小段指针——「开工先读 `ROUTE.md`」
2. **`ROUTE.md`**：任务类型 ↔ skill 装配表——AI 判类后知道该装谁、该读什么
3. **`WORKFLOW.md`**：阶段 ↔ 交付物 ↔ 验收判据——判不出"现在在哪个阶段"时读它
4. **路由声明**：AI 动手前必须先贴 `[ROUTE]` 行——你一眼看到它调了什么、读了什么
5. **开工证**（`tools/preflight.py`）：把该读的条款**正文**打印出来 + 发证；
   **skill 内容一改，证自动作废**（绑定 sha256），逼 AI 重读
6. **硬闸门**（`hooks/skill_gate.py`，可选装）：没证就改本库 / 跑库内脚本 → 直接拦下（退出码 2）

> 为什么不用"平台自动触发"兜底：各客户端触发机制不同、多数靠模型自行判断——不可预期。
> 本仓库把控制权收回到**文件 + 显式声明**：换任何客户端，结果一致。
> 在此之上，各 skill 的 `description` 都按"原生触发友好"打磨过——支持自动触发的客户端**两条腿都能走**。

## 本仓之外还有两个（**本地层**，走 `.gitignore`，不进本仓）

| 目录 | 是什么 | 为什么不在仓里 |
|---|---|---|
| `easyeda-agent` | 落图 / 布局 / 布线的 **CLI 化规程**（第三方，MIT）—— `硬件/落图` 的加强项；**没装也能落图**（走 `easyeda-api` 自带规程） | 自带 `easyeda update` 自更新，本地改动会被覆盖；且是第三方大件 |
| `ppt-master` | 汇报 PPT 链（第三方，84 MB / 13,000 文件） | 体量大，建议直接装上游 |

> 它们仍由 `skillman` 统一挂到各客户端（与进仓的 skill 一视同仁），只是**不随本仓发布**；
> **缺失时 `doctor` 只警告**。装法见 [`PREREQUISITES.md`](PREREQUISITES.md) §3。
> （另有平台机制目录 `shared/`——Trae CN 平台自带 skill 的公共依赖，本库已不再引用。）

### 嘉立创 EDA 链的前置（一次准备）

`easyeda-*` 驱动的是**运行中的**嘉立创 EDA 专业版——装完 skill 后还需要两步 GUI 操作：

1. 在 EDA「扩展管理器」里安装 [Run API Gateway](https://jlc-ext.com/item/oshwhub/run-api-gateway) 扩展，
   并**勾选"允许外部交互"**（菜单栏出现「API Gateway」= 已加载；**它不在就不可能做任何 AI↔EDA 操作**）；
2. 在 `easyeda-api/` 目录里跑一次 `npm install`（桥服务的 Node 依赖）。

链路：**AI → `easyeda-api` skill → Bridge Server(49620-49629) → Run API Gateway 扩展 → 嘉立创 EDA 专业版**。
⚠️ 扩展**不会自动重连**：EDA 先于桥打开、或桥中途重启时，在 EDA 里重载一次扩展（或重启 EDA）。

### 另一条链路：easyeda-agent（**可选加强**）

EDA 生态里的 [zhoushoujianwork/easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent)（MIT）——
它自带 CLI + daemon + **自己的** EDA 连接器 + **自己的** skill：

```
AI → 它的 skill → easyeda CLI/daemon → EDA Agent Connector(.eext) → EDA
```

主打 typed actions（布局规划 `layout-plan`、PCB 布线、丝印整理、PDF 建库等）。

- **怎么装**：CLI 用它的官方 installer（**先下载审阅**，别 `irm | iex`），
  且**必须带 `EASYEDA_INSTALL_SKILLS=none`** —— 否则它会把 skill 写进客户端的 skills 目录，
  与本库 `skillman` 的「逐项挂载」机制打架。skill 单独放进本库目录，由 `skillman` 统一挂各端。
- **它是本地层**：走 `.gitignore` 的第三方大件（**不进本仓**）；升级 = 重下 `skills.tar.gz` 覆盖目录。
- **本机适配不改上游文件**（它自带 `easyeda update`，改了会被覆盖）。
- 环境要求：EasyEDA Pro **V4**（推荐 V4.1.60+）+ 连接器 `.eext` + 工程开「允许外部交互」。

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

- `build-cmake` / `flash-jlink` / `debug-jlink` / `serial-monitor` / `serial-shell` / `static-analysis`：
  **自研**（2026-09-30 起替代原平台自带版本，进公开层；脚本纯标准库，除 `pyserial` 外零第三方依赖）。
- `easyeda-*` 两件套：[easyeda/easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill) · [easyeda/easyeda-viewer](https://github.com/easyeda/easyeda-viewer)（嘉立创 EDA 官方，MIT）。
- `easyeda-agent`（本地层，不进本仓）：[zhoushoujianwork/easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent)（MIT）
- `ponytail` 系：[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)（MIT，本库版有平台适配小改）
- 方法层（`tdd` / `codebase-design` / `grilling` / `handoff` / `writing-for-agents` / `diagnosing-bugs` / `resolving-merge-conflicts`）：[mattpocock/skills](https://github.com/mattpocock/skills)（MIT）
- 汇报 PPT 链：推荐直接安装上游 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)（本库不含）

## 维护

- **只读发布**：欢迎 issue 反馈；不接受 PR（保持单方维护的一致性）
- 加 / 改 / 退 skill 的规程：`ROUTE.md` §2.3「环境/改技能」
- 本库采用「公开层 + 本地层」：本机私有的扩展 skill 与实战台账不进本仓（见 `.gitignore` 注释）