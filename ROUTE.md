# ROUTE — 任务路由协议（任何 agent、任何任务，动手前先走一遍）

> 本协议**不依赖任何 AI 平台特性**——一份纯文本约定，任何能读文件的 agent 都能执行。
> 存在的理由：同一台机器上的 agent 们（CodeBuddy / Trae / Codex / …）各自的自动触发机制不同，
> 且多数由模型自行判断；把「该用哪个 skill」从「各平台的自动行为」改成「文件里的硬规定」，
> 结果才可预期、可复现、可追问。
>
> **执行入口**：各 agent 的全局规则 / 项目规则里的 `[MUST] 开工前置` 指到本文件
> （门是薄转发层，协议正文只有这一份；模板见 `templates/`）。

## 1. 四件事（顺序固定，不许跳）

| 步 | 做什么 | 产出 |
|---|---|---|
| **⓪ 拿证** | 跑 `python tools/preflight.py <类型>`，**读它打印的 skill 条款** | 开工证（12 位 `证=`） |
| **① 判类** | 按 §2 表判定任务类型 | 类型名，如 `硬件/落图` |
| **② 装 skill** | 装载该类型**全部**必载 skill（是"全都要"，不是"挑一个"） | skill 名列表 |
| **③ 读参考** | 按 §2「必读」列打开相关文件 | 文件路径列表 |

然后**先输出路由声明**（§3），再动手。顺序反了（先干再补声明）等于没做。

> **判不出"现在处在哪个阶段"**（而不是"这是什么类型的任务"）→ 读 [`WORKFLOW.md`](WORKFLOW.md)：
> 那是同一批 skill 的**阶段视图**（需求 → 选型 → 原理图 → 落图 → 固件 → 调试 → 文档），
> 每阶段给了交付物与验收判据。
> **两份分工**：`ROUTE.md` 管"**用哪个 skill**"（任务视图），`WORKFLOW.md` 管"**按什么阶段做**"（阶段视图）。

**为什么第 ⓪ 步是"拿证"**：长文档进上下文会被压缩，关键条款会丢——"放在显眼处提醒"治不了这个，
只有"不做就走不下去"能治。`preflight.py` 把该读的条款**正文**打印出来；没证去做改动动作，
会被 `hooks/skill_gate.py`（PreToolUse 钩子）拦下——装法见 `templates/hook-settings.json`。

## 2. 任务类型 → 装什么、读什么（装配清单）

> **这张表就是上下文装配清单**：按它加载，不必读全库。命中"触发特征"就必须装载对应
> skill、并读「必读」列，不许凭记忆自己发明流程。
>
> 通用规则：
> 1. **工程内文档优先**：进到具体工程后，该工程的 `AGENTS.md` 与 `docs/` **优先于本表**。
> 2. **机器事实**（路径 / 端口 / 版本）以机器上的实际文件为准，不从记忆里来。
> 3. **判不准** → 问人，不许猜着干。

### 2.1 硬件类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `硬件/选型` | 选 MCU/器件、电源树、接口规划、BOM 风险、方案对比 | `hardware-solution` | skill 正文 |
| `硬件/落图` | 画/改原理图、放件、扇出、布局、网络标号、打 NC、补「值」、跑 DRC | `easyeda-agent` · `easyeda-api` | skill 正文 + `references/` |
| `硬件/看图` | 离线看原理图/PCB、落图视觉复核、给图纸做离线快照 | `easyeda-viewer` | skill 正文 |
| `硬件/审计` | 原理图查错、换料、标位号、端口修补、DRC | `easyeda-api` | skill 正文 |
| `硬件/生产` | 打样检查、Gerber/BOM 导出、下单前核对 | `easyeda-api` | skill 正文 |

