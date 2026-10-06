---
name: datasheet-study
description: "选型之后、画图之前，把选定器件的 datasheet 吃透：读手册讲芯片、确认引脚/时序/电气参数（逐条带页码引用）、双模式讲解（评审式/教学式）。引擎是本地层 kicad-happy 的 datasheets/lcsc（缺了有降级路径）。中文触发：读数据手册、讲解芯片、器件深读、这颗芯片怎么用、确认某引脚/时序/参数、手册第几页说的什么。English: read/explain a datasheet, verify pin/timing/spec for MPN X, deep-read a selected part."
agent_created: true
---

# Datasheet Study（器件深读）

## 定位

- **上游** `hardware-solution`：管"选哪颗"（需求 → 架构 → 选型结论），datasheet 的批量下载也归它（其步骤 5，源优先级见它的 `references/download-sources.md`）。
- **本 skill**：管"这颗怎么用"——参数确认、讲解、设计要点，产出供人工画原理图/PCB 消费。
- **引擎**：本地层 kicad-happy 四件里的 `datasheets`（PDF 结构化提取+按 MPN 缓存）与 `lcsc`（搜器件/下手册）。**没装也能跑**，走 §降级路径。

## 双模式

- **评审式**（默认）：结合用户正在画的电路，讲影响设计成败的关键参数——供电范围与上电时序、配置引脚（BOOT/STRAP）、时钟、关键时序、去耦、热、已知坑。每条带**页码引用**（手册第 N 页 §x.x）。
- **教学式**（用户说"细讲"时切）：按手册章节完整过一遍：特性 → 引脚定义 → 电气特性 → 典型应用 → 封装与热。

## 流程

1. **取手册**：工程 `docs/hardware/datasheets/` 已有就直接用；没有 → 用 `lcsc` skill 按 MPN 下载；再不行 → 给出立创商城/原厂直链请用户手动下载。
   判据：本地 PDF 就位（文件头 `%PDF`），来源已记录。
2. **提取**：走 `datasheets` skill 的提取管线（scout → plan → dispatch → merge，**子代理隔离**大 PDF，按 MPN 缓存 JSON）。缓存命中直接复用。
   判据：产物通过其自带 schema 校验。
3. **讲解**：按当前模式产出。评审式先出**参数卡**（表：参数 / 值 / 条件 / 页码 / 对本设计的影响），再讲坑与待确认项。
   判据：每条结论可回溯到页码；查不到的进"待确认"清单，凭记忆说的值一律标注为假设。
4. **落盘**：讲解笔记写工程 `docs/hardware/<mpn>-study.md`；坑项按"现象 → 根因 → 处置"格式交给知识沉淀（适配层坑册）。
   判据：参数卡与笔记落盘，后续画图阶段可直接引用。

## 环境约定（kicad-happy 四件为本地层，上游文件不改一字）

- 上游文档里的 `skills/<名>/…` 路径，在本库按**库根 `<名>/…`** 解析（四件直接在库根一级目录）。
- 上游写 `python3` 处一律按 `python` 执行（Windows）。
- `datasheets` 的页选择脚本依赖 poppler（`pdftotext` / `pdfinfo`）；`lcsc` 走网络（jlcsearch 社区 API + datasheet.lcsc.com，无 key）。

## 降级路径

| 缺什么 | 怎么办 |
|---|---|
| kicad-happy 四件没装 | 本 skill 仍完整可用：子代理**分页读** PDF（按读 PDF 工具的单次页数上限切），主对话只收参数卡，不整本塞 |
| poppler 缺失 | 子代理直接读 PDF 对应页后汇总；脚本级缓存不建，讲解笔记照常落盘 |
| lcsc 不可用 / 无网 | 按 `hardware-solution` 的 `references/download-sources.md` 已验证源给直链，用户手动下载 |

## 反模式

| 想法 | 现实 |
|---|---|
| "这颗芯片我很熟" | 手册是唯一真相源；记忆值全部降级为待查证假设，讲解里逐条回页码 |
| 整本 PDF 读进主对话 | 大 PDF 必须子代理隔离，主对话只收参数卡与结论 |
| 结论不带页码 | 没有页码引用的参数无法复核，等于没给 |
| 典型应用电路跳过 | 原厂参考设计是最权威的连接关系来源，画图前值得整页读 |
| 拿老版手册讲新料 | 核对手册版本号/日期与 MPN 后缀一致，版本不符先换手册再讲 |

## 交接关系

- 参数卡与待确认清单 → **③ 原理图设计**（AI 出 pinout 表/连接表、人工画图）与 **④ PCB**（布局约束）消费。
- 坑项 → 知识沉淀（`通用/访谈与文档`），按坑册格式落。
- 选型阶段的器件比较、供应链风险仍归 `hardware-solution`；本 skill 接的是**已选定**的器件。
