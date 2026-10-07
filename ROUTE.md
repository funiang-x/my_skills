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
只有"不做就走不下去"能治。`preflight.py` 把该读的条款**正文**打印出来。
**没拿证去做改动动作的机器强制（`hooks/skill_gate.py`）是可选增强**——只有支持钩子的客户端能用；
不装照样开工，代价见 [`framework/跨端就绪.md`](framework/跨端就绪.md) §6。装法见 `templates/hook-settings.json`。

## 2. 任务类型 → 装什么、读什么（装配清单）

> **这张表就是上下文装配清单**：按它加载，不必读全库。命中"触发特征"就必须装载对应
> skill、并读「必读」列，不许凭记忆自己发明流程。
>
> 通用规则：
> 1. **工程内文档优先**：进到具体工程后，该工程的 `AGENTS.md` 与 `docs/` **优先于本表**。
> 2. **机器事实**（路径 / 端口 / 版本）以机器上的实际文件为准，不从记忆里来。
> 3. **判不准** → 问人，不许猜着干。
> 4. **「必载 skill」列可以随便手改**：在作者本机它是脚本从一份"任务类型全量表"生成的
>    （改动会四表同步）；fork 到你手里后 **`ROUTE.md` 本身就是手写源**，直接改这张表即可。
>    改完跑 `python tools/skillman.py doctor` 校验：引用的 skill 无死链 + `WORKFLOW.md`
>    的 skill 名 ⊆（本表 ∪ `.gitignore` 本地层名单）。

### 2.0 两级装载：先骨架层，再适配层

**看每一行的「必读」列**：它出现 `framework/` 就是骨架层（芯片无关），
出现 `adapters/` 就是适配层（芯片有关）。两份都要读，**顺序不能反** ——
先建立"这一步要产出什么、判据是什么"，再看"这颗芯片上怎么做"。

| 层 | 在哪 | 内容 | 换芯片时 |
|---|---|---|---|
| **骨架层** | `framework/`（净文档） | 适配层契约 · 工程契约 · 状态契约 · 跨端契约 · 冲突裁决 | **一行不改** |
| **适配层** | 库根带 `SKILL.md` 的芯片目录（`stm32-hal-cli-flow/`） | 芯片的构建 / 烧录 / 调试图程、工具链、板级差异、坑册 | **换一个目录** |
| **项目层** | 工程仓库内 | 源码 · `board_config.h` · `.ioc` · `PROJECT.md` | **新建一个工程** |

**现状**：只实现了 STM32。ESP32 / nRF / GD32 **留了位、没实现**（刻意的——
骨架只被一份实现拉着走，才不会被单一芯片的方言污染）。接入新芯片照
[`framework/适配层契约.md`](framework/适配层契约.md) §3 的 7 步，**骨架层不许动**。

> **三层各自的入口**（不要混）：`ROUTE.md` 说「用哪个 skill」·
> [`WORKFLOW.md`](WORKFLOW.md) 说「按什么阶段做」·
> [`framework/骨架总则.md`](framework/骨架总则.md) 说「哪些东西换芯片不用改」。

### 2.1 硬件类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `硬件/选型` | 选 MCU/器件、电源树、接口规划、BOM 风险、方案对比 | `hardware-solution` | skill 正文 + `framework/工程契约.md` |
| `硬件/深读` | 读/讲 datasheet、确认引脚/时序/电气参数、选定器件吃透（选型之后、画图之前） | `datasheet-study` · `datasheets` · `lcsc` | skill 正文 + `PREREQUISITES.md` §3.5（后两件是本地层 kicad-happy 摘装件，缺失走 datasheet-study 的降级路径） |
| `硬件/落图` | 画/改原理图、放件、扇出、布局、网络标号、打 NC、补「值」、跑 DRC | `easyeda-agent` · `easyeda-api` | skill 正文 + `references/` + [`stm32-hal-cli-flow/本机事实.md`](stm32-hal-cli-flow/本机事实.md)（**两条 EDA 链路别混** + 现场前提） |
| `硬件/看图` | 离线看原理图/PCB、落图视觉复核、给图纸做离线快照 | `easyeda-viewer` | skill 正文 |
| `硬件/审计` | 原理图查错、换料、标位号、端口修补、DRC | `easyeda-api` | skill 正文 |
| `硬件/生产` | 打样检查、Gerber/BOM 导出、下单前核对 | `easyeda-api` · `bom` · `jlcpcb` | skill 正文（bom/jlcpcb 是本地层 kicad-happy 摘装件：打样装配规则与 BOM 生命周期，备用） |

