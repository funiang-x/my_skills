---
name: easyeda-schematic-net-fanout
description: >-
  EasyEDA Pro schematic design workflow — placement, net fanout, readability
  refactor, NC marking, DRC closure, component value/multi-part fixes.
  嘉立创EDA专业版**原理图设计全流程**规程：LCSC 批量取器件、彩色功能分区框、按间距表放件、
  逐引脚 fanout、**可读性重构（内部网络走实体导线 / 电源地用旗 / 跨距离用标签）**、
  打 NC、补元件「值」、多部件元件（双运放）修正、DRC 收口与视觉复核。
  当要在嘉立创EDA里**画 / 改 / 重构 / 审计原理图**，或遇到元件重叠、引脚没标签、
  DRC 报悬空/位号/多部件/引脚与焊盘未对应时使用。
  ⚠️ 开工前必读本文件顶部「🚨 开工必读 · 本机硬规矩」一节。
  依赖本机 easyeda-api skill 与运行中的桥接服务；读图纸另需 skill easyeda-viewer。
license: MIT
compatibility: Requires easyeda-api skill and running bridge server
metadata:
  updated_2026_09_30c: 新增 G8（API 新件自带库属性/值免回填，勿对新件跑 value 脚本）；value 段落加同款警告；LESSONS 追加 T-49~T-53（DRC 盲区核对法 / delete 延迟生效 / 新件自带值 / 合并折线整删重建 / 备份防覆盖）
  updated_2026_09_30b: 正文最顶插「[MUST] 开工前置 · 五问」（对症"装载≠读到"：长文被压缩会丢条款）；audit-fix 随附 scripts/（audit_sch · bridge · dangling · delete_part）
  updated_2026_09_30: 新增「G 组·换器件/批量改图」7 条（换件后必跑 DRC / libraryType:DEVICE / 删端口连带删线 / 批量删建 / 换页等足 / 换件验收三件套 / 坐标比较）；LESSONS 追加 T-48 收窄 T-42
  version: "1.10.0"
  source: https://github.com/easyeda/easyeda-enhanced-schematic-skill (commit main @ 2026-09-28)
  local_patch: see PATCHES.md (6 adaptations for this machine)
  ledger: LESSONS.md (只增不改的实测台账 · 41 条 · 落图前必读)
  added_2026_09_29: >-
    顶部新增「开工必读 · 本机硬规矩」（LESSONS 41 条的蒸馏，A~F 六组）；
    scripts/eda_sch.py（nc/drc/value 统一入口）；与 skill easyeda-viewer 的视觉复核联动；
    可读性重构套路（清空重画）与多部件元件修法
---

> ## 🚨 [MUST] 开工前置 · 五问（**动手前逐条答完**；这是本机 2026-09-30 事故的直接补丁）
>
> 1. **这活有没有现成 skill？** 原理图类四件套：落图/扇出 `easyeda-schematic-net-fanout` ·
>    审计/修补 `easyeda-sch-audit-fix` · API 签名 `easyeda-api` · 离线看图 `easyeda-viewer`。
> 2. **它的「开工必读」读到了吗？** ⚠️ **装载 ≠ 读到** —— 长文档进上下文会被**压缩/截断**，
>    关键条款会丢。**必须显式复述**"我按 X 条、Y 条办"，复述不出来就是没读到，回去读。
> 3. **有没有现成脚本能干这事？** 先列 `scripts/`（本技能与兄弟技能）再决定自己写。
>    —— 2026-09-30 实测：跳过这步导致重造轮子，还踩了两个**早已记录**的坑。
> 4. **验收标准写死了吗？** 电气正确性 = **EDA 自己导出的 DRC**（唯一权威）；
>    几何/短路类 DRC 抓不到的 = `scripts/audit_sch.py`；看图 = `easyeda-viewer`。
> 5. **写前备份了吗？** 整页源码落盘 = 唯一完备快照（`getDocumentSource()` 分块取）。
>
> > **为什么放这里**：顶部内容在上下文被压缩时**存活率最高**。
> > 详细规矩在下面各节与 `LESSONS.md`（只增不改的实测台账）。


# EasyEDA Schematic Component Placement & Net Fanout

## 🚨 开工必读 · 本机硬规矩（照做，别重新发明）

> 这一节是 **`LESSONS.md`（41 条实测台账）的蒸馏**。**动手前先读完本节**；要细节再按编号去台账查。
> 每条都带 `T-xx` 出处，全部 **2026-09-29 之前在本机实测确立**。

### A. 坐标与连接（搞错全图废）

| # | 规矩 | 出处 |
|---|---|---|
| A1 | **引脚的电气连接点 = 属性 `(x,y)` 本身**，不是 `(x,y)+朝外×pinLength`（那是引脚画的另一端）。朝外方向：`0→(+1,0) 90→(0,+1) 180→(-1,0) 270→(0,-1)` | T-01 |
| A2 | **端口/标签 = `(x,y)+朝外×10`**；导线 = `(x,y) → 端口`。**永远不要写"引脚端点外 N"** —— 歧义表述是本机最大坑源 | T-09 |
| A3 | **标签必须配一根短线**才连得上（标签的连接点是**它自己的中心**）。短线 `net` 留空，网名由标签给 | T-32 |
| A4 | 标签方向 → `rotation`：**右=0 · 上=270 · 左=180 · 下=90** | T-33 |

### B. EDA 会**静默改你的图**（"操作成功但结果不对"）

| # | 规矩 | 出处 |
|---|---|---|
| B1 | 连通的导线会被**自动合并**成一个折线对象；`sch_PrimitiveWire.getAll()` 的 `w.line` 是**扁平坐标数组** `[x1,y1,x2,y2,…]`（每 4 个一段），**不是**"线段的数组" | T-29 |
| B2 | **穿过引脚的导线会被自动截断**（拆两段、留缺口）→ **布线必须显式绕开不相干引脚** | T-30 |
| B3 | **带 NC 标记的引脚拒绝建导线**（`create failed!`）。诊断用**端点扫描**二分失败边界 | T-31 |
| B4 | **`wire.modify` 改不动 `net`**（V4.1.60 起，传 `net:""` 也无效）→ 要清/改网名只能 **`delete` + `create` 重建** | T-35 |
| B5 | **别给多段折线设 `net`** → 报「导线有多个网络名: X、X…」（**段数 = 重名个数**）。要么单段、要么改用净标签 | T-36 |
| B6 | `sch_PrimitiveText.getAll()` 的 **`value` 读不到**（空串）→ 按**坐标**匹配文本，别按内容 | T-37 |

