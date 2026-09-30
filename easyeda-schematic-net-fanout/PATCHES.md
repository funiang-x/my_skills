# PATCHES — 本机适配与安装记录

> 本文件是本 skill 相对上游的**唯一改动说明**。装第三方 skill 不静默改上游内容。
>
> **本机适配共 7 条**（编号即改动顺序）。想看"这台机器上什么是真的"，去看 [`LESSONS.md`](LESSONS.md)（实测台账）。

---

## 1. 来源

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/easyeda/easyeda-enhanced-schematic-skill（嘉立创EDA **官方** org） |
| 分支/下载方式 | `main`，codeload tarball（HTTP 200 / 9852 B，2026-09-28） |
| 仓库内容 | 3 个文件：`SKILL.md` 14663B、`README.md` 1530B、`references/esp32-s3-debugger-example.md` 7346B |
| 上游声明的版本 | `metadata.version: 1.2.0`，license MIT（仓库 settings 未标 license，以 frontmatter 为准） |
| 安装位置 | `~/.ai-skills/easyeda-schematic-net-fanout/`（共享 skill 库单点，各端经 Junction 可见） |
| 目录名取 `easyeda-schematic-net-fanout` | 与 SKILL.md frontmatter `name` 一致（上游仓库名与 skill 名不同） |
| **本机版本** | `metadata.version: **1.4.0**`（2026-09-28） |

## 2. 安全审计（静态文本分析，未执行任何被审内容）

| 检查 | 结果 |
|---|---|
| 无 `hooks/`、无 `scripts/`、无二进制 | ✅ 全文只有 3 个 Markdown，**没有会话启动自动执行的代码** |
| 危险关键词（`eval`/`exec(`/`os.system`/`popen`/`sudo`/`chmod`/`rm -rf`/`nohup`/`require(`） | ✅ 无匹配（唯一命中是文档正文提到的 `curl` 与 `subprocess.run(["curl", …])` 示例） |
| Base64 长载荷 | ✅ 无匹配 |
| 敏感路径（`.ssh`/`.aws`/`.env`/api key/token/password/credential） | ✅ 无匹配 |
| 外联 URL | 6 个：`localhost:49620`（本地桥）、`github.com/easyeda/easyeda-api-skill`、`jlc-ext.com`、`lceda.cn`、2 个 githubusercontent/oshwhub 展示链接 —— 全部指向本机桥或嘉立创官方站点 |

**评级：P0 风险 = 无。** 唯一 P1 提示（继承自已装的 `easyeda-api` skill，非本 skill 新增）：
它会让 Agent 向本地桥 `/execute` 提交 JavaScript，由嘉立创EDA 客户端执行 = **对工程文件的写入权**。
按工作台铁律 2，落图前须人确认目标工程，且"回读核对差异为 0"仍是进下一步的门。

## 3. 接口可用性静态核对（对已装 `easyeda-api` v1.1.36 的 references）

| 本 skill 用到的接口 | 本地 references 是否有 |
|---|---|
| `lib_Device.getByLcscIds()` | ✅ `classes/LIB_Device.md` |
| `sch_PrimitiveRectangle.create()` | ✅ `classes/EDA.md`、`_quick-reference.md` |
| `sch_PrimitiveText.create()` | ✅ 同上 |
| `sch_PrimitiveComponent.getAllPinsByPrimitiveId()` | ✅ `classes/SCH_PrimitiveComponent.md:1112` |
| `sch_PrimitiveComponent.createNetFlag('Power'/'Ground', net, x, y, rot, mirror)` | ✅ 签名逐参数对得上 |
| `sch_PrimitiveComponent.createNetPort('BI', net, x, y, rot, mirror)` | ✅ 签名逐参数对得上 |
| `sch_PrimitiveWire.create([x1,y1,x2,y2], net)` | ✅ 签名对得上 |

