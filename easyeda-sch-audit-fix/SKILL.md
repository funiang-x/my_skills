---
name: easyeda-sch-audit-fix
description: 通过桥接审计并批量修补嘉立创 EDA Pro（EasyEDA Pro）原理图：几何法连通性核对、DRC、换料、标位号、端口修复、多部件元件修正、可读性重排。当用户说"帮我看看这张原理图有没有问题""原理图画得不好，你改一下""换掉图上某个错料""给元件标位号""核对网表/端口是否连上""这几条 DRC 处理一下"时使用。内含 18 个必踩的 API 坑与一套可复用的校验脚本。
agent_created: true
metadata:
  updated_2026_09_30b: 正文最顶插「[MUST] 开工前置 · 五问」（对症"装载≠读到"：长文被压缩会丢条款）；audit-fix 随附 scripts/（audit_sch · bridge · dangling · delete_part）
  updated_2026_09_30: 新增 坑19（串联元件被两端同名旗标并网短路，DRC 抓不到）/ 坑20（删端口连带删短线；勿把无导线旗标当冗余）；随附 scripts/audit_sch.py（正文 §2 一直引用却没给）；§2 补「坐标比较」与「换页等足」两条纪律
  version: "1.3.0"
  updated_2026_09_29: 纠正 §1.1（引脚连接点，原写法是错的）与 §1.4/§1.5（lib_Device 可用）；新增坑 13~18（EDA 静默改图 / net 改不动 / 多部件修法 / 禁源码注入组件 / 按页分组 / 文本 value 读不到）；顶部加「先读开工必读」指针
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


# 嘉立创 EDA Pro 原理图 · 审计与批量修补