### C. 造元件 / 改元件

| # | 规矩 | 出处 |
|---|---|---|
| C1 | ⛔ **不要用 `setDocumentSource` 注入组件记录** —— EDA 会标成「**异常数据**」致命错误（组件无位号、无引脚）。**造组件一律走 API `create`** | T-41 |
| C2 | **造元件必须用「库器件」uuid**（`lib_Device.search(name)` 拿到的），**不是**图上组件的 `component.uuid` —— 后者会**超时 30s 且不落件** | T-39 |
| C3 | **多部件元件（双运放等）四步修法**：① `create(库器件, x, y, "X.2", …)` ② 两单元位号都设**基位号**（`U1`，不是 `U1A/U1B`）③ `otherProperty["Multi-Part Group"]` 两单元**同值** ④ 两单元 `otherProperty` **整表完全相同** | T-39 |
| C4 | 库符号的 B 单元**可能没有电源脚**（V+/V− 只画在 A 单元）→ 换单元后要清掉接到旧电源脚的孤立线 | T-40 |
| C5 | 改属性**必须整表回写**（`modify(id,{otherProperty: 整表})`），只传一个键会清掉其余 | T-17 |
| C6 | **改元件必须按页分组**，写前先 `openDocument(该页)` —— `modify` 只对**当前打开的页**生效 | T-24 |
| C7 | **挪端口位置**只能 `delete` + `createNetPort/createNetFlag` 重建（端口不许 `modify`）；定位标签要按 **id 或「坐标+类型+网名」三重匹配** | T-19 |

### D. 拿数据 / 验收

| # | 规矩 | 出处 |
|---|---|---|
| D1 | **`lib_Device` 可用**：`search(name)` → uuid → **`get([uuid])`**（必须传**数组**）拿权威 `otherProperty`（含 `Value`）。批量查库**每批 ≤8 个型号** | T-21 / T-25 |
| D2 | **DRC 明细只能读 DOM**：`check(false,true,false)` 开面板 → 读 `#schDrcPrimaryLog`。**计数徽标是准的**，改前记基线、改后比对 | T-02 |
| D3 | **`sch_Drc.check` 是整设计级**（打开哪页跑都得同一组计数） | T-23 |
| D4 | **读全量 DRC 日志**要点面板内「导出」。⚠ EDA ≥V4.1.60 会弹**「另存为」对话框** → `eda_sch.py drc` **默认不点**，要日志才加 `--export … --click-export` | T-14 |
| D5 | **读图纸用 skill `easyeda-viewer`**（`dump`/`serve`/`shot`）—— EDA 的 `getDocumentSource()` 输出**就是 `.esch2` 正文**，可直接离线渲染。这是 AI 的"检查眼" | T-26 |
| D6 | 大字符串回传会 **HTTP 500** → 分块取（`s.slice(i, i+40000)`） | T-11 |

### E. 设计与可读性（2026-09-29 三页重构确立）

| # | 规矩 | 出处 |
|---|---|---|
| E1 | **连什么用什么画**：**内部网络 → 实体导线**；**电源/地 → 旗（netflag）**；**跨距离/跨页信号 → 净标签（netport）** | T-34 |
| E2 | **同器件同网的多脚 → 母线并联**（外侧一根母线 + 各脚短线 + **整组只留一个旗/标签**），不要一脚一标签 | T-38 |
| E3 | **可读性重构 = 清空重画**：备份整页 → 记网表（并查集）→ **删全部导线与标签** → 按网表重画 → 三项复核 | T-34 |
| E4 | **给页面加功能分区框 + 推导原理文字**（彩色矩形 + 标题 + 若干行说明）。文字**第 1 行要在最上**（y 最大），逐行 -17 | 本轮 |
| E5 | 元件**不要乱挪**：挪件会牵动它全部引脚的连线，属高风险 → 先报告、要人拍板 | T-28 |

### F. 铁律（流程层）

1. **[MUST] 批量前样本门**：任何全图级改动先用**一个引脚/一个器件**做样本，读数确认假设成立再批量。
2. **[MUST] 改完回读自证**：读回真实数据与预期逐条比对，不许只说"已完成"。
3. **[MUST] DRC 是唯一权威**：自写几何核对**证明不了**"连上了"。
4. **[MUST] 写前先备份**：整页源码落盘 = 完备快照，可整页回滚。

---

### G. 换器件 / 批量改图（2026-09-30 换屏接口 SMD→THT 实战确立）

| # | 规矩 | 出处 |
|---|---|---|
| **G1** | **换件后必须当轮跑 DRC**。若报 `引脚与焊盘未对应`（错误级）：**只对「API `create` 出来的新件」成立** —— 建件后**别再调 `modify()`**（连改位号都算）。位号用 **`create` 返回句柄**的 `toAsync().setState_Designator()`；属性与 NC 合并成**一次源码注入**。对界面上已有的件，`modify` 照常用（§C5/§D 不受影响） | T-48（收窄 T-42） |
| **G2** | **`create` 必须带 `libraryType:"DEVICE"` + 库器件的两个 uuid**。漏了会建成"符号实例"：源码 COMPONENT 记录的 `partId` 变成**符号名**（正常应是 `<器件名>.1`，如 `SMA-KE.1`）⇒ DRC 报"引脚与焊盘未对应" | T-48 |
| **G3** | **删 netport/netflag 会连带删掉它自己的短线**；重建端口时短线**不会回来** ⇒ 端口变孤儿（DRC：`网络端口 X 没有连接导线`）。**改名前先记下短线两端点，重建后必须补线**。⛔ **别把"没有导线的旗标"当冗余直接删** —— 它可能是某引脚**唯一的落点**（本轮真删错过 `U1.4→AGND`/`U1.8→+5V_A`） | T-43 |
| **G4** | **批量改图必须批量化**：删用**数组** `delete([id,…])`、建用**一次调用**多发。逐条 `delete` + `setTimeout` 会被桥掐断（**HTTP 500**）且**部分已执行** ⇒ 页面处于半改状态。数组 `delete` 的**返回值要看**（逐条循环里失败会被静默忽略，留下重复旗标/零长度导线） | T-45 |
| **G5** | **跨页连读必须等足并回读页名自证**：`openDocument` + 0.7~0.9s **不够**，对账/导出会**串页**（典型：AFE 表里出现 PWR 的件、两页导出长度一模一样）。一次只处理一页，或每页 `openDocument` 后加长到 ≥1.5s 并校验页名 | T-46 |
| **G6** | **换件验收三件套**（缺一不算完）：① **逐脚回读**（新符号脚位与预期 0 不符）② **网表逐条比对**设计表（如 30 脚映射表）③ **DRC 回到基线计数**。几何自检只能当辅助 | 本轮 |
| **G7** | **坐标比较一律 `round()` 且统一容器类型**：引脚常返回 `979.9999999999998` 而导线端点是 `980`；JS 传回的是 **list**，Python 侧用 **tuple** 比永远不等 | T-47 |
| **G8** | **API `create` 的新件自带库属性（含 `Value`）**，无需 `value` 回填；⚠️ 也**别对新件跑 `eda_sch.py value`**（它内部用 `modify()` 回写 → 触发 G1 的「引脚与焊盘未对应」）。补值前先排除新件 | T-51 |