⚠️ 上述 3 个 net/wire 相关接口在本地文档里均标注 **"provided as a beta preview … Do not use this API in a production environment"**。
接口名与签名核对 = 已验证；**实跑通不通 = 已在 某工程 实战验证**（见 §5）。

---

## 4. 本机适配清单（7 条）

### 适配 1 · frontmatter 中文化 + 出处标注

`description` 追加中文触发句，并加 `metadata.source` / `metadata.local_patch` / `metadata.ledger`。
**理由**：上游描述纯英文，本机各端靠 description 语义匹配触发；工作台与用户口径均为中文
（`lceda` 场景下"画原理图/落图/扇出"是中文词）。

### 适配 2 · 新增「⚠️ 本机适配」小节（Overview 之后、Workflow Steps 之前）

- 桥端口**不要写死 `49620`** —— 本机桥在 49620-49629 自动选口
  （事实来源：`../easyeda-api/SKILL.md:48`）；
- 发给桥前**必须删 `//` 注释** —— 上游示例带注释，而 `easyeda-api/SKILL.md:213`
  规定代码按单行执行，原样贴会报错；
- 开工前置：桌面版已开 + **Gateway 扩展不自动重连** + 多窗口先 `POST /eda-windows/select`；
- **NC 脚不许静默跳过** —— 上游 Step 4 写 `NC → skip`，与工作台 `20_硬件链.md` §2
  "未用脚显式声明"冲突，**按工作台为准**。

### 适配 3 · 「实测 API 清单」→ 收敛为台账指针

原第 4 条「实测 API 清单」已**收敛成一句指针**：实测结论统一放进
[`LESSONS.md`](LESSONS.md)（只增不改的实测台账），避免同一批事实在 SKILL.md 与台账两处各写一份。
**冲突优先级：台账 > SKILL.md 正文 > 上游 README**。
其中最关键的一条被上提为独立「本机铁律」小节（见适配 5）。

### 适配 4 · 正文其余部分

上游正文其余部分保留原样（含 Step 6 里的 `localhost:49620` 示例，由适配 2 覆盖说明）。

### 适配 5 ⭐ · 新增「本机铁律：引脚连接点是 `(x,y)`，不是外端」

- EasyEDA 引脚模型：`(x,y)` = **电气连接点**；`rotation` 指向元件体内；`pinLength` 为朝内绘制长度。
- 朝外方向表 `0→(+1,0) · 90→(0,+1) · 180→(-1,0) · 270→(0,-1)`；
  正确接法 = **导线从 `(x,y)` 出发 → 端口放在 `(x,y)+朝外×10`**。
- 反例：某工程 三页把端口放 `(x,y)+朝外×(len+10)`、导线从 `(x,y)+朝外×len` 连过去
  → **216 个引脚全被 DRC 判「悬空」**，而几何核对自洽。
- 修复法：只把导线**靠引脚那一端**从外端移回 `(x,y)`，端口不动（本机已修 215 条）。
- 坑：`sch_PrimitiveWire.modify(id, {line})` **只传 line 会清空 `net`**，必须同时传 `net`。
- DRC 明细读法：`check(false,true,false)` 开底部面板 → 读
  `document.getElementById('schDrcPrimaryLog').textContent`（计数徽标 `全部/致命错误/错误/警告/信息` 在内）。
  API 侧 `verboseError:true` / `sch_Netlist` / `getNetlistFile()` / `sys_Log` 实测均不可用。

**同时就地纠正上游三处歧义**（这些是真正会害人的）：

| 位置 | 原文（歧义） | 改后 |
|---|---|---|
| Step 3 | `0 = pin points right (endpoint is to the right of component body)` | 明确 `(x,y)` **就是连接点**；给出朝外方向表；提示用 `getPrimitivesBBox` 复核 |
| Step 5 | `place a net flag/port 10 units away from the pin endpoint` | `10 units outward from the connection point, where the connection point is (x,y) itself`；导线**从 `(x,y)` 出发** |
| Pitfall 7 | 只说 flag 方向错会重叠 | 补：**不要把 `pinLength` 加到 `(x,y)` 上**，否则全图引脚被判悬空 |
| Pitfall 11 | 用 `designator == null` 判端口 | 改用 **`componentType === "part" / "netport" / "netflag"`** |