> ## ⚠️ 先读这条：落图/连线必须用 `easyeda-schematic-net-fanout`
>
> 本 skill 只负责**审计与修补**。凡是**建连接**（放端口/画线）的活，
> 先加载 `easyeda-schematic-net-fanout`（上游 `github.com/easyeda/easyeda-enhanced-schematic-skill`，
> 嘉立创**官方** org）。它的两条硬规程，自己想不到：
>
> 1. **引脚的电气连接点就是属性 `(x, y)`。** 正确做法：
>    `端口 = (x,y) + 朝外方向×10`（`flagRot` = 引脚 rot），
>    `导线 = (x,y) → 端口`。**一个非 NC 引脚 = 一个端口 + 一根线。**
>    `rotation` 指向元件**体内**，朝外方向：`0→+x · 90→+y · 180→-x · 270→-y`。
>
>    ⚠️ **本条 2026-09-28 傍晚实测修正**：原文写"端口放在**引脚端点**外 10 单位"——
>    这句的"引脚端点"太容易读成 `(x,y)+朝外×pinLength`（那是**引脚画的另一端**）。
>    照错理解做，会让**整张图每个引脚**都被 DRC 判「悬空」，而几何核对还显示"距离=0"。
>    某工程 三页 216 个引脚就是这么栽的（修完悬空 216→12）。
>    判定办法：`sch_Primitive.getPrimitivesBBox([pinId])` —— 包围盒从 `(x,y)` 朝**体内**延伸。
>    **实测台账见 `easyeda-schematic-net-fanout/LESSONS.md` T-01。**
> 2. **`sch_PrimitiveWire.create(line, net?, …)` 的 `net` 不能省。**
>    漏传 → 网名变成 `$3Nundefined` → **致命错误**"网络名不正确，含有非法字符"。
>
> 反过来说：**唯一可信的验收是 EDA 自己导出的 DRC 日志**（`schDrcLog_*.txt`），
> 不是自己的几何自洽脚本。自己写的检查器只能用来找**别的**问题（位号、值、封装、短路）。
>
> ---
>
> ### 🚨 2026-09-29 起：**先读那份「开工必读」**
>
> 上面两条只是入口。**全部硬规矩（A~F 六组、覆盖坐标/EDA 静默改图/造元件/取数验收/设计可读性）
> 已蒸馏进** `easyeda-schematic-net-fanout/SKILL.md` 顶部的
> **「🚨 开工必读 · 本机硬规矩」**。**动手前先读那一节**，本 skill 只管审计与修补的方法。
>
> 与审计/修补最相关的几条（编号见那份速查）：
> - **B1/B2**：EDA 会把连通导线**自动合并**成折线；会**自动截断穿过引脚的导线** → 布线要显式绕开引脚
> - **B4**：`wire.modify` **改不动 `net`**（V4.1.60 起）→ 只能删了重建
> - **C1**：⛔ **不要用 `setDocumentSource` 注入组件记录**（会变「异常数据」致命错误）
> - **C3**：**多部件元件（双运放）四步修法** —— 一次消掉"位号不合规/多部件不完整/引脚与焊盘未对应"三条 DRC
> - **C6**：**改元件必须按页分组**，写前先 `openDocument(该页)`
> - **D4**：EDA ≥V4.1.60 点 DRC「导出」会弹「另存为」对话框 → 默认别点
> - **E3**：**可读性重构 = 清空重画**（备份 → 记网表 → 删全部导线标签 → 按网表重画 → 三项复核）
> - **E2**：**同器件同网的多脚 → 母线并联**（整组只留一个旗/标签）
>
> ## 默认技能链（原理图类任务，按序加载）
>
> | 阶段 | skill |
> |---|---|
> | 选型 / 架构 | `hardware-solution` |
> | **落图 / 放件 / 扇出 / 布局** | **`easyeda-schematic-net-fanout`（必读）** |
> | API 签名查询 | `easyeda-api` |
> | **审计 / 换料 / 标位号 / 修补** | 本 skill |
>
> **实测条目（`T-xx`）**：本文与兄弟 skill 里的 `T-xx` 引用，指向维护者本地的实测台账
> （只增不改，不随本仓分发）——编号保留供溯源；正文结论已独立成立。
> 落图/改图前重点看：T-01 引脚连接点、T-10 源码注入、T-13 注入 vs 按键。
>
> 本库 EasyEDA 系 skill 现有 **4 份**：`easyeda-api`（桥/API 底座）· `easyeda-schematic-net-fanout`（落图规程）·
> 本 skill（审计/修补）· `easyeda-viewer`（离线看图）——职责边界清晰。
> **动手前先走一遍本库路由**：`ROUTE.md` §2 装配清单（`硬件/审计` 一行）。
>
> ## NC 标志：API 写不了，但**可以纯文本注入**（2026-09-28 修订 · 免键鼠）
>
> ### 三条已证死的 API 路线（仍然成立）
>
> | 路线 | 结果 |
> |---|---|
> | `pin.setState_NoConnected(true)` | **方法不存在**。`typeof === "undefined"`；`ISCH_PrimitiveComponentPin` 的 prototype 链上 `getState_/setState_` 只有 `X/Y/Rotation/PinLength/PinName/PinNumber/PinShape/PinType/PinColor/OtherProperty/PrimitiveId`，**没有 NoConnected** |
> | `eda.sch_PrimitivePin.modify(pin, {noConnected:true})` | **静默空操作**（2026-09-28 二次实测确认）：方法存在、不报错、**返回引脚对象**，但源码里 `"key":"NO_CONNECT"` 计数纹丝不动。对照实验：把 `pinLength` 由 20 改 40，读回**还是 20**。（`sch_PrimitivePin` 管的是**符号页**引脚；原理图页上 `getAllPrimitiveId()` 返回 0） |
> | 放库里的「非连接标识」符号 | **库里没有**（`lib_Device.search("no connect"/"非连接")` 无结果） |
>
> ### ★ 正解：`setDocumentSource()` 注入 ATTR 记录（已验证）
>
> NC 在页面源码里**就是一条普通 ATTR 记录**，可以构造并追加。完整方法与证据见
> `easyeda-schematic-net-fanout/LESSONS.md` 的 **T-10 / T-11 / T-12**。摘要：
>
> ```
> {"type":"ATTR","ticket":<全局唯一自增>,"id":"<16位hex，全局唯一>"}||{"parentId":"<引脚primitiveId>","key":"NO_CONNECT","x":<pin.x>,"y":<-pin.y>,"value":"yes","zIndex":<整数>}
> ```
>
> - `parentId` = `<元件 primitiveId>-<引脚后缀>`（即 `pin.getState_PrimitiveId()` 的 `-e323` 那截）
> - **`y` 取负**（源码坐标系 y 与 API 的 `pin.y` 符号相反）
> - `value` 恒 `"yes"`；追加到源码末尾即可：`src + "|\n" + rec`
> - 源码须**分块取回**（整页 >30 万字符时桥报 HTTP 500，用 `s.slice(i, i+40000)`）
>
> **实测证据（某工程 INT 页）**：源码 319896 → 320368 字符，`NO_CONNECT` 57 → **60**，
> `setDocumentSource` 返回 `true`，回读**逐字节等价**（仅 `DOCHEAD.client`/`updateTime`
> 被 EDA 自行改写），DRC 悬空引脚 **5 → 1**（全部 62→57，警告 13→8）。
>
> ### ⚠️ 唯一真风险 = **陈旧快照覆盖**（这才是上次弄丢 NC 的真因）
>
> 本版本（V3.2.65）实测：**写回包含 NC 的源码，NC 不会被剥掉**——旧结论
> 「`setDocumentSource` 每次都会把已有 `NO_CONNECT` 剥掉，实测 3 次 3 次都丢」
> **未能复现**（抽样 5 条旧 NC 全部幸存）。
>
> 但上次"把用户手动打的一个 NC 弄没"这件事是真的，**最可能的机制是**：
> 先读了源码 → 用户又在界面里手动打了 NC → 你写回的却是**读之前那份快照**
> → 手动那次改动被整份覆盖掉。
>
> **所以铁律是**：**读源码与写源码之间不许有任何人/任何操作改动该页**；
> 写之前先 `getDocumentSource()` 存盘（那就是完备备份）；写完立刻回读比对。
>
> ### 备选（注入不可用时兜底）：OS 级模拟按键
>
> 桥里 `doSelectPrimitives([pinId])` + `zoomToSelectedPrimitives()` 选中聚焦，
> 再由系统脚本调 `user32.dll SetForegroundWindow` 抢 EDA 焦点（**抢不到必须中止**，
> 免得把 `c` 打到别的窗口），最后 `WScript.Shell.SendKeys("c", false)`。
> 前置：用户在「设置 → 快捷键」里把「放置非连接」绑到 `C`。
>
> **但它很脆**：实测同一批 4 个引脚，按键法 **4 次只成 1 次**（点击画布会清掉选中、
> 焦点易丢），而注入法**一次成功**。且它会**抢占用户的鼠标键盘**，用户在电脑前会被打断。
> **能用注入就用注入**（速度/可靠性/可回滚三项全胜）。
>
> ### 另两条绕过（须用户拍板，不推荐）
>
> ① DRC 设置里关掉「引脚悬空」检查项（会连真漏连一起掩盖）；
> ② 把未用脚各接一个同名网络（DRC 干净但**电气上等于短接**）。
>
> **发现 EDA 内置命令的技巧**：`sys_ShortcutKey.getShortcutKeys(true)` 能列出 600 条内置命令
> （比翻文档快），例如能查到 `{"shortcutKey":[""],"title":"放置非连接","documentType":[2],"scene":[2,3,4,5]}`。