### 2.2 软件类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `软件/编码` | 写 / 改**任何**代码（含脚本）；全仓过度工程审计 / 只查复杂度的评审 | `ponytail` · `ponytail-audit` · `ponytail-review` | skill 正文 |
| `软件/构建` | 嵌入式工程构建（CMake 系） | `stm32-hal-cli-flow` · `build-cmake` | skill 正文 |
| `软件/烧录` | flash、下载固件、RTT 日志（J-Link） | `flash-jlink` | skill 正文 |
| `软件/静态分析` | cppcheck、clang-tidy、MISRA 筛选、交付前代码质量扫描 | `static-analysis` | skill 正文 |
| `软件/体积` | `.map`、固件大小、内存占用、版本体积对比 | `stm32-hal-cli-flow` | skill 正文 |
| `软件/RTOS` | 任务栈水位、死锁检测、调度异常、中断不响应 | `stm32-hang-triage` | skill 正文 |
| `软件/调试` | 崩溃、卡死、HardFault、静默死锁、跑飞（STM32 + J-Link） | `stm32-hang-triage` · `debug-jlink` | skill 正文 |
| `规划/工程` | 从模板派生新工程、换芯片 | `stm32-hal-cli-flow` | skill 正文 |

> **`ponytail` 是强制的**——写 / 改**任何**代码（含脚本）都必须装载它，无例外。
> 它的 2 个子命令 `ponytail-audit`（全仓审计）· `ponytail-review`（只查 diff）**按用户点名触发**，
> 不单独占任务类型，但仍登记在本行的 skill 格里（否则审计会判它们"发布出去也路由不到"）。

### 2.3 工具与环境类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `工具/串口` | 抓串口日志、等启动字符串、交互 shell、发命令看响应 | `serial-monitor` · `serial-shell` | skill 正文 |
| `环境/接线` | 新装 AI 客户端、某客户端读不到 skill 或规则 | `agent-skill-wiring` | skill 正文 |
| `环境/装技能` | 从 GitHub 安装 skill（含安全审计） | `install-github-skill` | skill 正文 |
| `环境/改技能` | **加 / 改 / 修 / 退本库 skill**——把工作流程沉淀成新 skill、修正文里说错的话、装完补挂各端。**装新 skill 时 [MUST] 先定它的任务类型**：自己判断 → 判不准就问用户，**不许留空**；**从 GitHub 来源装新 skill 时另加 `install-github-skill`** | 无 | skill 正文 |
| `环境/流水线` | 把多步串成一条链：**编译 + 烧录 + 监控** / 编译 + 烧录 + 调试 | 无 | 各步对应 skill 正文 |

### 2.4 文档与知识类（无必载 skill）

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `硬件/bringup` | 板子到手：焊接核对、限流上电、首次点亮 | 无 | `WORKFLOW.md` §2.1 ⑤ 的 checklist |
| `文档/报告` | 架构文档、测试报告、竞赛报告、编写说明 | 无 | `WORKFLOW.md` §2.1 ⑪ |
| `知识/沉淀` | 踩坑、决策、选型、复盘 | 无 | 你自己的知识库约定 |
| `管理/工作台` | 改本套文档、加 / 退 skill、加客户端 | 无 | 本仓 `README.md` 维护节 + §2.6 |

### 2.5 汇报材料类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `文档/汇报PPT` | 做 / 改 PPT、幻灯片、答辩与汇报材料、课件 | `ppt-master` | skill 正文（**可选增强**，见 §2.7） |

### 2.6 通用类（语言 / 平台无关的工程方法）

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `通用/设计与代码质量` | 设计或改进模块接口、想在写代码前先跑测试 | `codebase-design` · `tdd` | skill 正文；写代码时 `ponytail` 仍然强制 |
| `通用/调试` | 通用 bug 诊断循环（复现 → 收紧 → 定位） | `diagnosing-bugs` | skill 正文 |
| `通用/规格与协作` | 解 git 合并 / 变基冲突 | `resolving-merge-conflicts` | skill 正文 |
| `通用/访谈与文档` | 拷问/访谈需求与设计（非代码向）、会话交接、写 agent 文档（skill / AGENTS.md） | `grilling` · `handoff` · `writing-for-agents` | skill 正文 |

> **触发方式提醒**：`handoff` 带 `disable-model-invocation: true`
> ——**不会自动触发，需用户点名**。本表更像是"你知道有这些可用"，而不是"agent 会自动命中"。
>
> 2026-09-30 退库两个**纯转发壳**（正文只有一句「Call the Skill tool with X」，无独立内容）：
> `grill-with-docs`（差异化能力随 `domain-modeling` 退库已死）与 `grill-me`（7 行，只是
> `grilling` 的别名）。**方案拷问统一走 `grilling`**，不必保留别名目录。