## 🛠 设计一页的推荐流程（照这个走就不会踩坑）

```text
0) 前置：EDA 客户端已开 + Run API Gateway 扩展已加载且勾选「允许外部交互」；桥 /health 返回 edaConnected:true
1) 备份：把目标页源码 dump 存盘（唯一完备快照）
2) 读现状：并查集重建网表 + 拿全部引脚坐标/包围盒
3) 设计：划功能分区框 → 决定每个网络用「导线 / 旗 / 标签」→ 排出坐标
4) 施工：删旧导线与标签 → 按设计建导线（net 留空，名字交给标签/旗）→ 建旗/标签（**每个都配短线**）
5) 装饰：加分区框 + 标题 + 推导说明文字
6) 复核三件：① 网表逐网络比对（差异必须 0）② DRC 计数改前→改后 ③ 截图目视
7) 收工：提醒人在 EDA 里 Ctrl+S；把新结论追加进 LESSONS.md
```

**工具**：`scripts/eda_sch.py`（nc / drc / value）+ skill `easyeda-viewer`（dump / serve / shot）。

## Overview

This skill defines the proven workflow for placing components on an EasyEDA Pro
schematic and fanning out all pins to net flags/ports. The result is a clean,
non-overlapping layout where every pin has a visible net label connected by a
short wire — ready for the user to route connections manually.

## ⚠️ 本机适配六条（先读，覆盖下文示例）

1. **端口不要写死 49620**：本机桥自动在 **49620-49629** 里挑第一个可用端口。发请求前先探测：
   `for p in $(seq 49620 49629); do curl -s --max-time 2 http://localhost:$p/health | grep -q easyeda-bridge && echo $p; done`
   —— 下文 Step 6 示例里的 `49620` 换成探测到的 `$BRIDGE_PORT`。
2. **发给桥之前必须删掉所有 `//` 注释**：`easyeda-api` skill 规定代码在 EDA 内按
   单行执行（"Do not add comments to the generated code"）。本文件的 JavaScript 示例
   **只是给人读的说明**，原样贴进 `/execute` 会报错。
3. **开工前置**：桌面版嘉立创EDA专业版必须已打开且扩展已连上桥（桥设了登录自启，
   Gateway 扩展**不会自动重连**——EDA 先开或桥重启过，就要在 EDA 里重载扩展）。
   多窗口时先 `GET /eda-windows` 再 `POST /eda-windows/select` 选定目标窗口。
   **NC 脚不许静默跳过**：本文件 Step 4 说 NC 直接 skip，但工作台 `20_硬件链.md` §2
   要求未用脚显式声明 `NC-内部悬空` / `NC-引出排针`——按连接表落图，落完回读核对。
   **画 NC 的具体方法见下文「画 NC（非连接标志）」节**（用 `setDocumentSource()` 注入，
   不要用模拟按键——那会抢占用户的鼠标键盘，且实测极不可靠）。
4. **实测结论一律以台账为准**：[`LESSONS.md`](LESSONS.md)（本目录）是**只增不改的实测台账**——
   引脚模型、API 跑通/跑不通总表、坑与修复姿势都在里面。**落图前先扫一遍**。
   **冲突优先级：台账 > 本文 > 上游 README**（本文 Step 部分继承上游环境，未必适配本机）。

   **最要命的一条**（详见台账 `T-01` 与下文「本机铁律」）：

   > 引脚的**电气连接点就是属性 `(x,y)`** —— 不是 `(x,y)+朝外×pinLength`（那是引脚画的另一端）。
   > 写脚本、写规程**一律用坐标式子**，禁止"引脚端点 / 引脚外端"这类歧义词：
   > `端口 = (x,y) + 朝外方向×10`；`导线 = (x,y) → 端口`。

   桥端点：`GET /health` · `GET /eda-windows` · `POST /execute`
   （body `{"code": "return await …"}`，**单行执行、不许带 `//` 注释**）。

## ⚠️ 本机铁律：引脚连接点是 `(x,y)`，不是外端（2026-09-28 某工程 实战确立）

**这是本机落图最容易犯、也最致命的错。落图前必读。**

EasyEDA Pro 的引脚模型（用 `sch_Primitive.getPrimitivesBBox()` 实测确认）：

- 引脚属性 `(x, y)` = **电气连接点**（电线必须接到这里）。
- `rotation` 描述引脚**朝元件体内**绘制的方向；`pinLength` = 该方向上的绘制长度。
- 所以「引脚外端」= `(x, y) + 朝外方向 × pinLength`，那是**引脚画的另一端**，
  **接在那里等于没接**。

**朝外方向表**（`rot → 单位向量`）：`0 → (+1,0)` · `90 → (0,+1)` · `180 → (-1,0)` · `270 → (0,-1)`

实测证据（C16，0805 钽电容，元件中心 y=1220）：

| 引脚 | 属性 `(x,y)` | rot | pinLength | 包围盒 y 范围 | 结论 |
|---|---|---|---|---|---|
| 2 | (470,1200) | 270 | 19 | 1199.5 → 1219.5 | 从属性点朝体内画 ⇒ 属性点即连接点 |
| 1 | (470,1240) | 90 | 17 | 1240.5 → 1222.5 | 同上 |