适用：图已经画在 EasyEDA Pro 里，要通过 `easyeda-api` 桥接**读实况 → 找问题 → 原地改 → 验回来**。

## 随附脚本（`scripts/`，均已在本机实测跑通）

**公共件**：`bridge.py` —— `from bridge import run, pages`。端口**自动探测** 49620-49629；
`pages()` 返回 `{页名: uuid}`（用 `getAllSchematicsInfo()`：**别用** `getCurrentSchematicAllSchematicPagesInfo()`，
它在"当前没打开原理图文档"时返回**空数组**）；`open_page(uuid)` 会**等足 1500ms** 再返回
（换页太快会读到上一页源码，见 `easyeda-viewer/LESSONS.md` T-01）。

| 脚本 | 用途 | 用法 |
|---|---|---|
| `audit_sch.py` | **几何对账**（DRC 抓不到的那类）：① 两端同网　**①b 两侧同名旗标⇒并网短路**　② 一域多旗标名　③ 匿名网　④ 孤儿旗标 + **跨页命名网总表** | `python audit_sch.py` / `--page INT --page PWR` |
| `dangling.py` | **清死线 / 旗标残骸**（删件后留下、DRC 不报）。判据：从器件引脚出发做导线级 BFS，未被咬住的导线与孤立旗标即残骸 | `python dangling.py`（幂等，可直接重跑） |
| `delete_part.py` | **删件 + 清扇出**（连带该脚上的短线与线外端旗标；仅当短线外端无别的引脚/导线时才删旗标） | `python delete_part.py '[["页名",["R12"]]]'` |