### 2.2 软件类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `软件/编码` | 写 / 改**任何**代码（含脚本）；全仓过度工程审计 / 只查复杂度的评审 | `ponytail` · `ponytail-audit` · `ponytail-review` | skill 正文 + `framework/工程契约.md` §2 |
| `软件/构建` | 嵌入式工程构建（CMake 系） | `stm32-hal-cli-flow` · `build-cmake` | skill 正文 + `adapters` = [`stm32-hal-cli-flow/工具链.md`](stm32-hal-cli-flow/工具链.md) |
| `软件/烧录` | flash、下载固件、RTT 日志（J-Link） | `flash-jlink` | skill 正文 + [`stm32-hal-cli-flow/SKILL.md`](stm32-hal-cli-flow/SKILL.md) §2 §3.2 |
| `软件/静态分析` | cppcheck、clang-tidy、MISRA 筛选、交付前代码质量扫描 | `static-analysis` | skill 正文 |
| `软件/体积` | `.map`、固件大小、内存占用、版本体积对比 | `stm32-hal-cli-flow` | skill 正文 + [`工具链.md`](stm32-hal-cli-flow/工具链.md) §3 |
| `软件/RTOS` | 任务栈水位、死锁检测、调度异常、中断不响应 | `stm32-hang-triage` | skill 正文 |
| `软件/调试` | 崩溃、卡死、HardFault、静默死锁、跑飞（STM32 + J-Link） | `stm32-hang-triage` · `debug-jlink` | skill 正文 + [`stm32-hal-cli-flow/坑册.md`](stm32-hal-cli-flow/坑册.md) §D |
| `规划/工程` | 从模板派生新工程、换芯片 | `stm32-hal-cli-flow` | [`stm32-hal-cli-flow/SKILL.md`](stm32-hal-cli-flow/SKILL.md) §4 + [`板级差异.md`](stm32-hal-cli-flow/板级差异.md) |

> **`ponytail` 是强制的**——写 / 改**任何**代码（含脚本）都必须装载它，无例外。
> 它的 2 个子命令 `ponytail-audit`（全仓审计）· `ponytail-review`（只查 diff）**按用户点名触发**，
> 不单独占任务类型，但仍登记在本行的 skill 格里（否则审计会判它们"发布出去也路由不到"）。

### 2.3 工具与环境类

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `工具/串口` | 抓串口日志、等启动字符串、交互 shell、发命令看响应 | `serial-monitor` · `serial-shell` | skill 正文 |
| `环境/接线` | 新装 AI 客户端、某客户端读不到 skill 或规则 | `agent-skill-wiring` | skill 正文 + `framework/跨端就绪.md` |
| `环境/装技能` | 从 GitHub 安装 skill（含安全审计） | `install-github-skill` | skill 正文 |
| `环境/改技能` | **加 / 改 / 修 / 退本库 skill**——把工作流程沉淀成新 skill、修正文里说错的话、装完补挂各端。**装新 skill 时 [MUST] 先定它的任务类型**：自己判断 → 判不准就问用户，**不许留空**；**从 GitHub 来源装新 skill 时另加 `install-github-skill`** | 无 | skill 正文 + `framework/适配层契约.md` §0 §3 |
| `环境/流水线` | 把多步串成一条链：**编译 + 烧录 + 监控** / 编译 + 烧录 + 调试 | 无 | 各步对应 skill 正文 |
| `环境/工作流` | 改这套三层结构本身（`framework/` 契约、`ROUTE`/`WORKFLOW` 映射、`PROJECT.md` 字段、适配层接入） | 无 | `framework/` 全部**五份** + `framework/骨架总则.md` §6（分层判据） |
| `环境/外部集成` | 判断某一步该走本地 CLI 还是接外部服务（MCP / daemon / 云）；接 EDA、仪器、第三方服务 | 无 | [`framework/外部集成.md`](framework/外部集成.md) 全文 + `ROUTE.md` §2.7（降级路径） |

### 2.4 文档与知识类（除注明外无必载 skill）

