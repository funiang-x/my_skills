# PREREQUISITES — 拿到本仓到能开干，中间还差什么

> **公开层 24 个 skill，clone + 安装即可全流程开工。**
> （2026-09-30 起：原先 6 个"平台自带、非 Trae 用户拿不到"的 skill 已由**自研替代版进仓**，
> 本仓对 STM32 + J-Link + 嘉立创 EDA 主链**自洽**。）
> 剩下要自备的只有两类**可选件**：真工具链（缺了各有降级路径）与两个第三方大件 skill。
> **先读完这份，再跑 `install`。**

## 快速自检

装完跑一次：

```bash
python tools/skillman.py doctor
```

它会告诉你接线通不通、skill 可调用、路由一致。

**新机 clone 后第一次跑**，唯一可能出现的警告是本地层第三方大件未装：

```
⚠ 本地层 skill 未装（不随本仓发布，属已知状态）：easyeda-agent,ppt-master,datasheets,lcsc,jlcpcb,bom
```

| 缺的 | 影响 | 去哪补 |
|---|---|---|
| `easyeda-agent` | 与 `easyeda-api` **配合使用**（它出 typed actions，api 出桥与 API 参考）——没它时降级为 api 单跑 | §3.2（可选） |
| `ppt-master` | 汇报 PPT 链——没它也能写文档 | §3.1（可选） |
| kicad-happy 四件 | `硬件/深读` 的提取引擎——没它时 `datasheet-study` 走子代理读 PDF 降级 | §3.5（可选） |

**这不是缺陷，是分层**——所以 `doctor` 把它算**警告**不算错误。真正会算**错误**的是
「**公开层** skill 被引用却不在」，那说明表写错了或仓不完整。

**若报某端未接** → 见 §1。

---

## 1. 第 0 层 · 装到客户端（必做，clone 不等于装好）

客户端靠 `<客户端 skills 目录>/<名字>/SKILL.md` 发现 skill，所以必须挂接：

```bash
git clone https://github.com/funiang-x/my_skills
cd my_skills
python tools/skillman.py install            # 干跑：先看它要做什么
python tools/skillman.py install --apply    # 落地
```

`install` 做两件事，**第二件才是关键**：

1. 把各客户端的 skills 目录接到本仓（Junction / symlink）
2. 往各客户端的**用户级规则文件**写一段「全局门」指针——「开工先读 `ROUTE.md`」

**没有第 2 件，AI 不知道要读 `ROUTE.md`，整条触发链的起点就没了。**

> ⚠️ 全局门里写的是 `~/.ai-skills/ROUTE.md`。**clone 到别的位置**要改这段指针
> （`install` 会按实际路径写，但**换位置后要重跑一次**）。
> ⚠️ `install` 只处理它**探测到**的客户端；**Qoder** 没有 skills 目录约定，只走规则门。
> ⚠️ 不在探测清单里的客户端（Cursor / Windsurf 等）：按 `agent-skill-wiring` skill 的
> 「手工接线」节处理——**没有 skills 机制的 agent 也能用**：让它读 `ROUTE.md`，按表直接读
> `<库>/<skill>/SKILL.md` 正文干活即可（协议本身不依赖任何平台特性）。

## 2. 第 1 层 · 工具链（用到哪个装哪个；缺了各有降级路径）

**仓库脚本本身零依赖**：`preflight.py` / `skillman.py` / `skill_audit.py` / `gate.py` /
`_gatecore.py` **只用标准库**，只要 **Python 3 + git**（`_check_public.py` 要 `git ls-files`）。

skill 正文要的是真工具——**缺了不等于不能开工**：