> 三个脚本都在 `scripts/` 目录下直接跑（`bridge.py` 必须与它们同目录）。
> **注意**：`audit_sch.py` 只做**几何**判断，**"连没连上"的验收仍然是 DRC**（见顶部铁律）。

## 0. 前置

先加载 `easyeda-api` skill 拿 API 参考与桥接用法。桥接必须已在跑且 `edaConnected:true`：

```bash
for p in $(seq 49620 49629); do curl -s --max-time 1 http://127.0.0.1:$p/health; done
```

统一用一个 Python 小工具发 JS（**不要**用 curl 拼长 JS，Windows 下引号会炸）：

```python
# _eda.py
import json, urllib.request
BASE = "http://localhost:49620"
def exec_js(code, timeout=60):
    req = urllib.request.Request(BASE + "/execute",
        data=json.dumps({"code": code}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
def run(code, timeout=60):
    r = exec_js(code, timeout)
    if not r.get("success"): raise RuntimeError(r.get("error"))
    return r["result"]
```

**不要用 `%` 格式化拼 JS 字符串**（JS 里有 `% 360` 之类会炸）。用 `.replace("__PG__", pg)`。

## 1. 六个必踩的坑（先读，能省半天）

1. **⭐ 引脚坐标 `(x,y)` 就是电气连接点 —— 不是"根部"。**（**2026-09-29 纠正本条，原写法是错的**）
   原写"电气端点 = 根部 + 引脚长 × 方向"，那是**引脚画的另一端**，接在那里 = 没接。
   某工程 曾照此把全图 **216 个引脚**判成悬空，而自写几何核对还显示"距离=0"。
   正确模型：`rotation` 描述引脚**朝元件体内**绘制的方向，`pinLength` 是朝内的绘制长度；
   朝外方向 `0→(+1,0) 90→(0,+1) 180→(−1,0) 270→(0,−1)`；
   **端口 = `(x,y)+朝外×10`；导线 = `(x,y) → 端口`**。
   存疑时读 `sch_Primitive.getPrimitivesBBox([pinId])`：包围盒从 `(x,y)` **朝体内**延伸 ⇒ 那就是连接点。
   > 权威口径与全部实测：skill `easyeda-schematic-net-fanout` 的
   > **「🚨 开工必读 · 本机硬规矩」**（A 组）+ `LESSONS.md` **T-01 / T-09**。

2. **移动网络端口不能用 `toAsync()`。**
   `c.toAsync().setState_X(x).setState_Y(y).done()` 会把端口的 **Name（网名）抹成 null**，
   还会补一堆空属性 → **静默断网/短路**。移动端口必须：
   `delete(id)` → `createNetPort("BI", net, x, y, 0, false)` / `createNetFlag(type, net, x, y, 0, false)` 重建。
   移动/替换**器件**不受影响（delete + create 同坐标即可，几何一致时导线与端口会自动重连）。

3. **`sch_Netlist.getNetlist()` 必超时**（桥接硬限 30s）。改用：
   `eda.sch_ManufactureData.getNetlistFile("nl", "EasyEDA")` → `await f.text()`，秒回。
   ⚠️ 但该网表以 **Unique ID** 为 key：缺 Unique ID 的器件会**塌缩成一个条目**，
   所以它**不能**当连通性 oracle。连通性要自己用几何法算。

4. **⭐ `lib_Device` 可用（2026-09-29 纠正，原写法过时）。**
   `lib_Device.search(name)` → 器件记录（含 `uuid`）；**`lib_Device.get([uuid])` 必须传数组**，
   返回的 **`property.otherProperty` 就是权威属性表**（含 `Value` / `Tolerance` / `Supplier Part`）。
   按立创料号查：`lib_Device.getByLcscIds(["C17414"], undefined, true)` 同样可用。
   ⚠️ 两个坑：`get()` 传**裸字符串**返回 undefined；**批量查库要分批**（每批 ≤8 个型号，
   一次 20+ 会失败）。
   （"search 不带属性"这句仍成立 —— search 只给身份，属性要 `get([uuid])` 才拿得到。）