**为什么必须改正文而不只写台账**：这是**位置性歧义**，照原文做必然重犯
（某工程 三页 216 个引脚就是这么栽的）。只写台账、不动正文，等于把坑留在原地。

### 适配 6 ⭐ · 新增「画 NC（非连接标志）的正确姿势 = `setDocumentSource()` 注入」+ 配套脚本

- **否定**模拟按键路线：会抢占用户鼠标键盘；实测同一批 4 脚，按键法 **4 成 1**，
  注入法 **1 成 1**。除非注入不可用，否则不用按键。
- **正解**：NC 在页面源码里就是一条普通 `ATTR` 记录 —— 构造后追加，整体写回：

  ```
  {"type":"ATTR","ticket":N,"id":"<16hex>"}||{"parentId":"<pinId>","key":"NO_CONNECT","x":pinX,"y":-pinY,"value":"yes","zIndex":Z}
  ```

  要点：`ticket`/`id` 全局唯一；**y 取负**；`assert newSrc.startswith(src)` 自证非破坏；
  写完回读 + 跑 DRC 复核。
- **源码须分块取回**：整页 >30 万字符时一次 `return` 会 HTTP 500，用 `s.slice(i,i+40000)`。
- **记录流格式**：`|\n` 连接、每条 `HEADER||DATA`、末尾无分隔符；
  解析用 `partition('||')`（只切第一个）。
- **唯一真风险 = 陈旧快照覆盖**：读与写之间不许有人改动该页，否则整份覆盖人工改动。
- 顺带新增 **Pitfall 21~23**（大响应 500 / 注入姿势与陈旧快照风险 / 不要模拟按键）。

**证据**（某工程 INT 页）：源码 319896→320368，`NO_CONNECT` **57→60**，桥返回 `true`，
回读**逐字节等价**（仅 `DOCHEAD.client`/`updateTime` 被 EDA 改写），
DRC 悬空引脚 **5→1**、全部 **62→57**、警告 **13→8**。

> **同时修正了一条旧结论**：`easyeda-sch-audit-fix` 曾记「`setDocumentSource` 每次调用
> 都会把已有 `NO_CONNECT` 剥掉，实测 3 次 3 次都丢」——**本版本（V3.2.65）未复现**，
> 抽样 5 条旧 NC 全部幸存。该"弄丢 NC"事件最可能的真因是**写回了过期快照**，已在两处写明。

### 适配 7 · 新增 `LESSONS.md` 台账 + 「学习与进化纪律」章节

skill 目录下新增 [`LESSONS.md`](LESSONS.md)，收录**亲手验证过**的事实（每条四段式：
结论 / 证据 / 验证方式 / 日期，并标 已验证 / 未验证 / 不适用）。首版 T-01~T-09；
2026-09-28 深夜补 T-10~T-13（源码注入 / 大响应上限 / 记录流格式 / 注入 vs 按键）。
`SKILL.md` 顶部改为**指针**，并新增章节 **「🔁 学习与进化纪律」**：每次落图/改图后必做三件事
（① 追加台账 ② 若坑来自本文自身写得歧义则**当场改本文** ③ 跑工作台体检对账）。

**同一轮修掉兄弟 skill 的错规则**：`easyeda-sch-audit-fix/SKILL.md`
① 顶部"端口放在**引脚端点**外 10 单位"同源歧义 → 改坐标式子；
② NC「只能人工右键」→ **可自动化**（先记 OS 按键，2026-09-28 深夜再修正为**源码注入优先**）；
③「`sch_Drc.check()` 拿不到明细，必须自建 DRC」→ **可读 DOM 计数徽标**，自建几何 DRC 降级为辅助；
④ `getAllPins()` 的 `pinLength`/`noConnected` 会抛异常 → 细化为
（`pinLength` 正常；引脚对象**根本没有** NC 相关方法）。