| skill | 外部依赖 | 缺了怎么办（降级路径） |
|---|---|---|
| `stm32-hal-cli-flow` | `arm-none-eabi-gcc` · `cmake` · `ninja` · `python3` | 装工具链；或改走工程自带入口 |
| `stm32-hang-triage` | 同上 + J-Link 工具链 | 先装 J-Link（`--detect` 会报缺） |
| `build-cmake` | `cmake`（+ Ninja/Make 生成器） | `--detect` 报 `environment-missing`，**不要硬拼命令** |
| `flash-jlink` | SEGGER J-Link 工具包（JLink.exe / JLinkExe / JLinkRTTLogger） | `--detect` 报缺；可用环境变量 `JLINK_DIR` 指向安装目录 |
| `debug-jlink` | J-Link 工具包 + `arm-none-eabi-gdb` | `--gdb` 可显式指定 gdb 路径 |
| `serial-monitor` / `serial-shell` | `pyserial`（`pip install pyserial`） | 脚本报 `environment-missing` 并给替代：PuTTY / `screen` |
| `static-analysis` | `cppcheck` / `clang-tidy` | 报缺并给安装指引；或优先用工程自带 lint |
| `easyeda-api` | Node + 在本 skill 目录跑一次 `npm install` | 改用 EDA 客户端自带导出 / 操作 |
| `easyeda-viewer` | Node（≥18） | 不装则跳过离线看图 |
| `install-github-skill` | `git` · `tar` | — |

## 3. 第 2 层 · **不在本仓里的东西**（都可选）

### 3.1 本地层第三方件（2 个大件 + kicad-happy 摘装四件，由 `.gitignore` 划定，不随本仓发布）

| 名字 | 是什么 | 怎么来 |
|---|---|---|
| `ppt-master` | 汇报 PPT 链（84 MB / 13,000 文件） | 装上游 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) |
| `easyeda-agent` | 落图 / 布局 / 布线的 CLI 化规程（2.7 MB） | 见 §3.2 |
| `kicad-happy` 四件（`datasheets`/`lcsc`/`jlcpcb`/`bom`） | datasheet 结构化提取 / LCSC 搜器件下手册 / 打样装配规则 / BOM 生命周期（103 文件） | 见 §3.5 |

**缺了会怎样**：`硬件/落图` 少一个加强件（依旧可走 `easyeda-api` 自带规程）；
`文档/汇报PPT` 无 skill 可用（按工程自己的文档规范手工产出）；
`硬件/深读` 走 `datasheet-study` 自带的子代理读 PDF 降级；`硬件/生产` 少两份备用知识册。其余流程不受影响。

> **平台机制目录 `shared/`**：Trae CN 平台自带 skill 的公共依赖，本库自研版**不再引用**；
> 留在 `.gitignore` 名单里只是防误入仓。

### 3.2 `easyeda-agent`（**与 `easyeda-api` 配合使用**，需另装）

EDA 生态的 [zhoushoujianwork/easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent)（MIT，自带 CLI/daemon/连接器）。
`硬件/落图` 的**正规做法是两个一起装**：agent 出规程与 typed actions，`easyeda-api` 出 WebSocket 桥与 API 参考；
**只装 api 也能干活**，`doctor` 对此只警告（本地层缺失）。

**daemon 要常驻**：`easyeda daemon start --auto-update-skill=false`（关掉它的 skill 自动同步——否则会顶掉
你的 skill 接线），再做登录自启（照 `easyeda-api` 那份**幂等 VBS** 的模式：先 `easyeda daemon health` 判活，退 0 就跳过）。

⚠️ **装它时必带 `EASYEDA_INSTALL_SKILLS=none`**：否则它会把 skill 写进客户端的 skills 目录，
与 `skillman` 的管理机制**打架**（双头管理）。skill 单独放进本库目录，再用 `skillman install --apply` 挂到各端。

### 3.3 EDA 侧 GUI 前置（**不做就完全无法落图**）

`easyeda-*` 驱动的是**运行中的**嘉立创 EDA 专业版：

1. 在 EDA「扩展管理器」里安装 **Run API Gateway** 扩展，并**勾选"允许外部交互"**
   （菜单栏出现「API Gateway」= 已加载）
2. 在 `easyeda-api/` 目录里跑一次 `npm install`（桥服务的 Node 依赖）

