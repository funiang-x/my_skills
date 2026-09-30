---
name: easyeda-viewer
description: >-
  用离线单文件查看器（easyeda/easyeda-viewer）预览/自检嘉立创EDA专业版原理图与 PCB。
  把运行中的 EDA 工程页面导出成 .esch2，再用 viewer 渲染成可看的图纸（浏览器预览）
  或做无头渲染自检（对象数 / 未知类型数）。当需要在**不打开 EDA 客户端**的情况下
  看原理图、给原理图做视觉复核、留一份可分享的离线快照，或验证落图结果是否
  「真的画上了」时使用。也支持打开 .epro2 / .eprj3 / .epcb2 等工程文件。
license: Apache-2.0 (viewer 本体)
compatibility: 需要先 clone + npm install + 构建 easyeda-viewer（环境变量 EASYEDA_VIEWER_DIR 指向它，默认 ~/easyeda-viewer）；从 EDA 导出页面需 easyeda-api 桥
metadata:
  agent_created: true
  viewer_repo: https://github.com/easyeda/easyeda-viewer
  viewer_local: ${EASYEDA_VIEWER_DIR:-~/easyeda-viewer}
  viewer_version: 0.3.0
  audited: 静态审计 P2 安全（无 curl/subprocess/rm -rf/eval；外联仅 127.0.0.1 与 SVG 命名空间；无敏感路径、无 hooks）
  updated_2026_09_30: 补「shot」子命令用法（含工程包模式 --doc/--zoom，新 asset `shot_doc.mjs`）；关键事实新增"单页 .esch2 无符号库、要看真图必须用 .epro2"与工程包导出姿势；接口细节补 window.__ev/camera/DOM 事实
  updated_2026_09_30b: 公开化改写——本机绝对路径全部泛化为 EASYEDA_VIEWER_DIR 约定（默认 ~/easyeda-viewer）
---

# easyeda-viewer — 离线看图纸 / 落图视觉复核

## 它是什么