### 2.7 可选增强与降级路径（**装没装都能开工**）

- **本地层第三方大件**（不随本仓发布；`doctor` 对它们缺失**只警告**，不算错误）：
  - `easyeda-agent`（落图 / 布局 / 布线加强；[zhoushoujianwork/easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent)，MIT）：
    `硬件/落图` 的加强项。**没装也能落图**——走 `easyeda-api` 自带的官方规程与 `references/`。
    装它时**必带 `EASYEDA_INSTALL_SKILLS=none`**（否则它与本库的挂载机制双头打架），
    再把它的 skill 目录放进本库、由 `skillman` 统一挂到各端。
  - `ppt-master`（汇报 PPT；[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)）：
    `文档/汇报PPT` 的推荐项。没装时按工程自己的文档规范手工产出，不影响其余流程。
  - 逐项装法：`PREREQUISITES.md` §3。
- **工具链降级**：串口 skill 需 `pyserial`（缺 → 脚本明确报 `environment-missing` 并给 PuTTY / screen 替代）；
  `easyeda-*` 需 Node（缺 → 用 EDA 客户端自带导出）；J-Link 两件套需 SEGGER 工具包
  （缺 → 报 `environment-missing`，**脚本不猜安装路径**）。
- **本地扩展层（可选）**：只适合本机的 skill / 私有台账，放进本库后加进 `.gitignore` 的本地层名单，
  并把它的任务类型登记进 §2 对应行（`tools/skillman.py doctor` 会校验无死链）。
- **本协议不依赖任何"宿主工作台"**：凡需要本机具体数值的地方（路径 / 端口 / 版本），
  以你机器上的实际文件为准；本仓只承诺通用能力，不承诺"某台机器怎么干活"。
- **AI 边界（任何客户端都适用）**：**不擅自烧录**（先与人确认）· 不下单 · 不擦片 ·
  不改芯片配置的引脚 / 时钟前先问人。

## 3. 路由声明（固定格式，贴在回复开头）

```
[ROUTE] 类型=<类型> | skill=<a,b> | 参考=<文件路径,...> | 证=<开工证> | 依据=ROUTE.md
```

硬要求：

- 五个字段**一个都不能省**；skill 或参考为空时写 `无`，不许留空、不许删字段。
- `证=` 来自 `python tools/preflight.py <类型>`。前四字段靠自觉，**这一条靠钩子拦**：
  没证去做改动动作会被 `PreToolUse` 挡下（退出码 2）。
- **多轮任务中任务类型一变就重新声明**（例：先"软件/编码"后转"硬件/落图"→ 补一条 `[ROUTE]`）。
- 声明必须是**动手前**的第一条输出；中途发现判错类型 → 立即补声明说明更正。

示例：

```
[ROUTE] 类型=硬件/落图 | skill=easyeda-agent,easyeda-api | 参考=WORKFLOW.md §2.1 | 证=1a2b3c4d5e6f | 依据=ROUTE.md
[ROUTE] 类型=软件/编码 | skill=ponytail | 参考=无 | 证=6f5e4d3c2b1a | 依据=ROUTE.md
[ROUTE] 类型=通用/访谈与文档 | skill=grilling,handoff,writing-for-agents | 参考=无 | 证=无 | 依据=ROUTE.md
```

## 4. 收工自检（四问）

1. 声明里列的 skill，**真的都装载并按其要求做了吗**？
2. 声明里列的文档，**真的都读了吗**（还是只在声明里写了路径）？
3. 中途任务类型变过吗？变了而没补声明 = 违规。
4. 动手前**拿开工证了吗**？期间**改过 skill 吗**（改过则旧证作废，要重跑 `preflight.py`）？

## 5. 为什么用「声明」而不是「自动触发」

各平台的 skill 触发机制各不相同，且多数是"模型判断是否使用"——**不可预期、不可复现**。
本协议把控制权收回到**文件 + 显式声明**：

- 判定规则写在文件里 → 换任何 agent 结果一致；
- 声明贴在回复里 → 用户一眼看到"它调了什么、读了什么"，错了能当场纠正；
- 规则与文档都在仓库里 → 不依赖任何一家的云配置。
