# PREREQUISITES — 拿到本仓到能开干，中间还差什么

> **公开层 23 个 skill，clone + 安装即可全流程开工。**
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
⚠ 本地层 skill 未装（不随本仓发布，属已知状态）：easyeda-agent,ppt-master
```

| 缺的 | 影响 | 去哪补 |
|---|---|---|
| `easyeda-agent` | 与 `easyeda-api` **配合使用**（它出 typed actions，api 出桥与 API 参考）——没它时降级为 api 单跑 | §3.2（可选） |
| `ppt-master` | 汇报 PPT 链——没它也能写文档 | §3.1（可选） |

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

### 3.1 本地层第三方大件（2 个，由 `.gitignore` 划定，不随本仓发布）

| 名字 | 是什么 | 怎么来 |
|---|---|---|
| `ppt-master` | 汇报 PPT 链（84 MB / 13,000 文件） | 装上游 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) |
| `easyeda-agent` | 落图 / 布局 / 布线的 CLI 化规程（2.7 MB） | 见 §3.2 |

**缺了会怎样**：`硬件/落图` 少一个加强件（依旧可走 `easyeda-api` 自带规程）；
`文档/汇报PPT` 无 skill 可用（按工程自己的文档规范手工产出）。其余流程不受影响。

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

---

## 4. 一句话总结

| 谁 | 能不能开箱即用 |
|---|---|
| **任意 AI / 任意机器** | ✅ 公开层 23 个 skill clone + `install` 即得；缺的只是真工具链与 2 个可选大件（**都有降级路径**） |
| **要落图加强 / 汇报 PPT** | 按 §3 单独安装两个可选件——不装也各有替代 |