5. **器件属性/「值」的正规来源 = 库器件**（不是猜、不是从型号解码）。
   `lib_Device.search` + `get([uuid])` 拿 `otherProperty.Value`，**整表回写**
   `modify(id,{otherProperty: 整表})`（只传一个键会清掉其余）。
   库里没有时兜底用 `lib_Symbol.search(name)[0].description`。
   现成工具：`easyeda-schematic-net-fanout/scripts/eda_sch.py value --all --apply`。
   （旧写法"常返回 null → 只能读文档源码"已被 T-21 推翻。）

6. **源码记录格式**：每行 `{head}||{body}|` —— body 末尾有 **一个 `|` 终止符**，
   `json.loads` 前要 `rstrip("|")`；head 同理。源码里的 **y 是 API y 的负数**。

7. **`sch_Drc.check()` 取明细：API 不行，但 DOM 行。** `check(strict, ui, verboseError)` 三个参数
   都要给；`includeVerboseError:true` 在 **V3.2.65 实测仍返回 boolean**（文档承诺数组，未兑现），
   但它本身是**有效判据**：`check(false,…)`=非严格通过，`check(true,…)`=严格不通过。
   **拿明细/计数的可行路径**：`check(false, true, false)` 打开底部面板后读
   `document.getElementById('schDrcPrimaryLog').textContent` ——
   计数徽标 `全部(n)/致命错误(n)/错误(n)/警告(n)/信息(n)` 就在里面，
   **改前记基线、改后比对**，是最省事的闭环信号（实测 警告 69→13 就是这么验的）。
   > 面板是**虚拟列表**，只渲染 8 条消息封顶，`scrollTop` 刷不出来；计数徽标是准的。
   > `sch_Netlist.getNetlist()` 报 500、`getNetlistFile()` 因 `Unique ID` 空而组件全塌缩、
   > `sys_Log` 只有 `openProject` —— 都不可用。
   > **`sch_Drc.check` 是整设计级**（打开哪页跑都得同一组计数，T-23）。
   > **要全量日志**点面板内「导出」——⚠ **EDA ≥V4.1.60 会弹「另存为」对话框**（原生对话框，
   > 脚本关不掉）→ `eda_sch.py drc` **默认不点导出**，要日志才加 `--export … --click-export`（T-14）。

   **自建几何 DRC 降级为辅助**：仍可用于找**别的**问题（位号重复/值/封装/短路/单端网络），
   但**不能当"连上了"的验收**（见工作台根 `AGENTS.md` 铁律 2）。

8. **放 NC（无连接标志）。** 引脚对象 API 全无路（`setState_NoConnected` 不存在、
   `sch_PrimitivePin.modify(...,{noConnected:true})` 静默空操作）——
   但**走 `setDocumentSource()` 注入 ATTR 记录是可行的**（见文件顶部 NC 章 + 台账 T-10）。
   别再说"只能 GUI 右键点"。

9. **引脚的取用有坑，一律 `try/catch` 兜住**（否则整个 JS 抛错 → 桥接返回 **HTTP 500**，
   错误被吞掉很难查）。实测：
   - `getAllPinsByPrimitiveId(id)` 能正常返回 `pinNumber/pinName/x/y/rotation/pinLength/pinType`；
   - **引脚对象上根本没有 NC 相关方法**——`getState_NoConnected` / `setState_NoConnected`
     都不在 prototype 链上。NC 状态**只能**数源码里的 `"key":"NO_CONNECT"`；
   - `ISCH_PrimitivePin.getState_*()` 这套在**器件引脚**上并不齐全（只有 X/Y/Rotation/
     PinLength/PinName/PinNumber/PinShape/PinType/PinColor/OtherProperty/PrimitiveId），
     别假定文档写了就都在。**查之前先遍历 prototype 链**（见台账 T-08）。