| 类型 | 触发特征 | 必载 skill | 必读 |
|---|---|---|---|
| `硬件/bringup` | 板子到手：焊接核对、限流上电、首次点亮 | 无 | `WORKFLOW.md` §2.1 ⑤ 的 checklist |
| `文档/报告` | 架构文档、测试报告、竞赛报告、编写说明 | 无 | `WORKFLOW.md` §2.1 ⑪ |
| `文档/参考文献核验` | 核对参考文献真伪、DOI 解析、作者/卷期页比对、开题报告与论文的著录核查 | `nature-ref-verifier` | skill 正文 |
| `分析/软硬件链路` | 把软硬一体的工程拆成六条链（需求/功能/数据/交互/判据/风险）；只读一手资料（源码+原理图网表+生成物）；需求→实现追溯、软硬件交互、调用关系与数据流梳理、系统体检 | `swhw-chain` | skill 正文 |
| `知识/沉淀` | 踩坑、决策、选型、复盘 | 无 | 你自己的知识库约定 + 适配层 `坑册.md` 的格式（现象 → 根因 → 处置） |
| `管理/工作台` | 改本套文档、加 / 退 skill、加客户端 | 无 | 本仓 `README.md` 维护节 + §2.6 + `framework/跨端就绪.md` |

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
  - `easyeda-agent`（[zhoushoujianwork/easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent)，MIT）：
    **落图链是它与 `easyeda-api` 配合使用的两条链路**——agent 出规程与 typed actions（CLI + daemon
    + 自有 EDA 连接器），api 供 WebSocket 桥与 API 参考；`硬件/落图` **两个一起装**。
    **只有没装 agent 的机器才降级**为 api 单跑（它自带官方规程与 `references/`）。
    装 agent 时**必带 `EASYEDA_INSTALL_SKILLS=none`**（否则它与本库的挂载机制双头打架），
    再把它的 skill 目录放进本库、由 `skillman` 统一挂到各端。
    **daemon 要常驻**：用 `easyeda daemon start --auto-update-skill=false`（关掉它的 skill 自动同步，
    否则会顶掉你的 skill 接线）；常驻做法照 `easyeda-api` 那份**幂等 VBS** 的模式——
    先 `easyeda daemon health` 判活（退 0 = 已在跑就跳过），再起。
  - `ppt-master`（汇报 PPT；[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)）：
    `文档/汇报PPT` 的推荐项。没装时按工程自己的文档规范手工产出，不影响其余流程。
  - `kicad-happy` **四件摘装**（`datasheets` / `lcsc` / `jlcpcb` / `bom`；
    [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)，MIT，2026-10-06 审计安装）：
    **`硬件/深读` 的引擎**——datasheets 管 PDF 结构化提取+按 MPN 缓存，lcsc 管搜器件/下手册
    （登记在 `硬件/深读` 行）；jlcpcb（打样装配规则）/ bom（BOM 生命周期，深绑 KiCad，备用）
    登记在 `硬件/生产` 行。上游文件**不改一字**（升级 = 重下 tarball 覆盖四个目录），
    使用约定（`skills/` 前缀映射、`python3`→`python`）见 `datasheet-study`。
    装法与审计留证：`PREREQUISITES.md` §3.5。
  - 逐项装法：`PREREQUISITES.md` §3。