---

## 5. 验证

- 本机版本 **1.5.0**（2026-09-28 深夜二轮）：新增「拿全量 DRC」小节与「清 DRC 残留对症表」；
  台账补 T-14~T-20。
- 文件清单：`SKILL.md`、`LESSONS.md`、`PATCHES.md`（本文件）、`PATCHES.diff`（对上游逐行差异）、
  `README.upstream.md`（上游 README 改名保留出处）、
  `references/esp32-s3-debugger-example.md`、**`scripts/inject_nc.py`（本机新增，适配 6 的可执行实现）**。
- Junction 可见性：已接的各端 skills 目录均可见本目录与 `LESSONS.md`（单点安装、各端共享生效）。
- 体检：`python tools/skillman.py doctor` 会核对本 skill 的接线与可调用性。
- `scripts/inject_nc.py`：`py_compile` 通过；**正例实测**（某工程 INT 页 3 处注入成功、
  回读逐字节等价）；**负例实测 4 类**（不存在的脚号 / 不存在的位号 / 不存在的页 /
  重复提交已有 NC）均按预期报错且**不写回**，退出码正确（0 / 1 / 2）。
- **三态口径**：
  - 静态审计 + 接口签名核对 + 安装可见性 = **已验证**；
  - **端到端落图的 API 可用性 = 已验证**（2026-09-28 某工程 实战：桥连通，器件 / 引脚 / 选中 /
    聚焦 / 读源码 / DRC / 改线 / 注入 NC 均实测跑通）；
  - **本 skill 的完整规程（分区放件 → 逐引脚 fanout）是否被端到端执行过 = 未验证**——
    某工程 那次是现写脚本摸索的，规程本身还没被完整走过一遍。

---

## 6. 重装 / 升级后恢复本机适配（必读）

上游更新后重装会**覆盖 `SKILL.md`**——本机 7 条适配随之丢失。恢复步骤：

1. **重装前先备份本机版**（关键，别跳过）：
   ```bash
   cp -r ~/.ai-skills/easyeda-schematic-net-fanout ~/.local/skills-backup-<YYYYMMDD>/
   ```
2. 装上游新版 → 按 §4 的适配 1~7 逐条重做。
   篇幅最大的是适配 3/5/6/7，可直接从最近的
   `~/.local/skills-backup-*/easyeda-schematic-net-fanout/` 里整段取回
   （`SKILL.md` 与 `LESSONS.md` 一起拿）。
3. 重装后验收四项：
   - `grep -c "本机铁律" ~/.ai-skills/easyeda-schematic-net-fanout/SKILL.md` 应 ≥ 1；
   - `grep -c "setDocumentSource" ~/.ai-skills/easyeda-schematic-net-fanout/SKILL.md` 应 ≥ 1（适配 6 在）；
   - `test -f ~/.ai-skills/easyeda-schematic-net-fanout/LESSONS.md && echo OK`（台账在）；
   - 各端可见：`ls <任一已接端>/skills/easyeda-schematic-net-fanout/SKILL.md`（Junction 穿透）；
   - 跑 `python tools/skillman.py doctor`——会确认接线与 skill 可调用性（掉了会报红）。

**建议**：重装前先复制一份最新版到备份目录（含 `SKILL.md` 与 `LESSONS.md`）。

---

## 7. 回滚

```bash
rm -rf ~/.ai-skills/easyeda-schematic-net-fanout
```

若你把本 skill 登记进了路由表 / 体检清单 / 已接端，一并撤销对应条目
（`python tools/skillman.py doctor` 复核）。