10. **新建的导线不会立刻出现在 `getDocumentSource()` 里**（源码是滞后的快照）。
   但 `sch_PrimitiveWire.getAllPrimitiveId().length` 能立刻读到真实条数。
   所以：校验导线数量用 API，校验导线几何要用源码时记得先 `sch_Document.save()` 并重开文档。

11. **旋转器件要注意符号的"内部朝向"。** 同一个符号 `rot=90` 可能是横排、`rot=180` 可能是竖排
   （取决于符号画法）。**改完 rot 一定要 `await new Promise(r=>setTimeout(r,800))` 再读回引脚坐标**——
   `toAsync().done()` 后立刻读会拿到旧值。而且竖排时引脚可能落在一条竖直线上，
   从远处拉线过来会**穿过中间的引脚造成短路**。

12. **移动器件后必须重建它的端口**（端口跟着引脚端点走，不会自动跟随）。
   流程：删旧端点上的端口 → `toAsync()` 改 x/y/rotation → 等 800ms → 读回真实端点 → 按原名重建端口。

13. **⭐ EDA 会静默改你的图（"操作成功但结果不对"）。** 三条实测（台账 T-29/T-30/T-31）：
   - **连通导线自动合并**成一个折线对象 → `getAll()` 的 `w.line` 是**扁平坐标数组**
     `[x1,y1,x2,y2,…]`（每 4 个一段），按"线段数组"解析会只读到第一段、误判"导线丢了"；
   - **穿过引脚的导线被自动截断**（拆两段、留缺口）→ 你以为接上的两点被切开。
     **布线必须显式绕开不相干引脚**；
   - **带 NC 标记的引脚拒绝建导线**（`create failed!`）。诊断用**端点扫描**（固定一端、逐步移动另一端）二分边界。

14. **⭐ 改 `net` 只能删了重建（V4.1.60 起）。** `wire.modify(id,{line})` 或 `{line,net:""}`
   **都改不动** `net`（V3.2.65 时代"只传 line 会清空 net"的结论**已失效**）。
   另外**别给多段折线设 `net`** → 报「导线有多个网络名: X、X…」（**段数 = 重名个数**）。
   → 内部网络的正确画法是**导线 `net` 留空 + 一个净标签/旗**（台账 T-35 / T-36）。

15. **⭐ 多部件元件（双运放）的修法。** 病症：位号不合规 + 多部件不完整 + 引脚与焊盘未对应。
   根因常是**两个单元用了同一个 `subPartName`**（如都是 `OPA2197ID.1`）→ 抢焊盘、其余焊盘悬空。
   四步：① 用**库器件** uuid `create(comp, x, y, "X.2", …)`（用图上 `component.uuid` 会**超时且不落件**）
   ② 两单元位号都设**基位号**（`U1`，不是 `U1A/U1B`）③ `otherProperty["Multi-Part Group"]` 两单元同值
   ④ 两单元 `otherProperty` **整表完全相同**。查合法单元名：`lib_Symbol.get([symUuid]).subPartNames`。
   ⚠️ B 单元可能**没有电源脚**（V+/V− 只画在 A 单元）→ 换单元后要清掉接到旧电源脚的孤立线（T-39 / T-40）。

16. **⛔ 不要用 `setDocumentSource` 注入组件记录。** EDA 会标成
   **`[致命错误] 异常数据(为保证编辑器的正常使用，请先完成清理)`**，该组件无位号、无引脚。
   **造组件一律走 API `create`**；源码注入只用于**改属性类图元**（如 NO_CONNECT）。
   清理办法：读源码 → 按 `partId` 找出坏组件 id → 连同 `parentId` 指向它的 ATTR 一起摘掉 → 写回（T-41）。

17. **改元件必须按页分组**：`sch_PrimitiveComponent.modify` **只对当前打开的页生效**，
   混页写会报 `getState_ComponentType undefined`。每页写之前先 `openDocument(该页)`（T-24）。

18. **`sch_PrimitiveText.getAll()` 的 `value` 读不到**（空串）→ 想按内容匹配文本会 0 命中，**按坐标匹配**（T-37）。