- **立创EDA 扩展（可选增强）**：`easyeda-ai-assistant`
  （[jifengshandian/easyeda-ai-assistant](https://github.com/jifengshandian/easyeda-ai-assistant)，Apache-2.0）——
  立创EDA专业版原生扩展，定位"**不帮你画图，画完帮你查**"（悬空引脚 / DRC / 电源拓扑 / 引脚级问题审查，
  需要深度联动时可开它的只读 MCP）。**人工画图后的审查主力之一**（WORKFLOW ③④ 画后审查用）；
  **没装走回退**：`easyeda-viewer` / `easyeda-api` 审计链（导出 JSON 离线查）——主干不依赖它。
  装法：立创EDA「扩展管理器」搜 "AI Schematic Assistant"。
- **工具链降级**：串口 skill 需 `pyserial`（缺 → 脚本明确报 `environment-missing` 并给 PuTTY / screen 替代）；
  `easyeda-*` 需 Node（缺 → 用 EDA 客户端自带导出）；J-Link 两件套需 SEGGER 工具包
  （缺 → 报 `environment-missing`，**脚本不猜安装路径**）。
- **外部服务的降级**（EDA / 仪器 / 云）：判据与四条硬要求见
  [`framework/外部集成.md`](framework/外部集成.md)。要点：**主干不许依赖它**，
  且**必须写回退路径**——EDA 链缺服务时退回"结构化连接表"（已有先例）。
- **本地扩展层（可选）**：只适合本机的 skill / 私有台账，放进本库后加进 `.gitignore` 的本地层名单，
  并把它的任务类型登记进 §2 对应行（`tools/skillman.py doctor` 会校验无死链）。
- **全项目模板已随本仓携带**（2026-10-06 升级）：`templates/stm32-hal/`（参考板：
  **立创·梁山派·天空星 F407 开发板**，核心板 STM32F407VGT6）——2026-10-06 起从"纯固件模板"
  升级为**全项目模板**：软件(firmware 四层)+硬件(hardware/)+文档(docs/INDEX)+工作区治理
  （`_work/_archive` 机制 + 归位器随模板携带：`templates/stm32-hal/tools/tidy_workspace.py` + AGENTS「AI 工作产物落点」规则）。
  派生：**整项目** 在模板工程根跑 `python tools/derive_project.py <新名> --dest <父目录> --go`（固件工程名自动改写）；
  **仅固件** `python firmware/Tools/derive.py <新名> --dest <父目录> --verify`
  （`--verify` 会跑 build + test，退 0 = 新工程可用）。
  ⚠️ 上面那个 `tools/` 是**模板工程自己的** tools/（随快照携带），**不是本库的** tools/ ——
  别在本库根目录找它。
  母体维护在 `projects/templet`（G2026 为派生实例）。**母体改完必须回流快照**（`templates/stm32-hal/`
  是它的**快照**，不会自动跟；2026-10-06 就是漏了这一步）：
  `python tools/sync_template.py check --mother <母体路径>`（只比对，退 1 = 有漂移）
  → 确认后加 `apply --mother <母体路径> --apply` 落地；自检 `python tools/_test_sync_template.py`。
  **工程侧自备的模板仍然优先**：你已有的工程按工程自己的 `AGENTS.md` 与 `docs/` 走，本模板是兜底与起点。
- **本协议不依赖任何"宿主工作台"**：凡需要本机具体数值的地方（路径 / 端口 / 版本），
  以你机器上的实际文件为准；本仓只承诺通用能力，不承诺"某台机器怎么干活"。
- **AI 边界（任何客户端都适用）**：**不擅自烧录**（先与人确认）· 不下单 · 不擦片 ·
  不改芯片配置的引脚 / 时钟前先问人。

## 2.8 换机器 / 迁移（★ 门里有**绝对路径**，这是唯一的"搬不走"）

**先说清楚什么能搬、什么不能**：

| 东西 | 换机器 | 为什么 |
|---|---|---|
| `framework/` · `ROUTE.md` · `WORKFLOW.md` · 30 个 skill | ✅ **直接能搬** | 全是相对引用，不含本机数值 |
| `templates/stm32-hal/` | ✅ 能搬 | vendor 源码已随仓提交 |
| **门文件里写的库路径** | ❌ **搬不走** | 门正文含创建时的**绝对路径**；库换地方，门就集体指空 |
| `本机事实.md`（适配层） | ❌ 搬不走 | 端口 / 路径 / 进程名是本机的 |

### 新机器上做三步（顺序别反）

```powershell
# ① 把库挂到各客户端 + 重写全局门（正文里的路径是运行时算的，会自动更新）
python tools/skillman.py install --apply

# ② 自检：全机的门是不是都指向**当前这个库**
python tools/skillman.py pathcheck

# ③ 按 ② 的清单重铺项目门（幂等，自动备份）
python tools/skillman.py doors <工程根> --types "<常用任务类型>" --apply
```

`pathcheck` 会扫全机的 `AGENTS.md` / `CLAUDE.md` / `project_rules.md`（默认根
`~/Desktop/Project`，用 `--roots` 换），按三类报：**指向本库** / **指向另一个存在的库**
/ **指向死路径**。后两类都退 1，并给出要修的清单。

### 为什么必须有 ② 这一步

**门的路径没人查 = 换机器后静默失效。** 症状是"AI 不再走流程了"，而这**没有任何报错** ——
`doctor` 只看全局门，散在磁盘各处的项目门它看不见。2026-10 实测：老工作台被删后，
40 个门集体指向一个不存在的路径，靠人肉才发现。

> **判据**：凡"门正文/规程里出现绝对路径"的地方，都必须有一道**能查出它漂了**的检查。
> 没有检查的绝对路径 = 一颗定时炸弹。

### 库里绝对不许出现的东西

凡需要读某台机器的文件才知道的值（路径 / 端口 / 版本 / 进程名），
**只许出现在两处**：适配层的 `本机事实.md`（带日期，声明是缓存），以及**门文件**（由脚本生成）。
骨架层（`framework/`）出现这类值 = 分层漏了。

## 3. 路由声明（固定格式，贴在回复开头）

```
[ROUTE] 类型=<类型> | skill=<a,b> | 参考=<文件路径,...> | 证=<开工证> | 依据=ROUTE.md
```

硬要求：

- 五个字段**一个都不能省**；skill 或参考为空时写 `无`，不许留空、不许删字段。
- `证=` 来自 `python tools/preflight.py <类型>`。前四字段靠自觉，**这一条原本靠钩子拦**：
  钩子（`hooks/skill_gate.py`）**已降级为可选增强**——装了才拦，没装就以本条打印为准。
  **证池写在 `<当前工作区>/.ai-skills-state/preflight.json`**（不写用户目录；写不进去会自动降级为
  只打印，不影响开工）。
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