**错误做法（本机 某工程 曾 216 个引脚全踩）**：把端口放在
`(x,y) + 朝外 × (pinLength + 10)`、再用一根线从 `(x,y) + 朝外 × pinLength` 连过去。
→ 结果：**全图每个引脚都被 DRC 判「悬空」**，而几何上"看起来连着了"。

**正确做法**：

```text
端口位置  = (x,y) + 朝外方向 × 10      // 连接点外 10 单位
导线       = (x,y) → 端口位置           // 从连接点出发，10 单位短线
```

即：**导线靠引脚那一端必须落在 `(x,y)` 上**。端口在外 10 单位是为了不压住引脚本体。

### 修复现有错接（保留端口、只挪导线靠引脚的一端）

对每个 `part` 类元件的每个引脚：若存在一条导线，其某个端点 = `(x,y) + 朝外×pinLength`，
则把该端点改写为 `(x,y)`；另一端（连端口的）不动。
`sch_PrimitiveWire.modify(id, {line: [...], net: '<原网名>'})`。

> ⚠️ **`modify` 只传 `line` 会把 `net` 清空**（实测：PWR 44/44、INT 85、AFE 87 条网名全变空）。
> 必须同时传 `net`，或改完后按「端口位置 → 网名」映射补回。
> 本机 某工程 已按此补回 213 条。

### DRC 明细怎么读（API 拿不到，走 DOM）

`sch_Drc.check(strict, ui, verboseError)` 的 `verboseError: true` 在 V3.2.65 **实测仍返回 boolean**，
拿不到明细；`sch_Netlist.getNetlist()` 报 500；`getNetlistFile()` 因组件 `Unique ID` 为空而
**所有组件塌缩成一个空键条目**，不可用；`sys_Log.find/sort` 只有 `openProject` 一类条目。

**可行方案**：执行上下文**能读 DOM**。跑 `check(false, true, false)` 打开底部 DRC 面板后：

```js
const el = document.getElementById('schDrcPrimaryLog');
return el.textContent;   // 完整日志文本
```

面板顶部的计数徽标（`全部(n) / 致命错误(n) / 错误(n) / 警告(n) / 信息(n)`）也在 `textContent` 里，
**这就是最实用的闭环信号**：改前记基线、改后比对。

> 面板是**虚拟列表**，只渲染可见的若干条消息（实测 8 条封顶），
> 用 `scrollTop` 也刷不出更多；要看全部类别请用面板的「导出」按钮。
> 但**计数徽标是准的**，用它判断改动是否有效最省事。

## ⚠️ 画 NC（非连接标志）的正确姿势 —— `setDocumentSource()` 注入（2026-09-28 实测确立）

**一句话**：引脚对象 API 全都写不了 NC；**页面源码是一条记录流，NC 就是其中一条普通
`ATTR` 记录** —— 直接构造并追加，然后整体写回。全程**不碰用户的鼠标键盘**。

### 为什么不能用模拟按键

上游思路（选中引脚 → 抢焦点 → 发 `C` 键）在本机**实测极不可靠**：
同一批 4 个引脚，按键法 **4 次只成 1 次**；点击画布取焦点还会**清掉已有选中**。
更关键的是它会**抢夺用户的鼠标和键盘**（实测中打断了用户正常使用）。
**除非注入法不可用，否则不要用它。** 对比表见台账 `T-13`。

### 现成工具一：`scripts/eda_sch.py`（**统一入口，首选**）

本 skill 的「三件事」都在一个脚本里，默认干跑、自动备份、回读自证：

```bash
SK=~/.ai-skills/easyeda-schematic-net-fanout/scripts/eda_sch.py   # 换成你的库路径

python "$SK" audit --all                              # 只读体检：器件/NC/空「值」
python "$SK" drc   --all --export ./drc_logs --baseline ./drc_base.json
python "$SK" value --all                              # 干跑：列出待补「值」计划
python "$SK" value --all --apply                      # 写回（值取自 EDA 库器件）
python "$SK" nc    --page INT --pins EVK1.81,EVK1.83 --apply
```

- **`drc`**：跑 `check(false,true,false)` → 读 `#schDrcPrimaryLog` 计数徽标 → 点面板内「导出」
  把全量日志复制到 `--export` 目录；`--baseline` 首次写入、之后用来做**改前/改后比对**。
- **`value`**：审计「`otherProperty` 有 `Value` 键但值为空」的器件 → 用 `lib_Device.search` +
  `get([uuid])` 取**库里的权威 `Value`** → **整表回写**；库里没有就用 `lib_Symbol` 的描述兜底。
  ⚠️ **它内部用 `modify()` 回写** ⇒ **对 API `create` 的新件会触发「引脚与焊盘未对应」**（T-42/T-48/T-51）；
  **新件自带库值、不需要回填**——跑 value 前先排除新件。
- **`nc`**：委派给下面的 `inject_nc.py`（同一份已验证实现，不重复造）。

### 现成工具二：`scripts/inject_nc.py`（打 NC 的底层实现）

```bash
# 干跑（默认，只打印计划，不动工程）
python scripts/inject_nc.py --page INT --pins EVK1.81,EVK1.83,EVK1.84
# 确认无误后再写回
python scripts/inject_nc.py --page INT --pins EVK1.81,EVK1.83,EVK1.84 --apply
```

- `--page` 支持**页名模糊匹配**（INT / PWR / AFE）或页 uuid
- 默认**干跑**；写回前自动把原源码落盘备份；只**追加**记录并 `assert` 前缀自证
- 自动做 `ticket` / `id` 唯一性检查；写回后**回读比对**并请求保存
- 退出码：`0` 成功（含"无需改动"）/ `1` 出错未写回 / `2` 干跑发现异常
- **本文件所有内容（探桥、分块读源码、格式解析、唯一性、回读校验）都已内置**，
  下面的步骤是它内部在做什么，供理解与排障。

### 注入步骤（= 脚本内部流程）