19. **⭐ 串联元件被"自己的两端标签"短路（DRC 报不出来，必须自建检查）。**
   **症状**：0R / 串阻 / 磁珠形同虚设。**成因**：元件**两端挂了同名旗标** →
   EDA 按**网名**并网 → 两端短接。几何上两脚分属两个**独立连通域**，所以
   「同网检测」与「同坐标不同网名」两种常规扫描**都抓不到**。
   **修法**：把**其中一侧**的旗标改名（`LCD_BL_CTL` → `LCD_BL_PB0`），删原件 + 原位
   `createNetPort` 重建；验收 `LCD_BL_PB0 = {EVK1.11, R12.2}` / `LCD_BL_CTL = {R12.1, J5.28}`。
   **现成检查**：`scripts/audit_sch.py` 判据 **1b**（换件/重排后必跑）。
   实测：某工程 的 `R12`(1k 串阻) 就这么被短路了一整轮无人发现。

20. **⭐ 删网络旗标/端口会连带删掉它自己的短线。**
   `delete` 一个 netport/netflag 后按**原坐标**重建，端口位置能复位，但**那条把端口连到主网的
   短线已被一起删掉** → 端口变孤儿（DRC：`网络标识/网络端口 X 没有连接导线`）。
   **姿势**：改端口名前**先记录**它附近短线的两个端点，重建端口后**补建该短线**。
   ⛔ **别把"没有导线的旗标"当冗余直接删** —— 它可能是某个引脚**唯一的落点**。
   实测教训：某工程 AFE 页把 `AGND@(760,1000)` / `+5V_A@(760,1100)` 当冗余删掉，
   毁掉了 `U1.4`(V-)/`U1.8`(V+) 两处供电连接，DRC 随即报 10 个悬空脚。

其它：`getAll()` / `get(id)` 返回的常是**数组**（`Array.isArray(c)` 判断，取 `c[0]`）；
`getState_OtherProperty()` 时好时坏，别依赖。

## 2. 审计流程（只读，先别动图）

按顺序跑，每步都存证据：

1. **清点**：每页 `sch_PrimitiveComponent.getAll()` → 位号 / 器件名 / 值 / 封装 / 坐标。
   关注：`Designator` 是否为 `null`（= 未标注 `U?/R?`）、`Value` 是否为空、介质（`Temperature Coefficient`）与封装。
2. **导线数**：`sch_PrimitiveWire.getAllPrimitiveId().length`。某页为 0 = 纯端口连线，可读性差。
3. **连通性（几何法）**：端口坐标 vs 引脚**端点**坐标是否精确相等；不等的就是悬空。
4. **短路扫描**：把端口按坐标分组，同坐标出现**不同网名** = 短路。
5. **DRC**：`eda.sch_Drc.check(false, false, false)` → 返回 `false` 表示有错
   （EDA < v4.2 拿不到明细；`includeVerboseError=true` 只在 v4.2+ 有效）。
6. **网表**：`getNetlistFile` 导出，看有没有"该出现的网名没出现"。

**现成脚本**：`scripts/audit_sch.py`（只读对账，改图前后各跑一次）—— 逐页给出
「1 两端同网 / **1b 两侧同名旗标⇒并网短路** / 2 一域多旗标名 / 3 匿名网 /
4 孤儿旗标（未被导线咬住）」+ **跨页命名网总表**（用来逐条比对设计表）。

```bash
python scripts/audit_sch.py                        # 全工程所有原理图页
python scripts/audit_sch.py --page INT --page PWR  # 指定页
```

两条自建检查的纪律（本轮实测踩过，不遵守会把"全连通"误判成"全孤立"）：
- **坐标比较一律 `int(round(v))` 且两侧统一 tuple**：引脚常返回 `979.9999999999998` 而导线端点是
  `980`；JS 传回的是 **list**，Python 侧用 **tuple** 比永远不等。
- **跨页连读要等足**：`openDocument` + 0.7~0.9s **不够**，会**串页**（典型：AFE 的成员里冒出 PWR 的件、
  两页导出长度一模一样）。脚本内已用 1500ms；仍建议瞄一眼每页的「器件/导线/旗标」计数是否合理。

⚠️ **它只是辅助**：`连没连上` 的验收**仍是 DRC**（本文件顶部铁律）。

## 3. 修补流程

```
选料（place→读回校验） → 换件（delete+create 同坐标） → 补端口 → 跑 _verify_all.py → 不对就再修
```