[`easyeda/easyeda-viewer`](https://github.com/easyeda/easyeda-viewer) 是一个**纯本地、离线、
单文件**的嘉立创EDA专业版工程查看器（v0.3，**只读**——不改源文件、不支持编辑/DRC/BOM）。

**安装**：clone 到任意目录（默认约定 `~/easyeda-viewer`，或设环境变量 `EASYEDA_VIEWER_DIR`），
完成 `npm install` + `npm run build`，产物 `dist/index.html`（约 390 kB，JS/CSS 全内联，双击即用）。

**在本库里的定位**：EDA 落图流程的**视觉复核环**。
`DRC 管电气正确性`（唯一权威），`viewer 管"画出来长什么样"`（分区、重叠、穿件走线、
位号与值是否可见）——两者互补，都不能替代对方。

## 关键事实（实测确立）

> **EDA 的 `getDocumentSource()` 输出就是 `.esch2` 的正文**，可直接存盘喂给 viewer。

实测：某工程三页（INT/PWR/AFE）经 `scripts/viewer.py dump` 落成 `.esch2` 后，
viewer 无头渲染结果 **0 个未知类型**：

| 页 | 渲染对象数 | 未知类型 |
|---|---|---|
| INT | 204 | 0 |
| PWR | 108 | 0 |
| AFE | 263 | 0 |

（这意味着**不需要**先在 EDA 里「导出工程」——直接读页面源码即可。）

**但单页 `.esch2` 只画得出"占位框"**（实测）：符号库不在页面记录流里，
元件全部渲染成**红色虚线框**（位号/值也没有），只有图框、文字、导线是准的。
⇒ **要看真正的图纸**（符号/位号/值/实物图）**必须喂工程包 `.epro2`**：

| 输入 | 渲染结果 |
|---|---|
| `.esch2`（单页，dump 得来） | 图框/文字/导线正确；**元件 = 红色虚线占位框** |
| `.epro2`（工程包） | **完整符号 + 位号 + 值**（文档树里另有 Library/符号 分支） |

**导出工程包**（EDA 侧）：`SYS_FileManager.getProjectFile(undefined, undefined, 'epro2')`
→ 得 `File` 对象 → 桥分块 base64 回传（1.9 MB 工程 ≈ 64 块，约半分钟）。
⚠️ **它导出的是"已保存"状态** —— 改完图**先 `Ctrl+S` 再导出**，否则拿到的是旧版
（实测症状：新旧两套注释并存、注释仍写已改掉的网名）。

## 用法

> 下文 `$SK` 指本 skill 的脚本路径（如 `~/.ai-skills/easyeda-viewer/scripts/viewer.py`，
> 换成你的实际库路径）；`python` 用你机器上的解释器。

### 1. 从 EDA 导出页面 + 起本地预览（最常用）

```bash
SK=~/.ai-skills/easyeda-viewer/scripts/viewer.py

python "$SK" dump  --all --out ./_view            # EDA 三页 -> ./_view/*.esch2
python "$SK" serve --dir ./_view --port 8931      # 组预览目录并起 127.0.0.1 服务
```

`serve` 会把 `dist/index.html` 复制进预览目录、启动 `http.server`（**绑 127.0.0.1**），
并打印形如 `http://127.0.0.1:8931/index.html?file=AFE.esch2` 的地址 —— 交给浏览器即可
**离线看图纸**。

### 2. 无头渲染自检（AI 自己核对"是否真画上了"）

```bash
python "$SK" render ./_view/INT.esch2 ./_view/AFE.esch2
```

输出每页的 `obj=`（渲染对象数）/ `unknown=`（viewer 不认识记录类型数）。
**`unknown=0` 且 obj 数与预期相符** = 这份源码 viewer 完全认得、确实有内容。
对象数突降 = 页面被写坏或读到了空页。

### 3. 直接看现成工程文件

`.epro2` / `.eprj3`（或打包的 `.zip`）/ `.epcb2` / `.epan2` / `.esym2` 都可：
把它们放进 `--dir` 再 `serve`，用 `?file=<名字>` 打开；或直接双击 `dist/index.html` 拖入。

### 4. 截图（**AI 的"眼睛"**）

```bash
python "$SK" shot --file INT.esch2 --out ./_view/int.png        # 单文件（也吃 .epro2）
python "$SK" shot --file board.epro2 --doc AFE --out ./_view/afe.png
python "$SK" shot --file board.epro2 --doc AFE --zoom 2300,1120,2 --out ./_view/u2.png
```

- 无头 Chrome（puppeteer-core + 本机 Chrome）截 **canvas 区域**；截图存 `--out`。
- `--doc <页名片段>`：先在**文档树**里点选该页再截（内部点 `.ev-tree-row`）。
  ⚠️ 这是**打开指定页的唯一可行路**——`?open=<页 uuid>` **实测无效**。
- `--zoom docX,docY,times`：以**文档坐标** `(docX,docY)` 为中心滚轮放大，每次 **×1.82**
  （`pow(1.0015, 400)`）。视野 ≈ 画布宽 / 倍率（1600px、2 次≈3.3× ⇒ 视野 ≈ 480 单位）。
  脚本会打印 `zoom: {px,py,scale0,scale1,inside}` 供核对。
- ⚠️ 直接改 `window.__ev.shell.camera.scale` / `centerOn()` **会被 viewer 的 fit 重置** ⇒
  必须走"算屏幕坐标 + 派发 wheel"这条路（`assets/shot_doc.mjs` 已实现）。
- **只读**：截图不碰源文件；但它反映的是**当前载入的快照**（改图后重新导出/重新 dump）。

## 接口细节（踩过的）

- viewer 的 `?file=<url>` 只在 **http(s)** 下有效 → 必须走 `serve`，不能 `file://`。
- **直接驱动 viewer 内部**（`shot_doc.mjs` 已用）：`window.__ev.shell.camera` 暴露
  `tx/ty/scale`（世界→屏幕：`screen = tx + world * scale`）；文档树节点 =
  `div.ev-tree-row` 内的 `span.ev-tree-label`；`window.__ev.shell.objects` 是图元集合
  （带 `id/kind/title/bbox`）。派发 `wheel{deltaY:-400}` 到 canvas 即缩放一次 ×1.82。
- 无头渲染走 viewer 仓库的 `vite-node -c vite.smoke.config.ts`（把 `leafer-ui` 换成
  无 DOM 的 `@leafer-ui/draw`）。**vite-node 的 fs 白名单限制脚本必须位于仓库内** →
  本 skill 把 `assets/render_headless.mjs` 复制到 `$EASYEDA_VIEWER_DIR/.bridge-work/skill/`
  （该目录已被上游 `.gitignore` 忽略，不污染仓库）再执行。
- Node 用你机器上能用的 node（≥18）；可用 `EASYEDA_VIEWER_NODE` 指定解释器，
  否则走 PATH 里的 `node`。`vite-node` 入口是仓库内的 `node_modules/vite-node/vite-node.mjs`。
- 面板/对象树/属性面板都可点，**只读**——不要指望它改图；改图回 EDA（见 skill
  `easyeda-schematic-net-fanout`）。

## 边界（别越界）

- **只读**：viewer 不写回、不校验电气。**连通性/DRC 的权威仍是 EDA 自己的 DRC**。
- 它渲染的是**导出时的快照** → 改完图要**重新 dump**，否则看的是旧图。
- `.efp2` 不支持；DRC/ERC/BOM/3D/Gerber 不支持。
- 从 EDA 读页面源码依赖 **easyeda-api 桥**；只打开现成文件则不需要桥。

## 维护

- viewer 本体升级：`cd "${EASYEDA_VIEWER_DIR:-~/easyeda-viewer}" && git pull && npm install && npm run build`。
- 本 skill 的脚本改动请同时更新本文件「关键事实」表（数值漂移要重测）。