```text
1) 分块读回源码：   n = getDocumentSource().length
                    然后 s = getDocumentSource().slice(i, i+40000)  逐块拼
   （整页 >30 万字符时一次 return 会 HTTP 500 —— 见台账 T-11）
   拼好后**立刻存盘备份**，这就是完备快照。

2) 本地收集已知 NC：正则  "parentId":"([^"]+)"[^}]*?"key":"NO_CONNECT"
   得到「已打 NC 的引脚 id」集合，用于跳过重复。

3) 对每个待打 NC 的引脚构造记录：

   {"type":"ATTR","ticket":N,"id":"<16位hex>"}||{"parentId":"<pinId>","key":"NO_CONNECT","x":pinX,"y":-pinY,"value":"yes","zIndex":Z}

   - ticket：取全页 max(ticket) 后递增，**必须全局唯一**
   - id：16 位小写 hex，**不得与任何现有 id 撞**（先正则收集全部 id）
   - x / y：引脚坐标，**y 取负**（源码坐标系与 API 的 pin.y 符号相反）
   - value 恒 "yes"；zIndex 取全页 max 后递增即可

4) 追加写回：  newSrc = src + "|\n" + rec1 + "|\n" + rec2 ...
   **自证非破坏**：assert newSrc.startswith(src)

5) setDocumentSource(newSrc)     → 返回 true
6) 回读计数 + 跑 DRC 复核（DRC 读法见台账 T-02）
```

### 记录流格式（读写源码的前提，台账 T-12）

- 整页 = 记录用 **`|\n`** 连接，每条记录内部是 **`HEADER||DATA`**，**末尾无分隔符**。
- `type` 取值：`DOCHEAD` / `CANVAS` / `COMPONENT` / `WIRE` / `LINE` / `TEXT` / `ATTR`。
- 解析：`src.split('|\n')` → 每段 `hdr, _, data = part.partition('||')` → 各自 `json.loads`
  （**用 `partition` 只切第一个 `||`**，DATA 里可能再出现 `||`）。

### 实测证据（某工程 INT 页，2026-09-28）

| | 写回前 | 写回后 |
|---|---|---|
| 源码长度 | 319896 | 320368 |
| `"key":"NO_CONNECT"` | 57 | **60** |
| 桥返回 | — | `true` |
| 回读一致性 | — | **逐字节等价**（仅 `DOCHEAD.client`/`updateTime` 被 EDA 自行改写） |

DRC：悬空引脚 **5 → 1**，全部 **62 → 57**，警告 **13 → 8**。
（同一批 4 个引脚先试按键法只成 1 个，注入法一次全成。）

### ★ 先解决一件事：怎么拿到**全量** DRC 结果

**面板只有 8 行**（滚动窗口），计数徽标準但明细看不全 —— 想逐条清 DRC，**必须先拿全量**：

```js
// 1) 跑 DRC 打开面板
await eda.sch_Drc.check(false, true, false);
await new Promise(r => setTimeout(r, 3500));
// 2) 点面板自带的「导出」——注意必须限定在面板内，否则会点到菜单栏的「导出」
const p = document.getElementById("schDrcPrimaryLog");
const exp = [...p.querySelector("[class*='log-btns']").querySelectorAll("button")]
              .filter(b => (b.textContent || "").trim() === "导出")[0];
exp.click();                       // 落盘 C:\Users\<你>\Downloads\<uuid>.tmp（UTF-8 文本）
```

那个 `.tmp` **就是完整 DRC 日志**，带时间戳、逐条列出。`全部(n) / 警告(n) / 信息(n)` 与它一一对应。
**没有它，清 DRC 只能靠猜。**（台账 `T-14`）

### ⚠️ 唯一的真风险：**陈旧快照覆盖**

写完必须立刻回读比对。**读源码与写源码之间不许有人/有操作改动该页**——
否则你写回的是旧快照，会**整份覆盖掉期间的人工改动**（历史上正是这样弄丢过一个 NC）。
先存盘再写，就是完备备份。

### 清 DRC 常见残留（逐条对症，台账 T-15/T-16）

| DRC 消息 | 病因 | 修法 |
|---|---|---|
| `导线 X 是单网络，仅连接了一个元件引脚` | 导线端点落在 `(x,y)+朝外×pinLength`（引脚**尖端**）而非 `(x,y)` | 该端改到 `(x,y)`，`net` 设成附近标签的网名 |
| `导线 X 有多个网络名: GND、GND` | 导线**既有标签又手动设了 `net`** | 把该导线 `net` 清空（名字交给标签） |
| `网络端口 X 的名称与所连导线名称 Y 不一致` | 同一节点上标签与导线网名互相矛盾 | 决定哪个是正确网名，统一二者（**改动前先算电路语义**） |
| `元件 X 的属性"值"内容为空`（信息） | 库器件未带 `Value` | **`eda_sch.py value --apply`**：从 `lib_Device` 取库表 `Value` 整表回写（T-21/T-22）；库无值再用 `lib_Symbol` 描述兜底 |
| `元件的属性与供应商编号不匹配…建议使用器件标准化`（警告） | 器件属性与库不同步 | 本机**未找到 API**，需人工在 EDA 里处理（T-20） |

### 视觉复核：交给 skill `easyeda-viewer`（离线看图纸）