- **标位号**（零风险，先做）：`eda.sch_PrimitiveComponent.modify(id, {designator: "R1"})`。
  按坐标映射批量标；双通道运放两个符号都标同一个位号（BOM 会归并）。
- **换件**：记录旧件的 `(x,y,rot)` 与位号 → `delete` → `create(新device, x, y, "", rot, false, true, true)`
  → `modify({designator: 原位号})` → **读回校验** `Value/TC/Footprint`。
- **换件后端口会悬空**（新符号引脚几何可能不同）：重跑几何检查，把悬空端口**删了重建**到新端点。
  ⚠️ 别用最近邻自动吸附——会把信号脚吸到 VCC 脚上，造成短路。**按引脚功能手工指定**。
- **页面命名**：`dmt_Schematic.modifySchematicName(schUuid, name)` /
  `modifySchematicPageName(pageUuid, name)`。
- **保存**：`eda.sch_Document.save()`（每页都要 `openDocument` 后再存）。

## 4. 收尾

- 跑 `_verify_all.py`：三页都应为 **0 悬空 / 0 短路 / 0 无名端口 / 0 缺位号**。
- 从**文档源码**导出 BOM 存档（比 `getState_OtherProperty()` 可靠）。
- 把"本轮做了什么 / 没做什么"写进项目文档，别只留在对话里。

## 5. 常见"画得不好"清单（可直接当 checklist）

| 症状 | 检查方式 |
|---|---|
| 器件零位号 | `Designator == null` |
| 位号前缀错乱（电感标 U?、电容标 U?） | 位号首字母 vs 器件类型 |
| 值/介质与设计文档不符 | `Value` / `Temperature Coefficient` 逐件对设计表 |
| 封装违反工艺约束（手焊出现 0402/QFN） | `Supplier Footprint` |
| 信号链零导线 | 每页导线计数 |
| 网络命名多套并存 | 端口网名去重 |
| 页面名与内容无关 | `dmt_Schematic.getAllSchematicsInfo()` |
| 核心板/关键器件型号选错 | 器件名逐字对设计文档（**最容易漏，代价最大**） |
| 悬空端口 / 同点不同网短路 | §2 的几何检查 |

## 6. 把"画得不好"变成"看得懂"：重排套路

零导线的页（全靠网名连接）**连接是成立的**，但图纸不可读。重排配方：

1. **先搬件，后连线。** 先把"离群的级"搬到它的网络旁（典型症状：运放 B 通道在 x=760，
   它的反馈网络在 x=2260）。搬件 = 删端口 → 改坐标 → 读回 → 重建端口。
2. **主链路画成一条实线。** 沿链路把相邻元件引脚端点用 `sch_PrimitiveWire.create([[x1,y1,x2,y2,...]])` 连起来
   （折线直接给一串坐标）。并联到地的支路用**竖直短线**从元件引脚拉到链路。
3. **连线前先核对两端端口的网名是否一致**——名字不同就是把两个网络短接，自建 DRC 会报
   「同网络多网名(短路)」。同名则导线只是"把已有连接画出来"，零风险。
4. **中间节点端口可以保留**（它们顺便给节点起了名），但 F1/F2 这种无语义的名字建议改成有意义的。
5. **加功能分区文字**：`sch_PrimitiveText.create(x, y, 内容, 0, "#1F5FA9", null, 字号, 粗体, false, false)`。
   把关键设计参数（fc、元件值、复算余量）直接写在图上——评审者不用翻文档。
6. 收尾必跑自建 DRC：**悬空引脚 / 短路 / 同点重复端口** 三项都要看，还要单独查"悬空导线"
   （导线两端都不碰引脚/端口 = 删件后的残骸，要删掉）。

## 7. 删件前先想清楚

删一个器件会**留下悬空的导线**（另一端还在）。顺序：删件 → 重新枚举导线端点 →
把两端都不碰引脚/端口的导线删掉 → 再跑 DRC。

反过来说：**冗余器件是告警大户**。本项目 INT 页两个 2×20 排母贡献了 79/156 条悬空引脚告警，
而它们的脚名只有 1~40、不携带任何信号信息（信号全在核心板模块符号上）——删掉后告警直接砍半。
判据：**这个器件的引脚上有没有承载"信号语义"？没有就是可删的冗余。**