链路：**AI → `easyeda-api` skill → Bridge Server(49620-49629) → Run API Gateway 扩展 → 嘉立创 EDA 专业版**
⚠️ 扩展**不会自动重连**：EDA 先于桥打开、或桥中途重启时，要在 EDA 里重载一次扩展。

### 3.4 本地扩展层（可选，**不属于本仓**）

**本仓不依赖任何"宿主工作台"**。机器事实（路径 / 端口 / 版本）与只适合本机的 skill / 私有台账，
按 `ROUTE.md` §2.7 自建**本地扩展层**：放进本库目录 → 加进 `.gitignore` 本地层名单 →
把任务类型登记进 `ROUTE.md` §2 对应行（`tools/skillman.py doctor` 校验无死链）。

### 3.5 kicad-happy 四件摘装（`硬件/深读` 的引擎，2026-10-06 审计安装）

上游 [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)（MIT），11 个硬件分析 skill 的集合；
本库只摘**与 EDA 无关**的四件进本地层（`.gitignore` 划出，不随本仓发布）：

| 摘件 | 管什么 | 登记在 |
|---|---|---|
| `datasheets`（79 文件） | datasheet PDF 结构化提取（引脚/电气特性/外设）+ 按 MPN 缓存 | `硬件/深读` |
| `lcsc`（9 文件） | LCSC 搜器件 / 下手册（jlcsearch 社区 API，无 key） | `硬件/深读` |
| `jlcpcb`（1 文件） | JLCPCB 打样/装配规则知识册 | `硬件/生产` |
| `bom`（14 文件） | BOM 生命周期（深绑 KiCad 符号属性，立创用户备用） | `硬件/生产` |

**装法**（重装 / 升级照做；升级即覆盖，上游文件不改一字）：

```bash
curl -sL -o kh.tar.gz "https://codeload.github.com/aklofas/kicad-happy/tar.gz/refs/heads/main"
tar -xzf kh.tar.gz && cp -r kicad-happy-main/skills/{datasheets,lcsc,jlcpcb,bom} <库根>/
```

**审计留证（2026-10-06，纯静态、不执行被审内容）**：危险关键词全扫仅命中自清理（`rm -rf` 只指自己的
缓存目录）与 poppler 调用（subprocess 只跑 `pdftotext` / `pdfinfo`）；外联仅 LCSC/JLCPCB 官方域 +
jlcsearch 社区 API + schema 命名空间（`kicad-happy.local`，非真实端点）；无 base64 载荷、无敏感路径外传；
全部脚本 `py_compile` 通过。**评级：可装**。

**两条使用约定**（写在消费方 `datasheet-study`，由它负责翻译）：上游文档的 `skills/<名>/…` 前缀在本库
按**库根 `<名>/…`** 解析（四件直接在库根一级）；上游写 `python3` 处一律按 `python` 执行（Windows）。
`datasheets` 的页选择脚本依赖 poppler——缺了走 `datasheet-study` 的降级路径。

### 3.6 立创EDA 扩展（可选增强，不属于本库 skill）

`easyeda-ai-assistant`（[jifengshandian/easyeda-ai-assistant](https://github.com/jifengshandian/easyeda-ai-assistant)，
Apache-2.0）：立创EDA专业版原生扩展，定位"不帮你画图，画完帮你查"——悬空引脚 / DRC / 电源拓扑 /
引脚级问题（BOOT0 悬空、NRST 缺上拉、去耦电容位置等）审查，需要深度联动时可开它的只读 MCP。
**装法**：立创EDA「扩展管理器」搜 "AI Schematic Assistant"。
**没装走回退**：`easyeda-viewer` / `easyeda-api` 审计链（导出 JSON 离线查）——WORKFLOW ③④ 的画后审查主干不依赖它。

---

## 4. 一句话总结

| 谁 | 能不能开箱即用 |
|---|---|
| **任意 AI / 任意机器** | ✅ 公开层 24 个 skill clone + `install` 即得；缺的只是真工具链与可选第三方件（**都有降级路径**） |
| **要落图加强 / 汇报 PPT** | 按 §3 单独安装两个可选件——不装也各有替代 |