**DRC 管电气正确性，看图纸归 viewer。** 实测（T-26）：`getDocumentSource()` 的输出**就是 `.esch2`**，
可直接喂给 [`easyeda/easyeda-viewer`](https://github.com/easyeda/easyeda-viewer) 离线渲染，
无需在 EDA 里「导出工程」。用法见 skill **`easyeda-viewer`**：

```bash
python ~/.ai-skills/easyeda-viewer/scripts/viewer.py dump  --all --out ./_view
python ~/.ai-skills/easyeda-viewer/scripts/viewer.py serve --dir ./_view --port 8931
python ~/.ai-skills/easyeda-viewer/scripts/viewer.py render ./_view/AFE.esch2   # 无头自检
```

用途：分区框/重叠/穿件走线/位号与值是否可见的**目视复核**；给用户一份**可离线打开**的快照。
⚠️ 它渲染的是**导出时的快照**——改完图要**重新 dump**。

### 适用范围

`scripts/inject_nc.py` 已实测：正例（3 处注入成功）+ 4 类负例（不存在的脚号 / 位号 / 页、
已有 NC 重复提交）均按预期报错且**不写回**。

已在本机验证的只有 **NO_CONNECT 记录的追加**。其它图元（导线/端口/文本/删除）**属未验证**——
要动就在**副本工程**上先试（台账 `U-07`）。

## Workflow Steps

### Step 1: Batch-fetch device info by LCSC IDs

Use `lib_Device.getByLcscIds()` with `allowMultiMatch=true` to get all device
UUIDs and libraryUuids in one call:

```javascript
const lcscIds = ["C9900163599", "C9900012665", "C6186", ...];
const results = await eda.lib_Device.getByLcscIds(lcscIds, undefined, true);
// Each result has: uuid, libraryUuid, name, footprintName, etc.
```

**Important:** `otherProperty` keys are in English (e.g. "Supplier Part",
"Manufacturer"). Do NOT use Chinese keys — they will throw "is not defined".

### Step 2: Place components with spacing

**Schematic coordinate unit = 0.01 inch (10mil).** Grid step of 10 = 100mil.

#### Module-Box Layout (recommended for multi-block designs)

When the design has distinct functional blocks (e.g. USB/Power, MCU, Display,
Storage, Buttons), draw colored module rectangles FIRST, then place components
inside their respective boxes. This produces a readable, professional schematic.

**Module rectangle API:**
```javascript
// create(topLeftX, topLeftY, width, height, cornerRadius, rotation, color, fillColor, lineWidth, lineType, fillStyle)
// - color: border color string e.g. "#0066CC"
// - fillColor: "none" for transparent, null for default, or hex color
// - lineWidth: 1-10
await eda.sch_PrimitiveRectangle.create(x, topY, w, h, 10, 0, "#0066CC", "none", 2, null, null);
```

**Module text label API:**
```javascript
// create(x, y, content, rotation, textColor, fontName, fontSize, bold, italic, underLine, alignMode)
// alignMode: use NUMERIC value, NOT enum name (see pitfall below)
//   1=LEFT_TOP, 2=LEFT_MIDDLE, 4=CENTER_TOP, 5=CENTER, 6=CENTER_BOTTOM, 8=RIGHT_MIDDLE
await eda.sch_PrimitiveText.create(centerX, topY - 15, "USB & 电源", 0, "#0066CC", null, 16, true, false, false, 4);
```

**Grid layout example (5 modules in a 3x2 grid):**
```
Row 1 (top,    topY~1450):  USB&Power(x=50,w=620) | ESP32(x=750,w=700) | LCD(x=1550,w=520)
Row 2 (bottom, topY~700):   Button&UART(x=50,w=620) | (empty)            | TF Card(x=1550,w=520)
```
- Give each module enough interior space for all its components plus net flag fanout room (~100 units margin inside edges).
- ESP32 module needs the largest box (700x900+) — it has 41 pins fanning out on both sides.
- Place module label text 15 units below the top edge (inside the box, Y decreasing).

#### Component placement inside modules

```javascript
const placements = [
  // {designator, device_key, x, y, rotation}
  // Place each component at a coordinate INSIDE its module box
];

for (const p of placements) {
    const comp = {libraryUuid: p.libUuid, uuid: p.uuid};
    const created = await eda.sch_PrimitiveComponent.create(comp, p.x, p.y, "", p.rot, false, true, true);
    const asyncComp = created.toAsync();
    asyncComp.setState_Designator(p.des);
    await asyncComp.done();
}
```

**Spacing guidelines (in schematic units = 10mil each):**
- Small ICs (SOT-23, SOT-23-6): 200+ X gap, 250+ Y gap between rows
- Medium ICs (SOT-223, SMA): 250+ X gap
- Large components (ESP32 module, LCD): 350-400+ X gap, 350+ Y gap
- Buttons: 200+ X gap
- Always place large components (ESP32, LCD) on their own row or in their own module box
- Passive components (R/C, 2-pin): 100+ X gap is sufficient; they are small
- When using module boxes, ensure components + their fanout flags stay inside the box — add ~100 units margin from box edges

### Step 3: Get all pin positions

```javascript
const pins = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(compPrimitiveId);
// Each pin has: getState_PinNumber(), getState_PinName(), getState_X(), getState_Y(), getState_Rotation()
```

**引脚坐标语义（务必按这条理解——搞错会让整张图的引脚全被判悬空）：**

`getState_X() / getState_Y()` 返回的 `(x,y)` **就是引脚的电气连接点**。
`rotation` 指的是引脚**朝元件体内**绘制的方向，`pinLength` 是该方向上的绘制长度。

朝外方向（= 远离器件体；端口与导线往这个方向走）：

| `rotation` | 朝外方向 | 相对器件的含义 |
|---|---|---|
| 0 | `(+1, 0)` | 引脚从器件**右侧**伸出 |
| 90 | `(0, +1)` | 从**上侧**伸出 |
| 180 | `(-1, 0)` | 从**左侧**伸出 |
| 270 | `(0, -1)` | 从**下侧**伸出 |

> ⚠️ 上游原表述 "0 = pin points right (endpoint is to the right of component body)"
> 极易被误读成"`(x,y)` 是器件侧那端、端点要另算 `(x,y)+朝外×pinLength`"。
> **实测 `(x,y)` 已经是外端**——不要再加 `pinLength`。
> 存疑时用 `sch_Primitive.getPrimitivesBBox([pinId])` 看包围盒往哪边延伸，一眼可辨。

### Step 4: Define net assignments

Create a mapping `{designator}:{pinNumber} -> netName` based on the circuit design.
Classify each net:
- **Power nets** (3V3, 5V, VBUS, etc.) → use `createNetFlag("Power", ...)`
- **Ground net** (GND) → use `createNetFlag("Ground", ...)`
- **Signal nets** (everything else) → use `createNetPort("BI", ...)`
- **NC** (no connect) → skip

### Step 5: Create net flags/ports + connecting wires

For each pin, place a net flag/port **10 units outward from the connection point**,
where the connection point **is `(x, y)` itself**. Then draw a short wire
**starting at `(x, y)`** and ending on the flag/port.

```javascript
for (const e of entries) {
    let flagPrim;
    if (e.flagType === "power") {
        flagPrim = await eda.sch_PrimitiveComponent.createNetFlag("Power", e.net, e.fx, e.fy, e.flagRot, false);
    } else if (e.flagType === "ground") {
        flagPrim = await eda.sch_PrimitiveComponent.createNetFlag("Ground", e.net, e.fx, e.fy, e.flagRot, false);
    } else {
        flagPrim = await eda.sch_PrimitiveComponent.createNetPort("BI", e.net, e.fx, e.fy, e.flagRot, false);
    }
    // Wire: [pinX, pinY, flagX, flagY]
    const wire = await eda.sch_PrimitiveWire.create([e.pinX, e.pinY, e.fx, e.fy], e.net);
}
```

**Flag placement offset calculation**（`pinX/pinY` = `getState_X()/getState_Y()` = **连接点本体**）：
```
rot=0   → flag at (pinX+10, pinY),     flagRot=0,   wire=[pinX,pinY, pinX+10,pinY]
rot=180 → flag at (pinX-10, pinY),     flagRot=180, wire=[pinX,pinY, pinX-10,pinY]
rot=270 → flag at (pinX, pinY-10),     flagRot=270, wire=[pinX,pinY, pinX,pinY-10]
rot=90  → flag at (pinX, pinY+10),     flagRot=90,  wire=[pinX,pinY, pinX,pinY+10]
```

### Step 6: Execute via bridge — avoid shell escaping

When sending large payloads (99+ operations) via curl, **write the JSON payload
to a temp file** and use `curl -d @file` to avoid bash quoting issues:

```python
import json, subprocess
payload = json.dumps({"code": js_code})
with open("payload.json", "w") as f:
    f.write(payload)
result = subprocess.run(
    ["curl", "-s", "--max-time", "120", "-X", "POST",
     "http://localhost:49620/execute",
     "-H", "Content-Type: application/json",
     "-d", "@payload.json"],
    capture_output=True, text=True, timeout=180
)
```

## Coordinate System (CRITICAL)

**EasyEDA schematic Y-axis increases UPWARD** (first quadrant orientation).

- `sch_PrimitiveRectangle.create(topLeftX, topLeftY, width, height)`: `topLeftY` is the **TOP** boundary (larger Y value), `height` extends **DOWNWARD** (Y decreases). To draw a box with visual top-left at (30, 30) and size 540x360, use `topLeftX=30, topLeftY=390, width=540, height=360`.
- `sch_PrimitiveComponent.create(x, y, ...)`: larger `y` = higher on screen.
- `sch_PrimitiveText.create(x, y, ...)`: same, larger `y` = higher.

Getting this wrong causes module boxes to appear in the wrong quadrant (mirrored vertically). When placing module rectangles around components, compute `topLeftY = visualTopY + height`.

## Key Pitfalls

1. **Y-axis goes UP** - rectangle topLeftY is the top edge (large Y), height extends downward. Getting this wrong puts boxes in the wrong quadrant.
2. **Never inline JSON in bash -d '...' for large payloads** - Chinese characters
   or nested quotes break bash parsing. Always use `@file`.
3. **Always use `await`** on all EDA API methods - they return Promises.
4. **Set designator via async pattern**: `created.toAsync()` -> `setState_Designator()` -> `await done()`.
5. **`otherProperty` keys are English strings** - never use Chinese property names.
6. **EP (exposed pad) / mechanical pins** on USB-C etc. - skip if not in net assignment.
7. **`(x, y)` IS the connection point** - do NOT add `pinLength` to it. Placing the flag
   at `(x,y) ± pinLength` leaves **every pin in the sheet** reported as floating by DRC,
   while your own geometric check still says "distance = 0". Flag direction still comes
   from `rotation`; see `LESSONS.md` T-01 for the measured proof.
8. **Batch all flag+wire creations in one execute call** - much faster than
   individual curl calls. 127 flags + 127 wires (254 operations) complete in ~38 seconds.
9. **Component BBOX overlap** - always check component sizes before placing. Large
   components (ESP32, LCD, TF card) need 350+ X gap. Resistors/capacitors near
   large components must be offset enough to avoid BBOX collision.
10. **`ESCH_PrimitiveTextAlignMode` enum is NOT available as a global** in the
    bridge execution context. Passing `ESCH_PrimitiveTextAlignMode.CENTER_TOP`
    throws "is not defined". Use the **numeric value** directly: `1`=LEFT_TOP,
    `2`=LEFT_MIDDLE, `4`=CENTER_TOP, `5`=CENTER, `6`=CENTER_BOTTOM, `8`=RIGHT_MIDDLE.
    NOTE: this contradicts the `easyeda-api` skill's blanket rule "always use enum
    members" - for SCH text alignment, the enum is simply not injected into the
    execution context. Use numeric values.
11. **Tell real parts from net labels via `componentType`** - `getAll()` returns
    `componentType: "part" | "netport" | "netflag"`. Filter real components with
    `c.componentType === "part"`. (Net labels also show `designator === null` / `""`,
    but `componentType` is unambiguous and preferred.) A 30-component design with
    127-pin fanout yields 157 total component objects (30 real + 127 labels).
12. **Module boxes must accommodate fanout** - pins fan out 10+ units beyond each
    component edge. Size module rectangles with ~100 units interior margin so
    net flags/ports and wires stay inside the box. ESP32 (41 pins) needs the
    largest box (700x900+ schematic units).
13. **`fillColor: "none"`** makes rectangle backgrounds transparent (no fill).
    Use `"none"` explicitly - `null` gives the default fill which may obscure
    components placed behind the rectangle.
14. **Wire objects expose `.line` property, NOT `getState_Coordinates()`** -
    `w.line` returns `[x1, y1, x2, y2]` directly. `getState_Coordinates()`
    throws an error on wire objects. Use `w.line` and `w.net` to read wire
    geometry and net name.
15. **Deleting a component does NOT auto-delete its net flags or wires** -
    you must manually locate and delete the associated net flags/ports (via
    `sch_PrimitiveComponent.delete`) and wires (via `sch_PrimitiveWire.delete`).
    Orphaned net labels remain on the canvas otherwise.
16. **Tactile button same-pole pins must share a net** - on TS-1187A and similar
    4-pin buttons, pin1=pin2 (A=B) are the same pole, pin3=pin4 (C=D) are the
    same pole. NEVER assign different nets to same-pole pins. Typical wiring:
    pin1+pin2 -> signal (BOOT/EN), pin3+pin4 -> GND. Assigning pin1=BOOT and
    pin2=GND is a hard error - they are internally shorted.
17. **`execute_code` on Windows writes temp files to `tempfile.gettempdir()`**,
    NOT `/tmp/`. The Linux-style `/tmp/` path does not exist on Windows. Always
    use `os.path.join(tempfile.gettempdir(), "filename")` for temp payloads.
18. **`sch_PrimitiveWire.modify(id, {line})` clears `net`** when you omit it - pass
    `net` together with `line`, or restore it by looking up the net name from the label
    sitting at one of the wire's endpoints. Measured: 215 geometry-only edits wiped
    100% of the `net` fields (`LESSONS.md` T-03).
19. **DRC details are NOT available through the API.** `check(..., includeVerboseError:true)`
    still returns a boolean in V3.2.65. Run `check(false, true, false)` to open the bottom
    panel, then read `document.getElementById('schDrcPrimaryLog').textContent` - the
    `全部/致命错误/错误/警告/信息` counters live in that text and make a reliable
    before/after signal (`LESSONS.md` T-02).
20. **Never phrase a placement rule as "pin endpoint ± N".** That ambiguity is exactly what
    put a project's 216 pins off by `pinLength`. Always write the coordinate formula
    (`LESSONS.md` T-09).
21. **The bridge returns HTTP 500 when the response body is too large.** Returning a whole
    page source (~320k chars) fails, while `return s.length;` on the same page succeeds -
    the limit is on the *response*, not the API. Read big payloads in slices
    (`s.slice(i, i + 40000)`) and stitch them back (`LESSONS.md` T-11).
22. **`setDocumentSource()` is the way to add primitives you cannot create via the API**
    (verified for NO_CONNECT). Write the record text, append it, self-assert that the new
    source still starts with the old one, then write back. **Never write back a snapshot
    taken before someone (or something) modified the page** - that is how a manually placed
    NC was destroyed once. Always re-read immediately after writing (`LESSONS.md` T-10/T-13).
23. **Do NOT simulate keystrokes unless there is no alternative.** It steals the user's
    mouse and keyboard, and measured reliability was 1 success out of 4 attempts versus
    1 of 1 for the injection path (`LESSONS.md` T-13).

## Modifying an Existing Schematic

When the user asks to modify an already-placed schematic (change net
assignments, add/remove components, fix wiring), you must locate and delete
the old net flags/ports and wires BEFORE creating new ones.

### Reading wire positions

Wire objects returned by `sch_PrimitiveWire.getAll()` expose their coordinates
via the `.line` property (NOT `getState_Coordinates()`, which does not exist):

```javascript
const wires = await eda.sch_PrimitiveWire.getAll();
// Each wire: { primitiveId, line: [x1, y1, x2, y2], net: "GND", ... }
```

### Reading component positions

Component objects expose position via `getState_X()`, `getState_Y()`,
`getState_Rotation()`, `getState_Designator()`, `getState_Net()`:

```javascript
const comps = await eda.sch_PrimitiveComponent.getAll();
// Net flags/ports have designator === null (no isNetFlag boolean)
// Use position + net to identify which flag belongs to which pin
```

### Locate-and-delete workflow

1. Get all components and wires with their positions
2. Filter by coordinate proximity to the target component's pin locations
   (net flags are 10 units away from pin endpoints, wires connect the two)
3. Delete the old net flags/ports via `sch_PrimitiveComponent.delete(pids)`
4. Delete the old wires via `sch_PrimitiveWire.delete(pids)`
5. Delete the component itself if removing it: `sch_PrimitiveComponent.delete(pid)`
6. Create new components, net flags, and wires as needed

```javascript
// Example: find all net flags/ports near a specific area
const toDelete = comps.filter(c => {
  const x = c.getState_X(), y = c.getState_Y();
  const des = c.getState_Designator();
  return !des && x >= minX && x <= maxX && y >= minY && y <= maxY;
});
// Then delete by primitiveId
```

**Pitfall:** When deleting components, their associated net flags and wires are
NOT automatically deleted - you must delete them separately. Always clean up
both the component AND its fanout (flags + wires) to avoid orphaned net labels.

## Verification

After fanout, verify with:
```javascript
const comps = await eda.sch_PrimitiveComponent.getAll();
const wires = await eda.sch_PrimitiveWire.getAll();
const rects = await eda.sch_PrimitiveRectangle.getAll();
const texts = await eda.sch_PrimitiveText.getAll();

// comps includes real components + net flags + net ports
// Net flags/ports have designator === null (no isNetFlag boolean)
// Wire objects have .line property: [x1, y1, x2, y2]
const realComps = comps.filter(c => {
  try { return c.getState_Designator() != null; } catch(e) { return false; }
});

return {
  realComponents: realComps.length,
  totalComponentObjects: comps.length,  // real + flags + ports
  wires: wires.length,
  rectangles: rects.length,
  texts: texts.length,
  designators: realComps.map(c => {
    try { return c.getState_Designator(); } catch(e) { return "?"; }
  }).sort()
};
```

Expected breakdown (example: 30-component ESP32-S3 design):
- Real components: 30 (match placement count)
- Total component objects: 157 (30 real + 127 net flags/ports)
- Wires: 127 (one per non-NC pin)
- Rectangles: 5 module boxes + any border decorations
- Texts: 5 module labels

## 🔁 学习与进化纪律（每次落图 / 改图后必做，不许省）

本 skill 的"进化"靠三件事，缺一件就算任务没做完：

> 注：文中 `T-xx` 与 `LESSONS.md` 指向维护者本地实测台账（不随本仓分发）；
> 编号保留供溯源，正文结论已独立成立。

1. **收工前追加台账** —— 把本次**新验证**的结论按四段式（结论 / 证据 / 验证方式 / 日期）
   追加到 [`LESSONS.md`](LESSONS.md) 末尾。被推翻的旧条目**不要删**：
   追加新条目并注明"推翻 T-xx"。
2. **就地修 skill** —— 若本次踩到的坑**是本文自身写错/写歧义**造成的，
   必须**当场改本文**，不能只写台账。否则下次照着本文做还会再踩一遍。
3. **对账本库** —— 改完跑 `python tools/skillman.py doctor`（**退出码 0 才算完**）；
   若涉及路由/结构变动，同步 `ROUTE.md`。

**什么算"新验证的结论"**：跑通/跑不通的 API、实测的坐标与单位语义、被证伪的文档说法、
可复用的批量脚本姿势。**不算**：临时路径、一次性报错、猜测、文档摘抄。

> 反面案例：某工程 一轮落图埋了 100+ 个临时脚本、结论全留在工程里，skill 与台账一无所获
> → 下次从零再试探一遍。**那是"干了活但没有进化"。**

## Reference Example

See `references/esp32-s3-debugger-example.md` for a complete worked example:
30 components, 5 module boxes, 127-pin net fanout, including the full net
assignment table for an ESP32-S3 wireless debugger design.
