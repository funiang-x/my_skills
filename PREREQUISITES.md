# PREREQUISITES — 拿到本仓到能开干，中间还差什么

> **本仓是「骨架」，不是「全套」。** clone 下来只是拿到说明书 —— 下面三层缺任何一层，
> 都会在某个环节断掉。**先读完这份，再跑 `install`。**

## 快速自检

装完跑一次：

```bash
python tools/skillman.py doctor
```

它会告诉你接线通不通、skill 可调用、路由一致。

**新机 clone 后第一次跑，「路由一致性」会报本地层 skill 未装**——实测就是这 3 个：

```
⚠ 本地层 skill 未装（不随本仓发布，属已知状态）：build-cmake,debug-jlink,easyeda-agent
```

| 缺的 | 去哪补 |
|---|---|
| `build-cmake` · `debug-jlink` | §3.1（Trae CN 自带，**非 Trae 用户拿不到**） |
| `easyeda-agent` | §3.2（**需另装**） |

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
> ⚠️ `install` 只处理它**探测到**的客户端。Qoder 没有 skills 目录约定，只走规则门。

## 2. 第 1 层 · 工具链

**仓库脚本本身零依赖**：`preflight.py` / `skillman.py` / `skill_audit.py` / `gate.py` /
`_gatecore.py` **只用标准库**，要 **Python 3 + git**（`_check_public.py` 要 `git ls-files`）。

但 **skill 正文要的是真工具**——用到哪个装哪个：

| skill | 外部依赖 |
|---|---|
| `stm32-hal-cli-flow` | `arm-none-eabi-gcc` · `cmake` · `ninja` · `python3` |
| `stm32-hang-triage` | 同上 ＋ J-Link 工具链 |
| `easyeda-api` | Node + 在本 skill 目录里跑一次 `npm install` |
| `easyeda-viewer` | Node（≥18） |
| `install-github-skill` | `git` · `tar` |

## 3. 第 2 层 · **不在本仓里的东西**（最大的坑）

### 3.1 本地层 skill（8 个，由 `.gitignore` 划定，不随本仓发布）

它们与公开层**一视同仁**地挂到各客户端，只是不进仓：

| 类别 | 名字 | 怎么来 |
|---|---|---|
| 平台自带 6 | `build-cmake` · `debug-jlink` · `flash-jlink` · `serial-monitor` · `serial-shell` · `static-analysis` | 随 **Trae CN** 自带；**非 Trae 用户拿不到**——需要时自己写一份等价的 |
| 第三方 2 | `ppt-master` | 装上游 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) |
| | `easyeda-agent` | 见 §3.2 |

**缺了会怎样**：`硬件/落图` 的必载 skill 装不到 → **硬件主链断在第 ③ 步**；
烧录 / 串口 / 静态分析 / 汇报 PPT 这些任务类型**无 skill 可用**。

### 3.2 `easyeda-agent`（硬件落图链的关键，**需另装**）

它**不在本仓**（第三方大件，2.7 MB / 201 文件，MIT，自带 `easyeda update` 自更新）。
但 `ROUTE.md` §2 的 `硬件/落图` 行**点名了它**——所以**不装它，`doctor` 会报
`路由引用了不存在的 skill：easyeda-agent`**。

装法见上游 [zhoushoujianwork/easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent)。
⚠️ **必带 `EASYEDA_INSTALL_SKILLS=none`**：否则它会把 skill 写进客户端的 skills 目录，
与 `skillman` 的管理机制**打架**（双头管理）。skill 单独放进 `~/.ai-skills/easyeda-agent/`，
再用 `skillman install --apply` 挂到各端。

### 3.3 EDA 侧 GUI 前置（**不做就完全无法落图**）

`easyeda-*` 驱动的是**运行中的**嘉立创 EDA 专业版：

1. 在 EDA「扩展管理器」里安装 **Run API Gateway** 扩展，并**勾选"允许外部交互"**
   （菜单栏出现「API Gateway」= 已加载）
2. 在 `easyeda-api/` 目录里跑一次 `npm install`（桥服务的 Node 依赖）

链路：**AI → `easyeda-api` skill → Bridge Server(49620-49629) → Run API Gateway 扩展 → 嘉立创 EDA 专业版**
⚠️ 扩展**不会自动重连**：EDA 先于桥打开、或桥中途重启时，要在 EDA 里重载一次扩展。

### 3.4 宿主工作台（本机专属，**不在本仓**）

`ROUTE.md` §2.5 与 `WORKFLOW.md` §6 都指向「宿主工作台」——那是**每台机器自己的**东西：
机器事实（路径 / 端口 / 版本）· 各阶段的本机实现细节 · 任务类型的本机扩展。

**本仓只承诺"通用能力"，不承诺"某台机器怎么干活"。** 你要自己维护那份工作台。

---

## 4. 一句话总结

| 谁 | 能不能开箱即用 |
|---|---|
| **本仓作者那台机器** | ✅ 能 —— 本地层 8 个 + 宿主工作台都在 |
| **任意 AI / 另一台机器** | ❌ **不能** —— 要 clone + `install` + 补本地层 skill + 自备工作台，才到约 80% |

**这不是缺陷，是分层**：`README.md` 讲的是"这个仓里有什么"，
本文讲的是"要跑起来还差什么"。**两份都要读。**
